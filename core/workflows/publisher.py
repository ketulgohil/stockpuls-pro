"""trader_workflows.publisher - Semantic Event Publisher for Inngest.

Decoupled from live market data:
- Operates in no-op mode if INNGEST_EVENT_KEY is not configured.
- Publishes only coarse-grained semantic events.
- Never publishes raw high-frequency tick streams.
- Strips sensitive tokens and credentials from payloads.
- Uses deterministic idempotency keys to ensure retry safety.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import queue
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SENSITIVE_KEY_SUBSTRINGS = {"access_token", "api_key", "secret", "password", "token"}


def sanitize_workflow_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Strip any credential or secret fields from event payloads."""
    clean: Dict[str, Any] = {}
    for k, v in data.items():
        k_lower = k.lower()
        if k_lower in ("instrument_key", "key") and isinstance(v, str) and ("|" in v or len(v) < 15):
            clean[k] = v
            continue
        if any(bad in k_lower for bad in SENSITIVE_KEY_SUBSTRINGS):
            continue
        clean[k] = v
    return clean


def _find_inngest_credentials() -> Dict[str, str]:
    """Auto-discover Inngest keys from environment or trader/credentials.json."""
    creds = {
        "event_key": os.getenv("INNGEST_EVENT_KEY", ""),
        "signing_key": os.getenv("INNGEST_SIGNING_KEY", ""),
        "app_id": os.getenv("INNGEST_APP_ID", "stockpulse-pro"),
    }
    if creds["event_key"] and creds["signing_key"]:
        return creds

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates = [
        "trader/credentials.json",
        "credentials.json",
        os.path.join(root, "trader", "credentials.json"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    if not creds["event_key"]:
                        creds["event_key"] = data.get("inngest_event_key") or data.get("INNGEST_EVENT_KEY") or ""
                    if not creds["signing_key"]:
                        creds["signing_key"] = data.get("inngest_signing_key") or data.get("INNGEST_SIGNING_KEY") or ""
                    if creds["event_key"]:
                        break
            except Exception:
                pass
    return creds


class InngestEventPublisher:
    """Asynchronous semantic event publisher for Inngest workflows."""

    def __init__(
        self,
        event_key: Optional[str] = None,
        app_id: Optional[str] = None,
        base_url: str = "https://inn.gs/e/",
        async_dispatch: bool = True,
    ):
        creds = _find_inngest_credentials()
        self.event_key = event_key or creds.get("event_key", "")
        self.app_id = app_id or creds.get("app_id", "stockpulse-pro")
        self.base_url = base_url.rstrip("/") + "/"
        self.async_dispatch = async_dispatch

        self._queue: queue.Queue = queue.Queue(maxsize=1000)
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def is_enabled(self) -> bool:
        """Returns True if an Inngest event key is configured."""
        return bool(self.event_key)

    def _ensure_worker(self) -> None:
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._stop_event.clear()
            self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker_thread.start()

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            event_name, data, timestamp = item
            self._send_immediate(event_name, data, timestamp)
            self._queue.task_done()

    def _send_immediate(
        self,
        event_name: str,
        data: Dict[str, Any],
        timestamp: Optional[str] = None,
    ) -> bool:
        try:
            sanitized = sanitize_workflow_data(data)
            sym = sanitized.get("symbol", "market")
            now_ms = int(time.time() * 1000)

            id_seed = f"{event_name}:{sym}:{timestamp or now_ms}"
            event_id = f"{event_name.replace('/', '.')}-{sym}-{hashlib.sha256(id_seed.encode()).hexdigest()[:12]}"

            event_payload = {
                "name": event_name,
                "data": sanitized,
                "user": {"id": "trader"},
                "ts": now_ms,
                "id": event_id,
            }

            url = f"{self.base_url}{self.event_key}"
            body_bytes = json.dumps(event_payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body_bytes,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": f"{self.app_id}/1.0",
                },
            )

            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 201, 202):
                    return True
                logger.warning("Inngest answered HTTP %d for %s", resp.status, event_name)
                return False
        except Exception as e:
            logger.warning("Failed to publish Inngest event %s: %s", event_name, e)
            return False

    def publish(
        self,
        event_name: str,
        data: Dict[str, Any],
        timestamp: Optional[str] = None,
    ) -> bool:
        """Publishes a single semantic event to Inngest without blocking."""
        if not self.is_enabled():
            return False

        if not self.async_dispatch:
            return self._send_immediate(event_name, data, timestamp)

        self._ensure_worker()
        try:
            self._queue.put_nowait((event_name, data, timestamp))
            return True
        except queue.Full:
            logger.warning("Inngest event queue full, dropping event: %s", event_name)
            return False


_global_publisher: Optional[InngestEventPublisher] = None


def get_event_publisher() -> InngestEventPublisher:
    """Retrieve or initialize singleton event publisher."""
    global _global_publisher
    if _global_publisher is None:
        _global_publisher = InngestEventPublisher()
    return _global_publisher
