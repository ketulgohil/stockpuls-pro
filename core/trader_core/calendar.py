"""trader_core.calendar - Exchange Calendar and IST Utilities.

Direct port of trader_core/calendar.py from Indian Day Trader, adapted to
run standalone within StockPulse Pro.
"""

import datetime
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union

# Indian Standard Time (UTC+05:30)
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IST")

# Regular trading session bounds (IST)
REGULAR_SESSION_START_HOUR = 9
REGULAR_SESSION_START_MINUTE = 15
REGULAR_SESSION_END_HOUR = 15
REGULAR_SESSION_END_MINUTE = 30
BAR_DURATION_MINUTES = 5
TOTAL_REGULAR_BARS = 75  # (375 minutes / 5 minutes)


class CalendarError(Exception):
    """Base error for calendar operations."""


class CalendarDataError(CalendarError):
    """Raised when calendar payload is corrupted, tampered, or malformed."""


class CalendarExpiredError(CalendarError):
    """Raised when calendar data is expired or queried outside its effective window."""


class SpecialSession:
    """Special trading session definition (e.g., Diwali Muhurat Trading)."""

    def __init__(
        self,
        date: str,
        name: str,
        start_time: str,
        end_time: str,
        phase_name: str = "muhurat",
        description: str = "",
    ):
        self.date = date  # YYYY-MM-DD
        self.name = name
        self.start_time = start_time  # HH:MM:SS
        self.end_time = end_time  # HH:MM:SS
        self.phase_name = phase_name
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "phase_name": self.phase_name,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpecialSession":
        return cls(
            date=str(data["date"]),
            name=str(data["name"]),
            start_time=str(data["start_time"]),
            end_time=str(data["end_time"]),
            phase_name=str(data.get("phase_name", "muhurat")),
            description=str(data.get("description", "")),
        )


class CalendarMetadata:
    """Versioned source metadata and cryptographic checksum for an exchange calendar."""

    def __init__(
        self,
        source_url: str,
        retrieval_date: str,
        effective_date: str,
        expiry_date: str,
        checksum: str = "",
        version: str = "1.0.0",
    ):
        self.source_url = source_url
        self.retrieval_date = retrieval_date
        self.effective_date = effective_date
        self.expiry_date = expiry_date
        self.checksum = checksum
        self.version = version

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_url": self.source_url,
            "retrieval_date": self.retrieval_date,
            "effective_date": self.effective_date,
            "expiry_date": self.expiry_date,
            "checksum": self.checksum,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalendarMetadata":
        return cls(
            source_url=str(data["source_url"]),
            retrieval_date=str(data["retrieval_date"]),
            effective_date=str(data["effective_date"]),
            expiry_date=str(data["expiry_date"]),
            checksum=str(data.get("checksum", "")),
            version=str(data.get("version", "1.0.0")),
        )


