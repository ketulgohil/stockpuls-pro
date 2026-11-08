"""trader_core.candle - Candle Validation & Integrity Engine for Indian Equities (NSE/BSE).

Direct port of trader_core/candle.py from Indian Day Trader.
"""

from dataclasses import dataclass
import datetime
from decimal import Decimal
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Tuple, Union

from .calendar import IST, parse_ist_timestamp

CORROBORATED_HALT_STATUSES = {
    "HALT",
    "SUSPENDED",
    "CIRCUIT_HALT",
    "TRADING_HALT",
    "EXCHANGE_HALT",
}


class CandleQualityState(Enum):
    VALID = "VALID"
    FORMING = "FORMING"
    INVALID_DIMENSIONS = "INVALID_DIMENSIONS"
    INVALID_BOUNDARIES = "INVALID_BOUNDARIES"
    INVALID_VOLUME = "INVALID_VOLUME"
    MISALIGNED_TIMESTAMP = "MISALIGNED_TIMESTAMP"
    ZERO_VOLUME_WARNING = "ZERO_VOLUME_WARNING"
    DATA_GAP_OR_HALT = "DATA_GAP_OR_HALT"


@dataclass
class Candle:
    """Standardized representation of a single price candle."""

    timestamp: datetime.datetime
    open: Union[Decimal, float]
    high: Union[Decimal, float]
    low: Union[Decimal, float]
    close: Union[Decimal, float]
    volume: Union[int, float, Decimal]
    is_complete: bool = True

    @property
    def range(self) -> Union[Decimal, float]:
        return self.high - self.low

    @property
    def body(self) -> Union[Decimal, float]:
        return abs(self.close - self.open)

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.open > self.close

    def to_dict(self) -> Dict[str, Any]:
        vol = self.volume
        if isinstance(vol, (int, float, Decimal)):
            try:
                vol_out = int(vol) if vol == int(vol) else float(vol)
            except Exception:
                vol_out = float(vol)
        else:
            vol_out = str(vol)
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": str(self.open) if isinstance(self.open, Decimal) else self.open,
            "high": str(self.high) if isinstance(self.high, Decimal) else self.high,
            "low": str(self.low) if isinstance(self.low, Decimal) else self.low,
            "close": str(self.close) if isinstance(self.close, Decimal) else self.close,
            "volume": vol_out,
            "is_complete": bool(self.is_complete),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], use_decimal: bool = False) -> "Candle":
        return normalize_candle(data, use_decimal=use_decimal)


def _to_decimal(val: Any) -> Decimal:
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def _is_finite_number(val: Any) -> bool:
    if isinstance(val, bool):
        return False
    if isinstance(val, int):
        return True
    if isinstance(val, float):
        return math.isfinite(val)
    if isinstance(val, Decimal):
        return not (val.is_nan() or val.is_infinite())
    return False


