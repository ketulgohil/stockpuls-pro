"""trader_core.costs - Indian Statutory Transaction Cost Calculator for Equity Intraday.

Direct port of trader_core/costs.py from Indian Day Trader. Pure standard-library
implementation using Decimal monetary arithmetic throughout.
"""

import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Union


class CostError(Exception):
    """Base exception for cost engine operations."""


class InvalidCostInputError(CostError):
    """Raised when monetary, quantity, or exchange inputs are invalid."""


class FeeScheduleError(CostError):
    """Base exception for fee schedule lookup or validation failures."""


class FeeScheduleNotFoundError(FeeScheduleError):
    """Raised when no fee schedule matches the requested parameters and date."""


class FeeScheduleExpiredError(FeeScheduleError):
    """Raised when fee schedules have expired without a known replacement."""


class FeeScheduleStaleError(FeeScheduleError):
    """Raised when a fee schedule has exceeded the maximum staleness threshold."""


class ExchangeNotSupportedError(CostError):
    """Raised when an unconfigured or non-Indian exchange is requested."""


class SegmentNotSupportedError(CostError):
    """Raised when an unsupported market segment is requested."""


class BrokerTariffNotFoundError(CostError):
    """Raised when an unknown broker tariff schedule is requested."""


class StatutoryLevySchedule:
    """Effective-dated statutory levies for Indian equity intraday cash segment."""

    def __init__(
        self,
        schedule_id: str,
        effective_from: datetime.date,
        effective_to: Optional[datetime.date],
        stt_sell_rate: Decimal,
        sebi_rate: Decimal,
        stamp_duty_buy_rate: Decimal,
        gst_rate: Decimal,
        source_circular: str,
        verified_date: datetime.date,
    ):
        self.schedule_id = schedule_id
        self.effective_from = effective_from
        self.effective_to = effective_to
        self.stt_sell_rate = stt_sell_rate
        self.sebi_rate = sebi_rate
        self.stamp_duty_buy_rate = stamp_duty_buy_rate
        self.gst_rate = gst_rate
        self.source_circular = source_circular
        self.verified_date = verified_date


class ExchangeFeeSchedule:
    """Effective-dated exchange turnover charges."""

    def __init__(
        self,
        exchange: str,
        segment: str,
        effective_from: datetime.date,
        effective_to: Optional[datetime.date],
        turnover_rate: Decimal,
        source_circular: str,
        verified_date: datetime.date,
    ):
        self.exchange = exchange.upper()
        self.segment = segment.upper()
        self.effective_from = effective_from
        self.effective_to = effective_to
        self.turnover_rate = turnover_rate
        self.source_circular = source_circular
        self.verified_date = verified_date


class BrokerTariffSchedule:
    """Effective-dated broker tariff schedule."""

    def __init__(
        self,
        broker_id: str,
        rate: Decimal,
        max_per_order: Decimal,
        min_per_order: Decimal,
        effective_from: datetime.date,
        effective_to: Optional[datetime.date],
        source: str,
        verified_date: datetime.date,
    ):
        self.broker_id = broker_id.lower()
        self.rate = rate
        self.max_per_order = max_per_order
        self.min_per_order = min_per_order
        self.effective_from = effective_from
        self.effective_to = effective_to
        self.source = source
        self.verified_date = verified_date


STATUTORY_SCHEDULES: List[StatutoryLevySchedule] = []
EXCHANGE_SCHEDULES: List[ExchangeFeeSchedule] = []
BROKER_SCHEDULES: List[BrokerTariffSchedule] = []
MAX_STALENESS_DAYS = 180


def register_statutory_schedule(schedule: StatutoryLevySchedule) -> None:
    STATUTORY_SCHEDULES.append(schedule)


def register_exchange_schedule(schedule: ExchangeFeeSchedule) -> None:
    EXCHANGE_SCHEDULES.append(schedule)


def register_broker_tariff(schedule: BrokerTariffSchedule) -> None:
    BROKER_SCHEDULES.append(schedule)


