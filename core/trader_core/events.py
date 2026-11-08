"""trader_core.events - Shared Domain Event Contracts for Live Market Data.

Defines canonical immutable schemas for:
- QuoteEvent (normalized top-of-book / snapshot)
- TickEvent (raw trade tick with exchange & receive timestamps)
- CandleEvent (5-minute and session bars)
- FeedStatusEvent (lifecycle transitions)
- AlertEvent (deterministic decision alerts)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import math
from typing import Any, Dict, Optional

SCHEMA_VERSION = "1.0.0"

FEED_LIFECYCLE_STATES = {
    "STOPPED",
    "CONNECTING",
    "AUTHENTICATING",
    "SUBSCRIBING",
    "WARMING",
    "LIVE",
    "STALE",
    "RECOVERING",
    "DISCONNECTED",
    "MARKET_CLOSED",
}


def _ensure_aware_dt(dt: Optional[datetime]) -> datetime:
    """Ensures a datetime object is timezone-aware; defaults to UTC if naive or None."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_dt(val: Any) -> datetime:
    if isinstance(val, datetime):
        return _ensure_aware_dt(val)
    if isinstance(val, str):
        if not val.strip():
            raise ValueError("Timestamp string cannot be empty")
        dt = datetime.fromisoformat(val)
        return _ensure_aware_dt(dt)
    if val is None:
        return datetime.now(timezone.utc)
    raise ValueError(f"Cannot parse timestamp from {val!r}")


@dataclass(frozen=True)
class QuoteEvent:
    """Normalized top-of-book / quote event."""

    symbol: str
    instrument_key: str
    ltp: float
    quote_time: datetime
    prev_close: Optional[float] = None
    volume: int = 0
    receive_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if not math.isfinite(self.ltp) or self.ltp <= 0:
            raise ValueError(f"ltp must be positive and finite, got {self.ltp}")
        if self.prev_close is not None:
            if not math.isfinite(self.prev_close) or self.prev_close <= 0:
                raise ValueError(
                    f"prev_close must be positive and finite, got {self.prev_close}"
                )
        if self.volume < 0:
            raise ValueError(f"volume cannot be negative, got {self.volume}")
        object.__setattr__(self, "quote_time", _ensure_aware_dt(self.quote_time))
        object.__setattr__(
            self, "receive_time", _ensure_aware_dt(self.receive_time)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "symbol": self.symbol,
            "instrument_key": self.instrument_key,
            "ltp": float(self.ltp),
            "prev_close": float(self.prev_close)
            if self.prev_close is not None
            else None,
            "volume": int(self.volume),
            "quote_time": self.quote_time.isoformat(),
            "receive_time": self.receive_time.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QuoteEvent":
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            symbol=data["symbol"],
            instrument_key=data.get("instrument_key", ""),
            ltp=float(data["ltp"]),
            quote_time=_parse_dt(data.get("quote_time")),
            prev_close=float(data["prev_close"])
            if data.get("prev_close") is not None
            else None,
            volume=int(data.get("volume", 0)),
            receive_time=_parse_dt(data.get("receive_time")),
        )


@dataclass(frozen=True)
class TickEvent:
    """Individual trade tick."""

    symbol: str
    instrument_key: str
    price: float
    quantity: int
    exchange_time: datetime
    receive_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if not math.isfinite(self.price) or self.price <= 0:
            raise ValueError(f"price must be positive and finite, got {self.price}")
        if self.quantity < 0:
            raise ValueError(f"quantity cannot be negative, got {self.quantity}")
        object.__setattr__(self, "exchange_time", _ensure_aware_dt(self.exchange_time))
        object.__setattr__(
            self, "receive_time", _ensure_aware_dt(self.receive_time)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "symbol": self.symbol,
            "instrument_key": self.instrument_key,
            "price": float(self.price),
            "quantity": int(self.quantity),
            "exchange_time": self.exchange_time.isoformat(),
            "receive_time": self.receive_time.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TickEvent":
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            symbol=data["symbol"],
            instrument_key=data.get("instrument_key", ""),
            price=float(data["price"]),
            quantity=int(data.get("quantity", 0)),
            exchange_time=_parse_dt(data.get("exchange_time")),
            receive_time=_parse_dt(data.get("receive_time")),
        )

    @classmethod
    def from_feed_tick(cls, tick: Any, symbol: Optional[str] = None) -> "TickEvent":
        inst_key = getattr(tick, "instrument_key", "")
        if not symbol:
            if inst_key:
                try:
                    from trader_core.providers.base import InstrumentMaster

                    symbol = InstrumentMaster().resolve(inst_key).symbol
                except Exception:
                    symbol = inst_key.split("|")[-1].strip().upper()
            else:
                symbol = "UNKNOWN"
        ltt = getattr(tick, "ltt", None)
        if ltt:
            exchange_time = datetime.fromtimestamp(ltt / 1000.0, tz=timezone.utc)
        else:
            exchange_time = datetime.now(timezone.utc)
        return cls(
            symbol=symbol,
            instrument_key=inst_key,
            price=float(getattr(tick, "ltp", 0.0)),
            quantity=int(getattr(tick, "ltq", 0) or 0),
            exchange_time=exchange_time,
        )