def validate_candle(
    c: Candle,
    current_time: Optional[datetime.datetime] = None,
    interval_seconds: int = 300,
    require_complete: bool = True,
    allow_zero_volume: bool = True,
    validate_alignment: bool = True,
) -> Tuple[bool, Optional[str]]:
    """Validate mathematical boundaries, positive dimensions, completion and alignment."""
    if not isinstance(c, Candle):
        return False, "INVALID_TYPE: Expected Candle instance"

    ts = c.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=IST)
    else:
        ts = ts.astimezone(IST)

    for name, val in [("open", c.open), ("high", c.high), ("low", c.low), ("close", c.close)]:
        if not _is_finite_number(val):
            return False, f"INVALID_DIMENSIONS: Price {name} must be a finite number"
        if val <= 0:
            return False, f"INVALID_DIMENSIONS: Price {name} ({val}) must be strictly positive"

    o_dec = _to_decimal(c.open)
    h_dec = _to_decimal(c.high)
    l_dec = _to_decimal(c.low)
    c_dec = _to_decimal(c.close)

    if h_dec < l_dec:
        return False, f"INVALID_BOUNDARIES: High ({c.high}) cannot be less than Low ({c.low})"
    if h_dec < o_dec or h_dec < c_dec:
        return False, f"INVALID_BOUNDARIES: High ({c.high}) must be >= max(open, close)"
    if l_dec > o_dec or l_dec > c_dec:
        return False, f"INVALID_BOUNDARIES: Low ({c.low}) must be <= min(open, close)"

    if not _is_finite_number(c.volume):
        return False, "INVALID_VOLUME: Volume must be a finite number"
    if c.volume < 0:
        return False, f"INVALID_VOLUME: Volume ({c.volume}) cannot be negative"
    if not allow_zero_volume and c.volume == 0:
        return False, "ZERO_VOLUME: Candle volume is zero"

    if validate_alignment:
        if ts.second != 0 or ts.microsecond != 0:
            return False, f"MISALIGNED_TIMESTAMP: Timestamp {ts} has non-zero second or microsecond"
        interval_minutes = interval_seconds // 60
        if interval_minutes == 30:
            if ts.minute not in (15, 45):
                return False, f"MISALIGNED_TIMESTAMP: Timestamp {ts} not aligned to Indian 30-minute session boundary (:15 or :45)"
        elif interval_minutes == 60:
            if ts.minute != 15:
                return False, f"MISALIGNED_TIMESTAMP: Timestamp {ts} not aligned to Indian 60-minute session boundary (:15)"
        elif interval_minutes == 45:
            if ts.minute not in (0, 15, 30, 45):
                return False, f"MISALIGNED_TIMESTAMP: Timestamp {ts} not aligned to 45-minute session boundary"
        elif interval_minutes in (1, 5, 15):
            if ts.minute % interval_minutes != 0:
                return False, f"MISALIGNED_TIMESTAMP: Timestamp {ts} not aligned to {interval_minutes}-minute boundary"

    if not isinstance(c.is_complete, bool):
        return False, "INVALID_TYPE: is_complete must be a boolean"

    if require_complete and not c.is_complete:
        return False, "FORMING_CANDLE: Candle is incomplete / forming"

    if current_time is not None:
        curr_ist = (
            current_time.replace(tzinfo=IST)
            if current_time.tzinfo is None
            else current_time.astimezone(IST)
        )
        bar_end = ts + datetime.timedelta(seconds=interval_seconds)
        if require_complete and bar_end > curr_ist:
            return (
                False,
                f"FORMING_CANDLE: Interval [{ts} - {bar_end}] has not elapsed as of {curr_ist}",
            )

    return True, None


def validate_session_bars(
    bars: List[Candle],
    expected_count: int,
    allow_zero_volume: bool = True,
    session_start: Optional[datetime.datetime] = None,
    interval_seconds: int = 300,
    market_status: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """Validate sequence continuity, count, and integrity of a session bar series."""
    if not isinstance(bars, (list, tuple)):
        return False, "INVALID_TYPE: bars must be a list or tuple"
    if len(bars) != expected_count:
        return False, f"COUNT_MISMATCH: Expected {expected_count} bars, got {len(bars)}"
    if expected_count == 0:
        return True, None

    for i, bar in enumerate(bars):
        valid, err = validate_candle(
            bar,
            interval_seconds=interval_seconds,
            require_complete=True,
            allow_zero_volume=True,
        )
        if not valid:
            return False, f"INVALID_CANDLE at index {i}: {err}"

    bar_timestamps: List[datetime.datetime] = []
    for bar in bars:
        ts = bar.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=IST)
        else:
            ts = ts.astimezone(IST)
        bar_timestamps.append(ts)

    if session_start is not None:
        start_ist = (
            session_start.replace(tzinfo=IST)
            if session_start.tzinfo is None
            else session_start.astimezone(IST)
        )
        if bar_timestamps[0] != start_ist:
            return (
                False,
                f"DATA_GAP_OR_HALT: First bar timestamp {bar_timestamps[0]} does not match expected session start {start_ist}",
            )

    for i in range(1, len(bars)):
        prev_ts = bar_timestamps[i - 1]
        curr_ts = bar_timestamps[i]
        if curr_ts == prev_ts:
            return False, f"DUPLICATE_BAR: Duplicate candle timestamp at index {i}: {curr_ts}"
        if curr_ts < prev_ts:
            return False, f"OUT_OF_ORDER: Candle at index {i} ({curr_ts}) precedes index {i - 1} ({prev_ts})"

    for i in range(1, len(bars)):
        prev_ts = bar_timestamps[i - 1]
        curr_ts = bar_timestamps[i]
        delta = (curr_ts - prev_ts).total_seconds()
        if delta != interval_seconds:
            return (
                False,
                f"DATA_GAP_OR_HALT: Gap detected between index {i - 1} ({prev_ts}) and index {i} ({curr_ts}): "
                f"delta is {int(delta)}s, expected {interval_seconds}s",
            )

    if not allow_zero_volume:
        is_corroborated_halt = (
            market_status is not None
            and market_status.upper() in CORROBORATED_HALT_STATUSES
        )
        if not is_corroborated_halt:
            for i, bar in enumerate(bars):
                if bar.volume <= 0:
                    return (
                        False,
                        f"DATA_GAP_OR_HALT: Uncorroborated zero volume at index {i} ({bar.timestamp})",
                    )

    return True, None