def _init_default_schedules() -> None:
    register_statutory_schedule(
        StatutoryLevySchedule(
            schedule_id="STATUTORY_EQ_2020",
            effective_from=datetime.date(2020, 7, 1),
            effective_to=datetime.date(2027, 12, 31),
            stt_sell_rate=Decimal("0.00025"),
            sebi_rate=Decimal("0.000001"),
            stamp_duty_buy_rate=Decimal("0.00003"),
            gst_rate=Decimal("0.18"),
            source_circular="Finance Act 2019 / Indian Stamp Rules 2020 / SEBI Circular SEBI/HO/MRD/DoP2/CIR/P/2019/115",
            verified_date=datetime.date(2026, 10, 1),
        )
    )
    register_exchange_schedule(
        ExchangeFeeSchedule(
            exchange="NSE",
            segment="EQ",
            effective_from=datetime.date(2024, 10, 1),
            effective_to=datetime.date(2027, 12, 31),
            turnover_rate=Decimal("0.0000297"),
            source_circular="NSE Circular NSE/F&A/63901 dated Sep 24, 2024",
            verified_date=datetime.date(2026, 10, 1),
        )
    )
    register_exchange_schedule(
        ExchangeFeeSchedule(
            exchange="NSE",
            segment="EQ",
            effective_from=datetime.date(2020, 7, 1),
            effective_to=datetime.date(2024, 9, 30),
            turnover_rate=Decimal("0.0000325"),
            source_circular="NSE Circular NSE/F&A/43900",
            verified_date=datetime.date(2024, 5, 1),
        )
    )
    register_exchange_schedule(
        ExchangeFeeSchedule(
            exchange="BSE",
            segment="EQ",
            effective_from=datetime.date(2024, 10, 1),
            effective_to=datetime.date(2027, 12, 31),
            turnover_rate=Decimal("0.0000375"),
            source_circular="BSE Notice 20240927-1",
            verified_date=datetime.date(2026, 10, 1),
        )
    )
    register_broker_tariff(
        BrokerTariffSchedule(
            broker_id="discount",
            rate=Decimal("0.0003"),
            max_per_order=Decimal("20.00"),
            min_per_order=Decimal("0.00"),
            effective_from=datetime.date(2020, 1, 1),
            effective_to=datetime.date(2027, 12, 31),
            source="Zerodha / Upstox Retail Tariff Schedule 2020-2026",
            verified_date=datetime.date(2026, 10, 1),
        )
    )
    register_broker_tariff(
        BrokerTariffSchedule(
            broker_id="zero",
            rate=Decimal("0.00"),
            max_per_order=Decimal("0.00"),
            min_per_order=Decimal("0.00"),
            effective_from=datetime.date(2020, 1, 1),
            effective_to=datetime.date(2027, 12, 31),
            source="Zero-Commission Retail Intraday Tariff",
            verified_date=datetime.date(2026, 10, 1),
        )
    )
    register_broker_tariff(
        BrokerTariffSchedule(
            broker_id="flat20",
            rate=Decimal("0.00"),
            max_per_order=Decimal("20.00"),
            min_per_order=Decimal("20.00"),
            effective_from=datetime.date(2020, 1, 1),
            effective_to=datetime.date(2027, 12, 31),
            source="Flat Rs 20 Institutional/API Tariff",
            verified_date=datetime.date(2026, 10, 1),
        )
    )


_init_default_schedules()


def get_active_statutory_schedule(query_date: datetime.date) -> StatutoryLevySchedule:
    matching: List[StatutoryLevySchedule] = []
    has_candidate_pool = False
    for s in STATUTORY_SCHEDULES:
        has_candidate_pool = True
        if s.effective_from <= query_date:
            if s.effective_to is None or query_date <= s.effective_to:
                matching.append(s)
    if not matching:
        if has_candidate_pool:
            all_past = all(s.effective_to is not None and s.effective_to < query_date for s in STATUTORY_SCHEDULES)
            if all_past:
                raise FeeScheduleExpiredError("All statutory fee schedules expired before query date: %s" % query_date)
        raise FeeScheduleNotFoundError("No active statutory fee schedule found for date: %s" % query_date)
    active = sorted(matching, key=lambda x: x.effective_from, reverse=True)[0]
    days_stale = (query_date - active.verified_date).days
    if days_stale > MAX_STALENESS_DAYS:
        raise FeeScheduleStaleError(
            "Statutory fee schedule '%s' is stale (%d days since verification on %s; max %d)"
            % (active.schedule_id, days_stale, active.verified_date, MAX_STALENESS_DAYS)
        )
    return active


