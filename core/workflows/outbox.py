"""trader_workflows.outbox - Transactional Outbox Dispatcher for Inngest.

Runs as a decoupled background daemon thread polling pending semantic events
from OutboxRepository and delivering them to Inngest via HTTPS with bounded
backoff and deterministic idempotency.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from core.trader_core.storage.repository import OutboxRepository, sanitize_storage_data
from core.workflows.publisher import _find_inngest_credentials

logger = logging.getLogger(__name__)


class OutboxDispatcher:
    """Dispatches durable outbox events to Inngest asynchronously with bounded retry backoff."""

    def __init__(
        self,
        repository: OutboxRepository,
        event_key: Optional[str] = None,
        app_id: Optional[str] = None,
        base_url: str = "https://inn.gs/e/",
        poll_interval: float = 1.0,
        batch_size: int = 20,
        max_retries: int = 5,
        backoff_base: float = 1.0,
        backoff_max: float = 30.0,
    ):
        self.repository = repository
        creds = _find_inngest_credentials()
        self.event_key = event_key or creds.get("event_key", "")
        self.app_id = app_id or creds.get("app_id", "stockpulse-pro")
        self.base_url = base_url.rstrip("/") + "/"
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def is_enabled(self) -> bool:
        """Returns True if an Inngest event key is configured."""
        return bool(self.event_key)

    def dispatch_single_event(self, event: Dict[str, Any]) -> bool:
        """Attempt to deliver a single outbox event to Inngest."""
        if not self.is_enabled():
            return False

        event_id = event["id"]
        event_name = event["event_name"]
        idempotency_key = event["idempotency_key"]
        payload_data = event.get("payload")
        if not isinstance(payload_data, dict):
            try:
                payload_data = json.loads(event["payload_json"])
            except Exception:
                payload_data = {}

        clean_payload = sanitize_storage_data(payload_data)
        now_ms = int(time.time() * 1000)

        inngest_event = {
            "name": event_name,
            "data": clean_payload,
            "user": {"id": "trader"},
            "ts": now_ms,
            "id": idempotency_key,
        }

        url = f"{self.base_url}{self.event_key}"
        body_bytes = json.dumps(inngest_event).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body_bytes,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"{self.app_id}/1.0",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 201, 202):
                    self.repository.mark_dispatched(event_id)
                    logger.debug("Successfully dispatched outbox event %s (%s)", event_id, event_name)
                    return True
                error_msg = f"Inngest returned HTTP {resp.status}"
                logger.warning(error_msg)
                self.repository.mark_failed(event_id, error_msg, max_retries=self.max_retries)
                return False
        except urllib.error.HTTPError as he:
            if 400 <= he.code < 500 and he.code != 429:
                err = f"HTTP {he.code}: {he.reason}"
                logger.error("Non-retryable Inngest HTTP error for %s: %s", event_name, err)
                self.repository.mark_failed(event_id, err, max_retries=0)
            else:
                err = f"HTTP {he.code}: {he.reason}"
                logger.warning("Retryable Inngest HTTP error for %s: %s", event_name, err)
                self.repository.mark_failed(event_id, err, max_retries=self.max_retries)
            return False
        except Exception as exc:
            err = f"Network or dispatch error: {exc}"
            logger.warning("Inngest dispatch error for %s: %s", event_name, err)
            self.repository.mark_failed(event_id, err, max_retries=self.max_retries)
            return False

    def dispatch_pending(self, batch_size: Optional[int] = None) -> int:
        """Poll pending outbox rows and dispatch them."""
        if not self.is_enabled():
            return 0

        limit = batch_size or self.batch_size
        events = self.repository.fetch_pending(limit=limit)
        if not events:
            return 0

        dispatched_count = 0
        for ev in events:
            if self._stop_event.is_set():
                break
            success = self.dispatch_single_event(ev)
            if success:
                dispatched_count += 1
            else:
                retries = ev.get("retry_count", 0) + 1
                backoff = min(self.backoff_max, self.backoff_base * (2 ** min(retries, 6)))
                logger.debug("Dispatch failure, backing off for %.1fs", backoff)
                if not self._stop_event.is_set():
                    self._stop_event.wait(min(backoff, 1.0))

        return dispatched_count

    def _worker_loop(self) -> None:
        """Background worker thread loop polling outbox."""
        logger.info("OutboxDispatcher background daemon thread started.")
        while not self._stop_event.is_set():
            try:
                self.dispatch_pending()
            except Exception as e:
                logger.warning("Unexpected error in OutboxDispatcher loop: %s", e)
            self._stop_event.wait(self.poll_interval)
        logger.info("OutboxDispatcher background daemon thread stopped.")

    def start(self) -> None:
        """Start background daemon thread."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="OutboxDispatcher")
            self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Stop background daemon thread cleanly."""
        with self._lock:
            if self._thread is None:
                return
            self._stop_event.set()
            self._thread.join(timeout=timeout)
            self._thread = None
