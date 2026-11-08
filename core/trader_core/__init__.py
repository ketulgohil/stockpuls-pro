"""trader_core - Indian Day Trader core library ported into StockPulse Pro.

Pure standard-library components adapted to run on top of StockPulse Pro's
existing Upstox data layer (core.upstox_data). Enforces Decimal monetary
arithmetic, IST session boundaries, fail-closed fee schedules, and no
automated broker execution.
"""

from __future__ import annotations

from .calendar import (  # noqa: F401
    IST,
    REGULAR_SESSION_START_HOUR,
    REGULAR_SESSION_START_MINUTE,
    REGULAR_SESSION_END_HOUR,
    REGULAR_SESSION_END_MINUTE,
    TOTAL_REGULAR_BARS,
    BAR_DURATION_MINUTES,
    ExchangeCalendar,
    CalendarMetadata,
    SpecialSession,
    get_default_calendar,
    get_session_phase,
    get_expected_bars_count,
    is_trading_day,
    parse_ist_timestamp,
)
from .costs import (  # noqa: F401
    calculate_intraday_costs,
    CostBreakdown,
    CostError,
    FeeScheduleError,
    FeeScheduleNotFoundError,
    FeeScheduleExpiredError,
    FeeScheduleStaleError,
    BrokerTariffNotFoundError,
    ExchangeNotSupportedError,
    SegmentNotSupportedError,
    InvalidCostInputError,
)
from .candle import (  # noqa: F401
    Candle,
    CandleQualityState,
    validate_candle,
    validate_session_bars,
    normalize_candle,
    check_zero_volume_bars,
    get_candle_quality_state,
)

__all__ = [
    "IST",
    "calculate_intraday_costs",
    "CostBreakdown",
    "validate_candle",
    "Candle",
    "get_default_calendar",
    "get_session_phase",
    "parse_ist_timestamp",
]