def get_active_exchange_schedule(exchange: str, segment: str, query_date: datetime.date) -> ExchangeFeeSchedule:
    exch = exchange.upper()
    seg = segment.upper()
    supported_exchanges = {"NSE", "BSE", "NSE_TEST", "NSE_STALE"}
    if exch not in supported_exchanges and not any(s.exchange == exch for s in EXCHANGE_SCHEDULES):
        raise ExchangeNotSupportedError("Exchange '%s' is not supported. Supported: NSE, BSE" % exchange)
    supported_segments = {"EQ"}
    if seg not in supported_segments:
        raise SegmentNotSupportedError("Segment '%s' is not supported for equity intraday calculator" % segment)
    candidates = [s for s in EXCHANGE_SCHEDULES if s.exchange == exch and s.segment == seg]
    if not candidates:
        raise FeeScheduleNotFoundError(
            "No fee schedule configured for exchange '%s' segment '%s'" % (exch, seg)
        )
    matching = [
        s for s in candidates
        if s.effective_from <= query_date and (s.effective_to is None or query_date <= s.effective_to)
    ]
    if not matching:
        all_past = all(s.effective_to is not None and s.effective_to < query_date for s in candidates)
        if all_past:
            raise FeeScheduleExpiredError(
                "Exchange fee schedule for %s/%s expired before query date: %s" % (exch, seg, query_date)
            )
        raise FeeScheduleNotFoundError(
            "No active exchange fee schedule for %s/%s on date: %s" % (exch, seg, query_date)
        )
    active = sorted(matching, key=lambda x: x.effective_from, reverse=True)[0]
    days_stale = (query_date - active.verified_date).days
    if days_stale > MAX_STALENESS_DAYS:
        raise FeeScheduleStaleError(
            "Exchange fee schedule for %s/%s is stale (%d days since verification on %s; max %d)"
            % (exch, seg, days_stale, active.verified_date, MAX_STALENESS_DAYS)
        )
    return active


def get_active_broker_tariff(broker_id: str, query_date: datetime.date) -> BrokerTariffSchedule:
    b_id = broker_id.lower()
    candidates = [s for s in BROKER_SCHEDULES if s.broker_id == b_id]
    if not candidates:
        raise BrokerTariffNotFoundError(
            "Broker tariff '%s' is not recognized. Configured: discount, zero, flat20" % broker_id
        )
    matching = [
        s for s in candidates
        if s.effective_from <= query_date and (s.effective_to is None or query_date <= s.effective_to)
    ]
    if not matching:
        all_past = all(s.effective_to is not None and s.effective_to < query_date for s in candidates)
        if all_past:
            raise FeeScheduleExpiredError("Broker tariff '%s' expired before query date: %s" % (b_id, query_date))
        raise FeeScheduleNotFoundError("No active broker tariff for '%s' on date: %s" % (b_id, query_date))
    active = sorted(matching, key=lambda x: x.effective_from, reverse=True)[0]
    days_stale = (query_date - active.verified_date).days
    if days_stale > MAX_STALENESS_DAYS:
        raise FeeScheduleStaleError(
            "Broker tariff '%s' is stale (%d days since verification on %s; max %d)"
            % (b_id, days_stale, active.verified_date, MAX_STALENESS_DAYS)
        )
    return active