class ExchangeCalendar:
    """Exchange trading calendar with versioned metadata, holidays, and special sessions."""

    def __init__(
        self,
        metadata: CalendarMetadata,
        holidays: Dict[str, str],
        special_sessions: Optional[Dict[str, SpecialSession]] = None,
        segment: str = "EQUITY",
        exchange: str = "NSE",
    ):
        self.metadata = metadata
        self.holidays = holidays  # "YYYY-MM-DD" -> "Holiday Name"
        self.special_sessions = special_sessions or {}
        self.segment = segment
        self.exchange = exchange

    def compute_checksum(self) -> str:
        payload = {
            "segment": self.segment,
            "exchange": self.exchange,
            "metadata": {
                "source_url": self.metadata.source_url,
                "retrieval_date": self.metadata.retrieval_date,
                "effective_date": self.metadata.effective_date,
                "version": self.metadata.version,
            },
            "holidays": self.holidays,
            "special_sessions": {
                k: v.to_dict() for k, v in sorted(self.special_sessions.items())
            },
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def verify_checksum(self) -> bool:
        if not self.metadata.checksum:
            return False
        return self.compute_checksum() == self.metadata.checksum

    def is_expired(self, as_of: Optional[datetime.date] = None) -> bool:
        ref_date = as_of or datetime.date.today()
        expiry = datetime.date.fromisoformat(self.metadata.expiry_date)
        return ref_date > expiry

    def check_valid_for_date(self, target_date: datetime.date) -> None:
        effective = datetime.date.fromisoformat(self.metadata.effective_date)
        expiry = datetime.date.fromisoformat(self.metadata.expiry_date)
        if target_date < effective or target_date > expiry:
            raise CalendarExpiredError(
                "Calendar not valid for date %s (effective: %s to %s)"
                % (target_date.isoformat(), self.metadata.effective_date, self.metadata.expiry_date)
            )

    def is_regular_trading_day(self, dt: Union[datetime.date, datetime.datetime]) -> bool:
        if isinstance(dt, datetime.datetime):
            date_val = dt.astimezone(IST).date() if dt.tzinfo else dt.date()
        else:
            date_val = dt
        if date_val.weekday() >= 5:
            return False
        if date_val.isoformat() in self.holidays:
            return False
        return True

    def is_trading_day(self, dt: Union[datetime.date, datetime.datetime]) -> bool:
        if isinstance(dt, datetime.datetime):
            date_val = dt.astimezone(IST).date() if dt.tzinfo else dt.date()
        else:
            date_val = dt
        date_str = date_val.isoformat()
        if date_str in self.special_sessions:
            return True
        return self.is_regular_trading_day(date_val)

    def get_session_phase(self, dt: datetime.datetime) -> str:
        if dt.tzinfo is None:
            ist_dt = dt.replace(tzinfo=IST)
        else:
            ist_dt = dt.astimezone(IST)
        date_val = ist_dt.date()
        date_str = date_val.isoformat()
        time_val = ist_dt.time()

        if date_str in self.special_sessions:
            session = self.special_sessions[date_str]
            st = datetime.time.fromisoformat(session.start_time)
            et = datetime.time.fromisoformat(session.end_time)
            if st <= time_val < et:
                return session.phase_name
            if not self.is_regular_trading_day(date_val):
                return "closed"

        if not self.is_regular_trading_day(date_val):
            return "closed"

        t_pre_open_start = datetime.time(9, 0, 0)
        t_market_open = datetime.time(9, 15, 0)
        t_orb_end = datetime.time(9, 30, 0)
        t_pre_close_start = datetime.time(15, 0, 0)
        t_market_close = datetime.time(15, 30, 0)

        if t_pre_open_start <= time_val < t_market_open:
            return "pre-open"
        elif t_market_open <= time_val < t_orb_end:
            return "orb"
        elif t_orb_end <= time_val < t_pre_close_start:
            return "active"
        elif t_pre_close_start <= time_val < t_market_close:
            return "pre-close"
        else:
            return "closed"

    def get_expected_bars_count(self, current_time: datetime.datetime) -> int:
        if current_time.tzinfo is None:
            ist_dt = current_time.replace(tzinfo=IST)
        else:
            ist_dt = current_time.astimezone(IST)
        date_val = ist_dt.date()
        if not self.is_regular_trading_day(date_val):
            return 0
        session_open = datetime.datetime(
            date_val.year, date_val.month, date_val.day,
            REGULAR_SESSION_START_HOUR, REGULAR_SESSION_START_MINUTE, 0, tzinfo=IST,
        )
        if ist_dt < session_open:
            return 0
        elapsed_seconds = (ist_dt - session_open).total_seconds()
        completed_bars = int(elapsed_seconds // (BAR_DURATION_MINUTES * 60))
        if completed_bars < 0:
            return 0
        if completed_bars > TOTAL_REGULAR_BARS:
            return TOTAL_REGULAR_BARS
        return completed_bars

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange,
            "segment": self.segment,
            "metadata": self.metadata.to_dict(),
            "holidays": self.holidays,
            "special_sessions": {k: v.to_dict() for k, v in self.special_sessions.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExchangeCalendar":
        metadata = CalendarMetadata.from_dict(data["metadata"])
        holidays = {str(k): str(v) for k, v in data.get("holidays", {}).items()}
        special_sessions = {
            str(k): SpecialSession.from_dict(v)
            for k, v in data.get("special_sessions", {}).items()
        }
        cal = cls(
            metadata=metadata,
            holidays=holidays,
            special_sessions=special_sessions,
            segment=str(data.get("segment", "EQUITY")),
            exchange=str(data.get("exchange", "NSE")),
        )
        if not cal.verify_checksum():
            raise CalendarDataError(
                "Calendar checksum verification failed. Data may be corrupted or tampered."
            )
        return cal

    @classmethod
    def load_default(cls) -> "ExchangeCalendar":
        metadata = CalendarMetadata(
            source_url="https://www.nseindia.com/resources/exchange-communication-holidays?apiversion=v2",
            retrieval_date="2026-10-30",
            effective_date="2026-01-01",
            expiry_date="2026-12-31",
            version="1.0.0",
        )
        holidays = {
            "2026-01-26": "Republic Day",
            "2026-03-03": "Holi",
            "2026-03-20": "Id-Ul-Fitr",
            "2026-03-27": "Ram Navami",
            "2026-04-03": "Good Friday",
            "2026-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
            "2026-05-01": "Maharashtra Day",
            "2026-05-27": "Bakri Id",
            "2026-08-15": "Independence Day",
            "2026-09-04": "Milad-un-Nabi",
            "2026-10-02": "Mahatma Gandhi Jayanti",
            "2026-10-20": "Dussehra",
            "2026-11-10": "Diwali Balipratipada",
            "2026-11-24": "Gurunanak Jayanti",
            "2026-12-25": "Christmas",
        }
        muhurat = SpecialSession(
            date="2026-11-08",
            name="Diwali Muhurat Trading",
            start_time="18:15:00",
            end_time="19:15:00",
            phase_name="muhurat",
            description="Diwali Laxmi Pujan 1-hour special evening trading session",
        )
        special_sessions = {"2026-11-08": muhurat}
        cal = cls(
            metadata=metadata,
            holidays=holidays,
            special_sessions=special_sessions,
            segment="EQUITY",
            exchange="NSE",
        )
        cal.metadata.checksum = cal.compute_checksum()
        return cal


_DEFAULT_CALENDAR: Optional[ExchangeCalendar] = None


def get_default_calendar() -> ExchangeCalendar:
    global _DEFAULT_CALENDAR
    if _DEFAULT_CALENDAR is None:
        _DEFAULT_CALENDAR = ExchangeCalendar.load_default()
    return _DEFAULT_CALENDAR


def is_trading_day(
    dt: Union[datetime.date, datetime.datetime],
    calendar: Optional[ExchangeCalendar] = None,
) -> bool:
    cal = calendar or get_default_calendar()
    return cal.is_trading_day(dt)


def get_session_phase(
    dt: datetime.datetime,
    calendar: Optional[ExchangeCalendar] = None,
) -> str:
    cal = calendar or get_default_calendar()
    return cal.get_session_phase(dt)


def get_expected_bars_count(
    current_time: datetime.datetime,
    calendar: Optional[ExchangeCalendar] = None,
) -> int:
    cal = calendar or get_default_calendar()
    return cal.get_expected_bars_count(current_time)


def get_bar_slot(dt: datetime.datetime) -> int:
    if dt.tzinfo is None:
        ist_dt = dt.replace(tzinfo=IST)
    else:
        ist_dt = dt.astimezone(IST)
    date_val = ist_dt.date()
    start_time = datetime.datetime(
        date_val.year, date_val.month, date_val.day,
        REGULAR_SESSION_START_HOUR, REGULAR_SESSION_START_MINUTE, 0, tzinfo=IST,
    )
    end_time = datetime.datetime(
        date_val.year, date_val.month, date_val.day,
        REGULAR_SESSION_END_HOUR, REGULAR_SESSION_END_MINUTE, 0, tzinfo=IST,
    )
    if ist_dt < start_time or ist_dt >= end_time:
        return -1
    elapsed_minutes = (ist_dt - start_time).total_seconds() / 60.0
    slot = int(elapsed_minutes // BAR_DURATION_MINUTES)
    if 0 <= slot < TOTAL_REGULAR_BARS:
        return slot
    return -1


def get_bar_start_time(slot_index: int, day: datetime.date) -> datetime.datetime:
    if not (0 <= slot_index < TOTAL_REGULAR_BARS):
        raise ValueError(
            "Bar slot index %d out of valid session range [0..%d]"
            % (slot_index, TOTAL_REGULAR_BARS - 1)
        )
    return datetime.datetime(
        day.year, day.month, day.day,
        REGULAR_SESSION_START_HOUR, REGULAR_SESSION_START_MINUTE, 0, tzinfo=IST,
    ) + datetime.timedelta(minutes=slot_index * BAR_DURATION_MINUTES)


def get_bar_end_time(slot_index: int, day: datetime.date) -> datetime.datetime:
    if not (0 <= slot_index < TOTAL_REGULAR_BARS):
        raise ValueError(
            "Bar slot index %d out of valid session range [0..%d]"
            % (slot_index, TOTAL_REGULAR_BARS - 1)
        )
    return get_bar_start_time(slot_index, day) + datetime.timedelta(minutes=BAR_DURATION_MINUTES)


def parse_ist_timestamp(
    ts: Union[int, float, str],
    unit: Optional[str] = None,
) -> datetime.datetime:
    if isinstance(ts, bool):
        raise ValueError("Boolean value is not a valid timestamp: %r" % ts)
    if isinstance(ts, str):
        cleaned = ts.strip()
        if not cleaned:
            raise ValueError("Timestamp string cannot be empty")
        if re.match(r"^-?\d+(\.\d+)?$", cleaned):
            num_val = float(cleaned) if "." in cleaned else int(cleaned)
            return parse_ist_timestamp(num_val, unit=unit)
        if re.match(r"^\d{4}-\d{2}-\d{2}$", cleaned):
            raise ValueError("Date-only string is ambiguous as an intraday timestamp: %s" % cleaned)
        if "/" in cleaned:
            raise ValueError("Ambiguous non-ISO date format rejected: %s" % cleaned)
        iso_str = cleaned.replace(" ", "T") if " " in cleaned else cleaned
        if iso_str.endswith("Z"):
            iso_str = iso_str[:-1] + "+00:00"
        try:
            dt = datetime.datetime.fromisoformat(iso_str)
        except Exception as e:
            raise ValueError("Unable to parse ISO timestamp '%s': %s" % (cleaned, e))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=IST)
        return dt.astimezone(IST)
    if not isinstance(ts, (int, float)):
        raise ValueError("Unsupported timestamp type: %s" % type(ts))
    if ts < 0:
        raise ValueError("Timestamp cannot be negative: %r" % ts)
    if unit is not None:
        unit_lower = unit.lower()
        if unit_lower == "s":
            seconds = float(ts)
        elif unit_lower == "ms":
            seconds = float(ts) / 1e3
        elif unit_lower == "us":
            seconds = float(ts) / 1e6
        elif unit_lower == "ns":
            seconds = float(ts) / 1e9
        else:
            raise ValueError("Unsupported timestamp unit '%s'. Allowed: s, ms, us, ns" % unit)
    else:
        if 946684800 <= ts <= 3000000000:
            seconds = float(ts)
        elif 946684800 * 1e3 <= ts <= 3000000000 * 1e3:
            seconds = float(ts) / 1e3
        elif 946684800 * 1e6 <= ts <= 3000000000 * 1e6:
            seconds = float(ts) / 1e6
        elif 946684800 * 1e9 <= ts <= 3000000000 * 1e9:
            seconds = float(ts) / 1e9
        else:
            raise ValueError(
                "Ambiguous numeric timestamp %r outside recognized epoch ranges; "
                "specify explicit unit ('s', 'ms', 'us', 'ns')" % ts
            )
    utc_dt = datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc)
    return utc_dt.astimezone(IST)