@dataclass(frozen=True)
class CandleEvent:
    """Normalized OHLCV candle."""

    symbol: str
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    timestamp: datetime
    is_complete: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        for k, v in [
            ("open", self.open),
            ("high", self.high),
            ("low", self.low),
            ("close", self.close),
        ]:
            if not math.isfinite(v) or v <= 0:
                raise ValueError(f"{k} must be positive and finite, got {v}")
        if self.high < self.low:
            raise ValueError(
                f"high ({self.high}) cannot be less than low ({self.low})"
            )
        if self.open > self.high or self.open < self.low:
            raise ValueError(
                f"open ({self.open}) out of bounds [{self.low}, {self.high}]"
            )
        if self.close > self.high or self.close < self.low:
            raise ValueError(
                f"close ({self.close}) out of bounds [{self.low}, {self.high}]"
            )
        if self.volume < 0:
            raise ValueError(f"volume cannot be negative, got {self.volume}")
        object.__setattr__(self, "timestamp", _ensure_aware_dt(self.timestamp))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "symbol": self.symbol,
            "interval": self.interval,
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": int(self.volume),
            "timestamp": self.timestamp.isoformat(),
            "is_complete": bool(self.is_complete),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CandleEvent":
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            symbol=data["symbol"],
            interval=data.get("interval", "5m"),
            open=float(data["open"]),
            high=float(data["high"]),
            low=float(data["low"]),
            close=float(data["close"]),
            volume=int(data.get("volume", 0)),
            timestamp=_parse_dt(data.get("timestamp")),
            is_complete=bool(data.get("is_complete", False)),
        )


@dataclass(frozen=True)
class FeedStatusEvent:
    """Feed lifecycle status update."""

    feed_name: str
    state: str
    reason: str = ""
    last_tick_time: Optional[datetime] = None
    stale_seconds: float = 0.0
    active_subscriptions: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        st = self.state.upper()
        if st not in FEED_LIFECYCLE_STATES:
            raise ValueError(
                f"Invalid feed lifecycle state: {self.state}. "
                f"Allowed: {sorted(FEED_LIFECYCLE_STATES)}"
            )
        object.__setattr__(self, "state", st)
        if self.last_tick_time:
            object.__setattr__(
                self, "last_tick_time", _ensure_aware_dt(self.last_tick_time)
            )
        object.__setattr__(self, "timestamp", _ensure_aware_dt(self.timestamp))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "feed_name": self.feed_name,
            "state": self.state,
            "reason": self.reason,
            "last_tick_time": self.last_tick_time.isoformat()
            if self.last_tick_time
            else None,
            "stale_seconds": float(self.stale_seconds),
            "active_subscriptions": int(self.active_subscriptions),
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeedStatusEvent":
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            feed_name=data.get("feed_name", "upstox"),
            state=data["state"],
            reason=data.get("reason", ""),
            last_tick_time=_parse_dt(data.get("last_tick_time"))
            if data.get("last_tick_time")
            else None,
            stale_seconds=float(data.get("stale_seconds", 0.0)),
            active_subscriptions=int(data.get("active_subscriptions", 0)),
            timestamp=_parse_dt(data.get("timestamp")),
        )

    @classmethod
    def from_status(
        cls, status: Any, feed_name: str = "upstox", reason: str = ""
    ) -> "FeedStatusEvent":
        val = getattr(status, "value", str(status)).upper()
        state_map = {
            "CONNECTED": "LIVE",
            "SYNCING": "LIVE",
            "DISCONNECTED": "DISCONNECTED",
            "STALE": "STALE",
            "RECOVERING": "RECOVERING",
            "AUTHENTICATING": "AUTHENTICATING",
            "CONNECTING": "CONNECTING",
            "MARKET_CLOSED": "MARKET_CLOSED",
            "STOPPED": "STOPPED",
        }
        canonical_state = state_map.get(
            val, val if val in FEED_LIFECYCLE_STATES else "DISCONNECTED"
        )
        return cls(
            feed_name=feed_name,
            state=canonical_state,
            reason=reason or f"Feed status transition to {val}",
        )


@dataclass(frozen=True)
class AlertEvent:
    """Strategy or price alert trigger event."""

    alert_type: str
    symbol: str
    price: float
    timestamp: datetime
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    decision_id: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default="")
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if not math.isfinite(self.price) or self.price <= 0:
            raise ValueError(f"price must be positive and finite, got {self.price}")
        if self.stop_loss is not None:
            if not math.isfinite(self.stop_loss) or self.stop_loss <= 0:
                raise ValueError(
                    f"stop_loss must be positive and finite, got {self.stop_loss}"
                )
        if self.target is not None:
            if not math.isfinite(self.target) or self.target <= 0:
                raise ValueError(
                    f"target must be positive and finite, got {self.target}"
                )
        object.__setattr__(self, "timestamp", _ensure_aware_dt(self.timestamp))
        if not self.event_id:
            ts_str = self.timestamp.isoformat()
            seed = f"{self.alert_type}:{self.symbol}:{self.price}:{ts_str}"
            eid = (
                f"alert.triggered-{self.symbol}-"
                f"{hashlib.sha256(seed.encode()).hexdigest()[:12]}"
            )
            object.__setattr__(self, "event_id", eid)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "alert_type": self.alert_type,
            "symbol": self.symbol,
            "price": float(self.price),
            "stop_loss": float(self.stop_loss)
            if self.stop_loss is not None
            else None,
            "target": float(self.target) if self.target is not None else None,
            "decision_id": self.decision_id,
            "provenance": self.provenance,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AlertEvent":
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            event_id=data.get("event_id", ""),
            alert_type=data.get("alert_type", "GENERIC_ALERT"),
            symbol=data["symbol"],
            price=float(data["price"]),
            stop_loss=float(data["stop_loss"])
            if data.get("stop_loss") is not None
            else None,
            target=float(data["target"])
            if data.get("target") is not None
            else None,
            decision_id=data.get("decision_id"),
            provenance=data.get("provenance", {}),
            timestamp=_parse_dt(data.get("timestamp")),
        )