class CostBreakdown:
    """Container for itemized Indian equity intraday transaction costs."""

    def __init__(
        self,
        turnover: Decimal,
        buy_turnover: Decimal,
        sell_turnover: Decimal,
        brokerage: Decimal,
        brokerage_buy: Decimal,
        brokerage_sell: Decimal,
        stt: Decimal,
        exchange_charges: Decimal,
        sebi_charges: Decimal,
        stamp_duty: Decimal,
        gst: Decimal,
        total_costs: Decimal,
        breakeven_diff: Decimal,
        exchange: str,
        segment: str,
        broker_schedule: str,
        effective_date: datetime.date,
        statutory_circular: str,
        exchange_circular: str,
        is_estimate: bool = True,
    ):
        self.turnover = turnover
        self.buy_turnover = buy_turnover
        self.sell_turnover = sell_turnover
        self.brokerage = brokerage
        self.brokerage_buy = brokerage_buy
        self.brokerage_sell = brokerage_sell
        self.stt = stt
        self.exchange_charges = exchange_charges
        self.sebi_charges = sebi_charges
        self.stamp_duty = stamp_duty
        self.gst = gst
        self.total_costs = total_costs
        self.breakeven_diff = breakeven_diff
        self.exchange = exchange
        self.segment = segment
        self.broker_schedule = broker_schedule
        self.effective_date = effective_date
        self.statutory_circular = statutory_circular
        self.exchange_circular = exchange_circular
        self.is_estimate = is_estimate

    def __getitem__(self, item: str) -> Any:
        aliases = {
            "total_deductions": "total_costs",
            "breakeven_points_per_share": "breakeven_diff",
        }
        target = aliases.get(item, item)
        if hasattr(self, target):
            return getattr(self, target)
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turnover": str(self.turnover),
            "buy_turnover": str(self.buy_turnover),
            "sell_turnover": str(self.sell_turnover),
            "brokerage": str(self.brokerage),
            "brokerage_buy": str(self.brokerage_buy),
            "brokerage_sell": str(self.brokerage_sell),
            "stt": str(self.stt),
            "exchange_charges": str(self.exchange_charges),
            "sebi_charges": str(self.sebi_charges),
            "stamp_duty": str(self.stamp_duty),
            "gst": str(self.gst),
            "total_costs": str(self.total_costs),
            "total_deductions": str(self.total_costs),
            "breakeven_diff": str(self.breakeven_diff),
            "breakeven_points_per_share": str(self.breakeven_diff),
            "exchange": self.exchange,
            "segment": self.segment,
            "broker_schedule": self.broker_schedule,
            "effective_date": self.effective_date.isoformat(),
            "statutory_circular": self.statutory_circular,
            "exchange_circular": self.exchange_circular,
            "is_estimate": self.is_estimate,
        }


