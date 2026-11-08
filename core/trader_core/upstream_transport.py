"""trader_core.upstream_transport - Pure stdlib Upstox V3 TLS WebSocket Client.

Provides:
- Outbound TLS WebSocket connection to authorized Upstox V3 feeder URL.
- Standard-library RFC 6455 client handshake and masking.
- Subscription frame transmission for canonical instrument keys.
- Automatic PING / PONG heartbeat handling.
- Binary Protobuf frame dispatch to callbacks.
- Reconnection with bounded exponential backoff and jitter.
- Zero external pip compilation dependencies.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import random
import re
import socket
import ssl
import struct
import threading
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .dashboard.relay import encode_ws_frame, read_ws_frame

logger = logging.getLogger(__name__)


class UpstoxStreamTransport:
    """Manages outbound TLS WebSocket streaming connection to Upstox API V3."""

    def __init__(
        self,
        token: Optional[str] = None,
        instrument_keys: Optional[List[str]] = None,
        on_binary_message: Optional[Callable[[bytes], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        on_market_status: Optional[Callable[[Dict[str, str]], None]] = None,
        ws_url: Optional[str] = None,
        reconnect_delay: float = 1.0,
        max_reconnect_attempts: Optional[int] = None,
    ):
        self.token = token or ""
        self.instrument_keys = instrument_keys or []
        self.on_binary_message = on_binary_message
        self.on_status = on_status
        self.on_market_status = on_market_status
        self.ws_url = ws_url
        self.base_reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts

        self._running = False
        self._connected = False
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def is_connected(self) -> bool:
        """Returns True if the transport is actively connected."""
        return self._connected

    def set_instrument_keys(self, keys: List[str]) -> None:
        """Update subscription instrument keys and resubscribe if connected."""
        with self._lock:
            self.instrument_keys = list(dict.fromkeys(keys))
            if self._connected and self._sock:
                self._send_subscription(self._sock)

    def _notify_status(self, status: str) -> None:
        if self.on_status:
            try:
                self.on_status(status)
            except Exception as e:
                logger.error("Error in on_status callback: %s", e)

    def _authorize_ws(self) -> str:
        """Query Upstox REST API to retrieve authorized WebSocket redirect URI."""
        url = "https://api.upstox.com/v3/feed/market-data-feed/authorize"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "DalalStreetTrader/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            uri = data.get("data", {}).get("authorizedRedirectUri")
            if not uri:
                raise ValueError(
                    f"No authorizedRedirectUri in Upstox response: {data}"
                )
            return uri

    def _open_socket(self, uri: str) -> socket.socket:
        """Open raw TCP or TLS socket and perform RFC 6455 client handshake."""
        parsed = urllib.parse.urlparse(uri)
        is_ssl = parsed.scheme in ("wss", "https")
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if is_ssl else 80)
        path = parsed.path + ("?" + parsed.query if parsed.query else "")
        if not path:
            path = "/"

        raw_sock = socket.create_connection((host, port), timeout=10.0)
        if is_ssl:
            ctx = ssl.create_default_context()
            sock = ctx.wrap_socket(raw_sock, server_hostname=host)
        else:
            sock = raw_sock

        nonce = base64.b64encode(os.urandom(16)).decode()
        handshake = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {nonce}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "User-Agent: DalalStreetTrader/1.0\r\n\r\n"
        )
        sock.sendall(handshake.encode("utf-8"))

        # Read HTTP response headers
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = sock.recv(1024)
            if not chunk:
                sock.close()
                raise ConnectionError(
                    "Server closed connection during WebSocket handshake"
                )
            resp += chunk

        header_text = resp.split(b"\r\n\r\n")[0].decode(errors="replace")
        status_line = header_text.split("\r\n")[0]
        if "101" not in status_line:
            sock.close()
            raise ConnectionError(
                f"WebSocket handshake failed: {status_line}"
            )

        return sock

    def _send_subscription(self, sock: socket.socket) -> None:
        """Send client-masked JSON subscription frame."""
        if not self.instrument_keys:
            return
        sub_payload = json.dumps({
            "guid": f"sub-{os.getpid()}-{int(time.time())}",
            "method": "sub",
            "data": {
                "mode": "full",
                "instrumentKeys": self.instrument_keys,
            },
        }).encode("utf-8")
        # Upstox V3 feeder accepts binary opcode 2 frame for subscription request
        frame = encode_ws_frame(sub_payload, opcode=2, mask=True)
        sock.sendall(frame)
        logger.info(
            "Sent Upstox subscription for %d instruments",
            len(self.instrument_keys),
        )

    def connect_once(self) -> None:
        """Perform a single connection attempt and read loop until socket disconnect."""
        self._running = True
        uri = self.ws_url or self._authorize_ws()
        self._notify_status("CONNECTING")

        sock = self._open_socket(uri)
        with self._lock:
            self._sock = sock
            self._connected = True

        self._notify_status("CONNECTED")

        # Send initial subscription
        with self._lock:
            self._send_subscription(sock)

        sock.settimeout(5.0)

        # Read loop
        try:
            while self._running and self._connected:
                try:
                    res = read_ws_frame(sock)
                except (socket.timeout, TimeoutError):
                    continue
                except (ConnectionResetError, BrokenPipeError, OSError):
                    break

                if not res:
                    break

                opcode, payload, is_final = res

                # Handle PING (opcode 9) -> reply with client-masked PONG (opcode 10)
                if opcode == 9:
                    pong = encode_ws_frame(payload, opcode=10, mask=True)
                    try:
                        sock.sendall(pong)
                    except Exception:
                        break
                elif opcode == 8:  # CLOSE
                    break
                elif opcode == 2:  # BINARY (Protobuf)
                    if self.on_binary_message:
                        try:
                            self.on_binary_message(payload)
                        except Exception as e:
                            logger.error(
                                "Error in on_binary_message callback: %s", e
                            )
        finally:
            with self._lock:
                self._connected = False
                try:
                    sock.close()
                except Exception:
                    pass
                if self._sock == sock:
                    self._sock = None

            self._notify_status("DISCONNECTED")

    def _run_reconnect_loop(self) -> None:
        """Background thread executing connection with bounded exponential backoff."""
        attempt = 0
        while self._running:
            try:
                self.connect_once()
            except Exception as e:
                logger.warning(
                    "Upstox connection attempt %d failed: %s", attempt + 1, e
                )
                self._notify_status("DISCONNECTED")

            if not self._running:
                break

            attempt += 1
            if (
                self.max_reconnect_attempts is not None
                and attempt >= self.max_reconnect_attempts
            ):
                logger.warning(
                    "Max reconnect attempts reached (%d). Halting loop.", attempt
                )
                break

            delay = min(30.0, self.base_reconnect_delay * (2 ** min(attempt, 5)))
            jitter = random.uniform(0.0, 0.5)
            time.sleep(delay + jitter)

    def connect(self) -> None:
        """Start the streaming connection in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_reconnect_loop, daemon=True
        )
        self._thread.start()

    def disconnect(self) -> None:
        """Disconnect and stop streaming thread."""
        self._running = False
        with self._lock:
            self._connected = False
            if self._sock:
                try:
                    self._sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None
        if self._thread and threading.current_thread() != self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._notify_status("DISCONNECTED")