def check_zero_volume_bars(bars: List[Candle]) -> List[int]:
    return [i for i, b in enumerate(bars) if b.volume == 0]


def get_candle_quality_state(
    c: Candle,
    require_complete: bool = True,
    interval_seconds: int = 300,
    current_time: Optional[datetime.datetime] = None,
) -> CandleQualityState:
    if not isinstance(c, Candle):
        return CandleQualityState.INVALID_DIMENSIONS
    if not _is_finite_number(c.volume) or c.volume < 0:
        return CandleQualityState.INVALID_VOLUME
    for val in [c.open, c.high, c.low, c.close]:
        if not _is_finite_number(val) or val <= 0:
            return CandleQualityState.INVALID_DIMENSIONS
    o_dec = _to_decimal(c.open)
    h_dec = _to_decimal(c.high)
    l_dec = _to_decimal(c.low)
    c_dec = _to_decimal(c.close)
    if h_dec < l_dec or h_dec < o_dec or h_dec < c_dec or l_dec > o_dec or l_dec > c_dec:
        return CandleQualityState.INVALID_BOUNDARIES
    ts = c.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=IST)
    else:
        ts = ts.astimezone(IST)
    interval_minutes = interval_seconds // 60
    if ts.second != 0 or ts.microsecond != 0 or (interval_minutes > 0 and ts.minute % interval_minutes != 0):
        return CandleQualityState.MISALIGNED_TIMESTAMP
    if not c.is_complete:
        return CandleQualityState.FORMING
    if current_time is not None:
        curr_ist = current_time.replace(tzinfo=IST) if current_time.tzinfo is None else current_time.astimezone(IST)
        if ts + datetime.timedelta(seconds=interval_seconds) > curr_ist:
            return CandleQualityState.FORMING
    if c.volume == 0:
        return CandleQualityState.ZERO_VOLUME_WARNING
    return CandleQualityState.VALID


def normalize_candle(
    data: Union[Candle, Dict[str, Any]],
    use_decimal: bool = True,
) -> Candle:
    if isinstance(data, Candle):
        ts = data.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=IST)
        else:
            ts = ts.astimezone(IST)
        if use_decimal:
            o_val = _to_decimal(data.open)
            h_val = _to_decimal(data.high)
            l_val = _to_decimal(data.low)
            c_val = _to_decimal(data.close)
            vol_val = _to_decimal(data.volume)
        else:
            o_val = float(data.open)
            h_val = float(data.high)
            l_val = float(data.low)
            c_val = float(data.close)
            vol_val = float(data.volume)
        return Candle(
            timestamp=ts,
            open=o_val,
            high=h_val,
            low=l_val,
            close=c_val,
            volume=vol_val,
            is_complete=bool(data.is_complete),
        )

    raw_ts = data["timestamp"]
    if isinstance(raw_ts, datetime.datetime):
        ts = raw_ts.replace(tzinfo=IST) if raw_ts.tzinfo is None else raw_ts.astimezone(IST)
    else:
        ts = parse_ist_timestamp(raw_ts)

    if use_decimal:
        open_val = _to_decimal(data["open"])
        high_val = _to_decimal(data["high"])
        low_val = _to_decimal(data["low"])
        close_val = _to_decimal(data["close"])
        vol_raw = data.get("volume", 0)
        volume_val = _to_decimal(vol_raw)
    else:
        open_val = float(data["open"])
        high_val = float(data["high"])
        low_val = float(data["low"])
        close_val = float(data["close"])
        volume_val = float(data.get("volume", 0))

    is_complete = bool(data.get("is_complete", True))

    return Candle(
        timestamp=ts,
        open=open_val,
        high=high_val,
        low=low_val,
        close=close_val,
        volume=volume_val,
        is_complete=is_complete,
    )