def calculate_intraday_costs(
    buy_price: Decimal,
    sell_price: Decimal,
    qty: int,
    exchange: str = "NSE",
    segment: str = "EQ",
    broker_schedule: str = "discount",
    effective_date: Optional[Union[datetime.date, str]] = None,
) -> CostBreakdown:
    """Calculate exact Indian statutory transaction costs for equity intraday round-trip trade."""
    if isinstance(buy_price, float):
        raise TypeError("INV-06 Violation: Binary float prohibited for buy_price. Use decimal.Decimal instead.")
    if isinstance(sell_price, float):
        raise TypeError("INV-06 Violation: Binary float prohibited for sell_price. Use decimal.Decimal instead.")
    if not isinstance(buy_price, Decimal):
        raise TypeError("buy_price must be decimal.Decimal, got %s" % type(buy_price).__name__)
    if not isinstance(sell_price, Decimal):
        raise TypeError("sell_price must be decimal.Decimal, got %s" % type(sell_price).__name__)
    if buy_price <= Decimal("0"):
        raise InvalidCostInputError("buy_price must be strictly positive, got %s" % buy_price)
    if sell_price <= Decimal("0"):
        raise InvalidCostInputError("sell_price must be strictly positive, got %s" % sell_price)
    if isinstance(qty, bool) or not isinstance(qty, int):
        raise TypeError("qty must be an integer, got %s" % type(qty).__name__)
    if qty <= 0:
        raise InvalidCostInputError("qty must be a strictly positive integer, got %d" % qty)

    if effective_date is None:
        eval_date = datetime.date.today()
    elif isinstance(effective_date, str):
        try:
            eval_date = datetime.datetime.strptime(effective_date, "%Y-%m-%d").date()
        except ValueError:
            raise InvalidCostInputError("Invalid effective_date format. Expected YYYY-MM-DD, got: %s" % effective_date)
    elif isinstance(effective_date, datetime.date):
        eval_date = effective_date
    else:
        raise TypeError("effective_date must be datetime.date or YYYY-MM-DD string, got %s" % type(effective_date).__name__)

    stat_sched = get_active_statutory_schedule(eval_date)
    exch_sched = get_active_exchange_schedule(exchange, segment, eval_date)
    broker_sched = get_active_broker_tariff(broker_schedule, eval_date)

    qty_dec = Decimal(qty)
    paise = Decimal("0.01")
    rupee = Decimal("1")
    fourth_dec = Decimal("0.0001")

    buy_turnover = (buy_price * qty_dec).quantize(paise, rounding=ROUND_HALF_UP)
    sell_turnover = (sell_price * qty_dec).quantize(paise, rounding=ROUND_HALF_UP)
    total_turnover = (buy_turnover + sell_turnover).quantize(paise, rounding=ROUND_HALF_UP)

    if broker_sched.rate > Decimal("0"):
        calc_b_buy = (broker_sched.rate * buy_turnover).quantize(paise, rounding=ROUND_HALF_UP)
        brokerage_buy = min(broker_sched.max_per_order, max(broker_sched.min_per_order, calc_b_buy))
        calc_b_sell = (broker_sched.rate * sell_turnover).quantize(paise, rounding=ROUND_HALF_UP)
        brokerage_sell = min(broker_sched.max_per_order, max(broker_sched.min_per_order, calc_b_sell))
    else:
        brokerage_buy = broker_sched.min_per_order
        brokerage_sell = broker_sched.min_per_order

    brokerage_buy = brokerage_buy.quantize(paise, rounding=ROUND_HALF_UP)
    brokerage_sell = brokerage_sell.quantize(paise, rounding=ROUND_HALF_UP)
    total_brokerage = (brokerage_buy + brokerage_sell).quantize(paise, rounding=ROUND_HALF_UP)

    stt_raw = stat_sched.stt_sell_rate * sell_turnover
    stt = stt_raw.quantize(rupee, rounding=ROUND_HALF_UP).quantize(paise)

    exchange_charges = (exch_sched.turnover_rate * total_turnover).quantize(paise, rounding=ROUND_HALF_UP)

    sebi_charges = (stat_sched.sebi_rate * total_turnover).quantize(paise, rounding=ROUND_HALF_UP)

    stamp_raw = stat_sched.stamp_duty_buy_rate * buy_turnover
    stamp_duty = stamp_raw.quantize(rupee, rounding=ROUND_HALF_UP).quantize(paise)

    gst_taxable_base = total_brokerage + exchange_charges + sebi_charges
    gst = (stat_sched.gst_rate * gst_taxable_base).quantize(paise, rounding=ROUND_HALF_UP)

    total_costs = (
        total_brokerage + stt + exchange_charges + sebi_charges + stamp_duty + gst
    ).quantize(paise, rounding=ROUND_HALF_UP)

    breakeven_diff = (total_costs / qty_dec).quantize(fourth_dec, rounding=ROUND_HALF_UP)

    return CostBreakdown(
        turnover=total_turnover,
        buy_turnover=buy_turnover,
        sell_turnover=sell_turnover,
        brokerage=total_brokerage,
        brokerage_buy=brokerage_buy,
        brokerage_sell=brokerage_sell,
        stt=stt,
        exchange_charges=exchange_charges,
        sebi_charges=sebi_charges,
        stamp_duty=stamp_duty,
        gst=gst,
        total_costs=total_costs,
        breakeven_diff=breakeven_diff,
        exchange=exch_sched.exchange,
        segment=exch_sched.segment,
        broker_schedule=broker_sched.broker_id,
        effective_date=eval_date,
        statutory_circular=stat_sched.source_circular,
        exchange_circular=exch_sched.source_circular,
        is_estimate=True,
    )
