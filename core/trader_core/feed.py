"""trader_core.feed - Upstox V3 WebSocket feed lifecycle manager and stale detection.

Handles:
- Socket lifecycle states: DISCONNECTED -> CONNECTING -> CONNECTED -> STALE.
- Pure Python Protobuf decoding of Upstox V3 MarketDataFeed ticks.
- Injected monotonic clock for deterministic stale detection (>15s timeout during market hours).
- Market-status-first synchronization and OAuth authorization validation.
- Bounded exponential backoff reconnection schedule (1s..30s with jitter).
- Filtering of duplicate and out-of-order ticks based on exchange timestamps.
- Clock skew / drift detection (>30s).
- Bounded subscription limits (default 100 instruments).
- Recovery invariant from STALE: requires transport reconnect, exchange status confirmation,
  snapshot sync, and a newly completed valid bar before strategy signals unlock.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
from enum import Enum
import random
import time
from typing import Any, Callable, Dict, List, Optional, Set

from .calendar import IST, ExchangeCalendar, get_default_calendar
from .proto_decoder import (
    ProtobufDecodeError,
    Tick,
    decode_market_data_feed,
    extract_ticks,
)


class FeedStatus(Enum):
    """WebSocket feed connection lifecycle status."""
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    STALE = "STALE"


class FeedError(Exception):
    """Base exception for market data feed failures."""
    pass


class FeedAuthenticationError(FeedError):
    """Raised when WebSocket authorization or redirect handshake fails."""
    pass


class SubscriptionLimitExceededError(FeedError):
    """Raised when attempting to subscribe to more instruments than allowed."""
    pass


class StaleFeedError(FeedError):
    """Raised when feed inactivity exceeds allowable timeout during market hours."""
    pass


class ClockSkewError(FeedError):
    """Raised when exchange tick timestamp diverges substantially from system clock."""
    pass


class UpstoxFeedManager:
    """Manages Upstox V3 WebSocket connection lifecycle, decoding, and health monitoring."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        access_token: Optional[str] = None,
        stale_timeout_seconds: float = 15.0,
        skew_threshold_seconds: float = 30.0,
        max_subscriptions: int = 100,
        clock: Optional[Callable[[], float]] = None,
        wall_clock: Optional[Callable[[], datetime.datetime]] = None,
        calendar: Optional[ExchangeCalendar] = None,
        auth_handler: Optional[Callable[[], Any]] = None,
    ):
        from .providers.upstox import _find_credentials
        creds = _find_credentials()
        self.api_key = api_key or creds.get("api_key", "")
        self.access_token = access_token or creds.get("access_token", "")
        self.stale_timeout_seconds = float(stale_timeout_seconds)
        self.skew_threshold_seconds = float(skew_threshold_seconds)
        self.max_subscriptions = int(max_subscriptions)

        # Injected clocks for deterministic testing and production execution
        self._clock = clock if clock is not None else time.monotonic
        self._wall_clock = (
            wall_clock if wall_clock is not None
            else (lambda: datetime.datetime.now(IST))
        )
        self.calendar = calendar if calendar is not None else get_default_calendar()
        self.auth_handler = auth_handler

        # Internal state
        self._status = FeedStatus.DISCONNECTED
        self._signals_unlocked = False
        self._subscribed_instruments: Set[str] = set()
        self._last_tick_monotonic_timestamp = 0.0
        self._last_tick_timestamp_by_instrument: Dict[str, int] = {}
        self._market_status: Optional[str] = None

        # Recovery tracking
        self._pending_recovery = False
        self._snapshot_synced = False
        self._recovery_bar_completed = False

        # Callbacks
        self._tick_listeners: List[Callable[[Tick], None]] = []
        self._status_listeners: List[Callable[[FeedStatus], None]] = []

    @property
    def status(self) -> FeedStatus:
        """Current feed lifecycle status."""
        return self._status

    @property
    def is_signals_unlocked(self) -> bool:
        """Whether strategy signals are permitted to evaluate."""
        return self._signals_unlocked

    @property
    def subscribed_instruments(self) -> Set[str]:
        """Currently subscribed instrument keys."""
        return set(self._subscribed_instruments)

    @property
    def last_tick_monotonic(self) -> float:
        """Monotonic timestamp of last verified tick."""
        return self._last_tick_monotonic_timestamp

    def add_tick_listener(self, callback: Callable[[Tick], None]) -> None:
        """Register a callback for decoded ticks."""
        self._tick_listeners.append(callback)

    def add_status_listener(self, callback: Callable[[FeedStatus], None]) -> None:
        """Register a callback for feed status transitions."""
        self._status_listeners.append(callback)

    def _set_status(self, new_status: FeedStatus) -> None:
        if self._status != new_status:
            self._status = new_status
            for listener in self._status_listeners:
                try:
                    listener(new_status)
                except Exception:
                    pass

    def connect(self) -> None:
        """Initiate connection and authorization."""
        if self.auth_handler is not None:
            try:
                self.auth_handler()
            except Exception as e:
                self._set_status(FeedStatus.DISCONNECTED)
                self._signals_unlocked = False
                if isinstance(e, FeedAuthenticationError):
                    raise
                raise FeedAuthenticationError(
                    f"Authentication failed: {e}"
                ) from e

        # Socket transitions to CONNECTING
        self._set_status(FeedStatus.CONNECTING)
        self._signals_unlocked = False
        self._market_status = None

    def reconnect(self) -> None:
        """Initiate reconnection after disconnection or stale state."""
        self._pending_recovery = True
        self._snapshot_synced = False
        self._recovery_bar_completed = False
        self.connect()

    def disconnect(self) -> None:
        """Disconnect WebSocket feed and lock signals."""
        self._set_status(FeedStatus.DISCONNECTED)
        self._signals_unlocked = False
        self._pending_recovery = False

    def sync_market_status(self, market_status: str) -> None:
        """Synchronize exchange market status (market-status-first)."""
        self._market_status = market_status
        is_open = market_status.upper() in ("NORMAL_OPEN", "OPEN")

        if self._status in (FeedStatus.CONNECTING, FeedStatus.STALE):
            if is_open:
                self._set_status(FeedStatus.CONNECTED)
                self._last_tick_monotonic_timestamp = self._clock()

                # If this connection was recovering from STALE, signals stay locked
                # until snapshot sync and complete bar notification.
                if self._pending_recovery:
                    self._check_recovery_completion()
                else:
                    self._signals_unlocked = True
            else:
                # Market is not open (e.g. CLOSED)
                if self._status == FeedStatus.CONNECTING:
                    self._set_status(FeedStatus.CONNECTED)
                    self._signals_unlocked = False

    def sync_snapshot(self, snapshot_data: Any) -> None:
        """Mark snapshot data as synchronized during stale recovery."""
        self._snapshot_synced = True
        self._check_recovery_completion()

    def notify_bar_completed(self, bar_timestamp: datetime.datetime) -> None:
        """Notify feed manager that a full 5-minute bar has completed."""
        self._recovery_bar_completed = True
        self._check_recovery_completion()

    def _check_recovery_completion(self) -> None:
        """Check if all requirements to exit recovery and unlock signals are met."""
        if not self._pending_recovery:
            return

        is_open = (
            self._market_status
            and self._market_status.upper() in ("NORMAL_OPEN", "OPEN")
        )
        if (
            self._status == FeedStatus.CONNECTED
            and is_open
            and self._snapshot_synced
            and self._recovery_bar_completed
        ):
            self._pending_recovery = False
            self._signals_unlocked = True

    def subscribe(self, instruments: List[str]) -> None:
        """Subscribe to a list of instrument keys, validating limits."""
        new_items = set(instruments)
        potential_total = len(self._subscribed_instruments.union(new_items))
        if potential_total > self.max_subscriptions:
            raise SubscriptionLimitExceededError(
                f"Subscribing to {len(new_items)} instruments would exceed max limit "
                f"of {self.max_subscriptions} (current: {len(self._subscribed_instruments)})"
            )
        self._subscribed_instruments.update(new_items)

    def unsubscribe(self, instruments: List[str]) -> None:
        """Unsubscribe from instrument keys."""
        for inst in instruments:
            self._subscribed_instruments.discard(inst)

    def process_binary_message(self, data: bytes) -> List[Tick]:
        """Process incoming binary WebSocket frame from Upstox V3."""
        decoded = decode_market_data_feed(data)
        extracted = extract_ticks(decoded)

        # Synchronize market status if provided in frame
        ms = decoded.get("market_status")
        if ms and self._status == FeedStatus.CONNECTING:
            nse_st = (
                ms.get("NSE_EQ")
                or ms.get("NSE_FO")
                or next(iter(ms.values()), "")
            )
            if nse_st:
                self.sync_market_status(nse_st)

        now_mono = self._clock()
        now_wall = self._wall_clock()
        now_wall_ts = now_wall.timestamp()

        valid_ticks: List[Tick] = []

        for inst_key, tick in extracted.items():
            # Check clock skew if tick contains timestamp
            if tick.ltt > 0:
                tick_ts = tick.ltt / 1000.0
                # Future clock skew: exchange timestamp ahead of local system clock
                if (tick_ts - now_wall_ts) > self.skew_threshold_seconds:
                    raise ClockSkewError(
                        f"Tick timestamp {tick_ts:.1f} diverges into future "
                        f"from system clock {now_wall_ts:.1f} by "
                        f"{(tick_ts - now_wall_ts):.1f}s "
                        f"(threshold: {self.skew_threshold_seconds}s)"
                    )
                # Stale tick: tick from past (e.g. untraded symbol from yesterday
                # or >30s old snapshot). Skip rather than failing the entire frame.
                if (now_wall_ts - tick_ts) > self.skew_threshold_seconds:
                    continue

                # Check duplicate or out-of-order tick
                last_ltt = self._last_tick_timestamp_by_instrument.get(inst_key, 0)
                if tick.ltt <= last_ltt:
                    # Ignore duplicate or old tick
                    continue
                self._last_tick_timestamp_by_instrument[inst_key] = tick.ltt

            valid_ticks.append(tick)

        if valid_ticks:
            self._last_tick_monotonic_timestamp = now_mono
            if self._status in (FeedStatus.CONNECTING, FeedStatus.STALE):
                if self.is_in_market_hours():
                    self._set_status(FeedStatus.CONNECTED)
                    if not self._pending_recovery:
                        self._signals_unlocked = True

        # Emit ticks if feed is active
        for tick in valid_ticks:
            for listener in self._tick_listeners:
                try:
                    listener(tick)
                except Exception:
                    pass

        return valid_ticks

    def handle_heartbeat(self) -> None:
        """Record heartbeat ping/pong to reset the inactivity timer."""
        self._last_tick_monotonic_timestamp = self._clock()

    def is_in_market_hours(self) -> bool:
        """Determine whether current wall clock is within NSE/BSE regular trading hours."""
        now = self._wall_clock()
        if now.tzinfo is None:
            now = now.replace(tzinfo=IST)
        else:
            now = now.astimezone(IST)

        today = now.date()
        if not self.calendar.is_trading_day(today):
            return False

        # Regular NSE trading window: 09:15:00 to 15:30:00 IST
        market_open = datetime.time(9, 15, 0)
        market_close = datetime.time(15, 30, 0)
        current_time = now.time()

        return market_open <= current_time <= market_close

    def check_health(self) -> FeedStatus:
        """Check feed freshness and transition to STALE if inactivity exceeds threshold."""
        if self._status != FeedStatus.CONNECTED:
            return self._status

        # If outside market hours, do not declare stale based on tick inactivity
        if not self.is_in_market_hours():
            return self._status

        now_mono = self._clock()
        elapsed = now_mono - self._last_tick_monotonic_timestamp

        if elapsed > self.stale_timeout_seconds:
            self._set_status(FeedStatus.STALE)
            self._signals_unlocked = False
            self._pending_recovery = True
            self._snapshot_synced = False
            self._recovery_bar_completed = False

        return self._status

    def get_reconnect_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay (1s..30s) with randomized +/-20% jitter."""
        base_delay = min(30.0, 1.0 * (2 ** attempt))
        # Jitter +/- 20%
        jitter_factor = random.uniform(-0.20, 0.20)
        delay = base_delay * (1.0 + jitter_factor)
        # Bounded between 0.7s and 36s (30s * 1.2)
        return max(0.5, delay)
