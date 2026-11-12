"""Exit Planner API (port of trader-exit from Indian Day Trader).

Sets the stop and target BEFORE you enter on NSE/BSE, with full Indian
statutory cost netting (STT, GST, SEBI, exchange charges, stamp duty,
brokerage) and slippage hurdle check. Long side only. Advisory only —
no automated broker execution.

Endpoints:
  POST /api/exit/plan        Compute a stop/target plan
  GET  /api/exit/plan/{symbol}  Get the latest saved plan for a symbol
"""

from __future__ import annotations

import datetime
import json
import os
import re
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from core.trader_core import (
    calculate_intraday_costs,
    CostError,
    FeeScheduleError,
    get_default_calendar,
    IST,
)
from core.auth import verify_api_key

router = APIRouter(prefix="/api/exit", tags=["exit-planner"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PLANS_FILE = os.path.join(DATA_DIR, "exit_plans.json")

CENT = Decimal("0.01")
MIN_RISK_PCT = Decimal("0.05")
DEFAULT_SLIPPAGE_RATE = Decimal("0.0005")
DEFAULTS = {
    "flat_by": "15:15",
    "min_reward_risk": 1.0,
    "broker": "discount",
    "exchange": "NSE",
    "qty": 100,
}

OPEN = datetime.time(9, 15)
CLOSE = datetime.time(15, 30)


class PlanError(Exception):
    pass


class ExitPlanRequest(BaseModel):
    symbol: str = "RELIANCE"
    entry: float
    stop_rule: str = "orb_mid"  # orb_mid, orb_low, price, pct, atr
    stop_param: Optional[float] = None
    or_high: Optional[float] = None
    or_low: Optional[float] = None
    target_rule: str = "r"  # r, price
    target_param: Optional[float] = None  # R multiple or price
    qty: int = 100
    broker: str = "discount"
    exchange: str = "NSE"
    atr: Optional[float] = None
    atr_bars: int = 14
    date: Optional[str] = None  # YYYY-MM-DD


class ExitPlanResponse(BaseModel):
    symbol: str
    date: str
    setup: str
    entry: float
    stop: float
    stop_rule: str
    stop_label: str
    target: float
    target_r: float
    target_label: str
    risk_per_share: float
    reward_risk: float
    net_reward_risk: float
    net_reward_per_share: float
    breakeven: float
    breakeven_diff: float
    total_hurdle: float
    slippage: float
    statutory_costs: dict
    flat_by: str
    created_at: str
    note: str
    warnings: list[str] = []


def D(x, what="a number"):
    try:
        if isinstance(x, float):
            return Decimal(repr(x))
        return Decimal(str(x).strip().lstrip("₹").lstrip("$").replace(",", ""))
    except (InvalidOperation, ValueError):
        raise PlanError("%s is not a number: %r" % (what, x))


def cents(x):
    return D(x).quantize(CENT, rounding=ROUND_HALF_UP)


def floor_cents(x):
    return D(x).quantize(CENT, rounding=ROUND_FLOOR)


def parse_stop(text: str):
    t = str(text).strip().lower()
    if t in ("or-mid", "or_mid", "mid", "or-midpoint", "orb-mid", "orb_mid", "orb-midpoint"):
        return "or_mid", None
    if t in ("or-low", "or_low", "low", "orb-low", "orb_low"):
        return "or_low", None
    m = re.match(r"^(price|pct|atr):\s*[₹\$]?([0-9][0-9,]*\.?[0-9]*)$", t)
    if not m:
        raise PlanError("stop is or_mid, or_low, price:X, pct:X or atr:K (got %r)" % text)
    kind, val = m.group(1), D(m.group(2), "stop")
    if val <= 0:
        raise PlanError("stop %s needs a number above 0" % kind)
    if kind == "pct" and val >= 100:
        raise PlanError("stop pct:X needs X under 100")
    return kind, val


def _normalize_stop_rule(rule: str) -> str:
    r = rule.strip().lower()
    if r in ("orb_mid", "or-mid", "or-midpoint", "orb-mid", "orb-midpoint"):
        return "or_mid"
    if r in ("orb_low", "or-low", "orb-low"):
        return "or_low"
    return r


def parse_target(text: Optional[str]):
    if text is None:
        return "r", Decimal("1.5")
    t = str(text).strip()
    m = re.match(r"^([0-9]*\.?[0-9]+)\s*[Rr]$", t)
    if m:
        r = D(m.group(1), "target")
        if r <= 0:
            raise PlanError("target needs an R multiple above 0, like 1R, 1.5R or 2R")
        return "r", r
    m = re.match(r"^price:\s*[₹\$]?([0-9][0-9,]*\.?[0-9]*)$", t.lower())
    if m:
        return "price", D(m.group(1), "target")
    raise PlanError("target is 1.5R (default), 1R, 2R ... or price:X (got %r)" % text)


def r_label(r):
    n = int(r) if r == r.to_integral_value() else None
    WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
    return "%sR (%s times the risk)" % (format(r.normalize(), "f"), WORDS.get(n, format(r.normalize(), "f")))


def compute_plan(
    entry: Decimal,
    stop_rule: str,
    stop_param: Optional[Decimal],
    target_rule: str,
    target_param: Decimal,
    or_high: Optional[Decimal],
    or_low: Optional[Decimal],
    atr: Optional[Decimal],
    atr_bars: int,
    day: datetime.date,
    qty: int,
    broker: str,
    exchange: str,
) -> dict:
    e = cents(entry)
    if e <= 0:
        raise PlanError("the entry price must be above ₹0")

    detail = ""
    if stop_rule in ("or_mid", "or_low"):
        if or_high is None or or_low is None:
            raise PlanError("an %s stop needs the opening range (or_high and or_low)" % stop_rule.replace("_", "-"))
        oh, ol = cents(or_high), cents(or_low)
        if oh <= ol:
            raise PlanError("the opening-range high %s must be above its low %s" % (oh, ol))
        if stop_rule == "or_mid":
            raw = (oh + ol) / 2
            label = "opening-range midpoint"
            detail = "(%s + %s) / 2 = %s" % (oh, ol, format(raw.normalize(), "f"))
        else:
            raw, label = ol, "opening-range low"
    elif stop_rule == "price":
        raw, label = stop_param, "your price"
    elif stop_rule == "pct":
        raw = e * (1 - stop_param / 100)
        label = "%s%% under the entry" % format(stop_param.normalize(), "f")
        detail = "%s x (1 - %s%%) = %s" % (e, stop_param.normalize(), format(raw.normalize(), "f"))
    elif stop_rule == "atr":
        if atr is None:
            raise PlanError("an atr stop needs the session's bars")
        a = D(round(atr, 6))
        raw = e - stop_param * a
        label = "%s x ATR(%d) under the entry" % (format(stop_param.normalize(), "f"), atr_bars)
    else:
        raise PlanError("unknown stop rule %r" % stop_rule)

    stop = floor_cents(raw)
    if stop >= e:
        raise PlanError("the stop %s (%s) is at or above the entry %s" % (stop, label, e))
    if stop <= 0:
        raise PlanError("the stop works out to %s: pick a stop above ₹0" % stop)

    risk = e - stop
    floor_risk = e * MIN_RISK_PCT / 100
    if risk < floor_risk:
        raise PlanError("the stop is %s under the entry, less than 0.05%% of the price: too tight to survive the spread" % risk)

    if target_rule == "r":
        target = cents(e + target_param * risk)
        t_label = r_label(target_param)
    else:
        target = cents(target_param)
        t_label = "your price (%sR)" % format(((target - e) / risk).quantize(CENT, rounding=ROUND_HALF_UP).normalize(), "f")

    if target <= e:
        raise PlanError("the target %s is at or below the entry %s" % (target, e))

    rr = ((target - e) / risk).quantize(CENT, rounding=ROUND_HALF_UP)

    # Statutory cost netting & hurdle check
    q = int(qty or 100)
    if q <= 0:
        q = 100

    try:
        cost_breakdown = calculate_intraday_costs(
            buy_price=e,
            sell_price=target,
            qty=q,
            exchange=exchange,
            segment="EQ",
            broker_schedule=broker,
            effective_date=day,
        )
    except (CostError, FeeScheduleError) as ce:
        raise PlanError("Statutory cost calculation failed: %s" % ce)

    total_costs_per_share = (cost_breakdown.total_costs / Decimal(q)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    slippage = ((e + target) * DEFAULT_SLIPPAGE_RATE).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    total_hurdle = (total_costs_per_share + slippage).quantize(CENT, rounding=ROUND_HALF_UP)
    gross_reward = target - e
    net_reward = (gross_reward - total_hurdle).quantize(CENT, rounding=ROUND_HALF_UP)

    if net_reward <= Decimal("0"):
        raise PlanError(
            "the target %s does not clear statutory costs and slippage hurdle (%s): costs exceed profit margin."
            % (target, total_hurdle)
        )

    net_rr = (net_reward / risk).quantize(CENT, rounding=ROUND_HALF_UP)
    breakeven = cents(e + total_hurdle)

    return {
        "entry": e,
        "stop": stop,
        "stop_rule": stop_rule,
        "stop_label": label,
        "stop_detail": detail,
        "target": target,
        "target_r": target_param if target_rule == "r" else rr,
        "target_label": t_label,
        "risk": risk,
        "reward_risk": rr,
        "net_reward_risk": net_rr,
        "net_reward": net_reward,
        "net_risk": risk,
        "total_hurdle": total_hurdle,
        "breakeven": breakeven,
        "breakeven_diff": total_hurdle,
        "slippage": slippage.quantize(CENT, rounding=ROUND_HALF_UP),
        "statutory_costs": cost_breakdown.to_dict(),
    }


def _load_plans() -> dict:
    if not os.path.exists(PLANS_FILE):
        return {}
    try:
        with open(PLANS_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return {}


def _save_plans(plans: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = PLANS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(plans, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, PLANS_FILE)


@router.get("/plans")
def exit_plans_list(auth: bool = Depends(verify_api_key)):
    """All saved exit plans, keyed by symbol."""
    return {"plans": _load_plans()}


@router.post("/plan", response_model=ExitPlanResponse)
def exit_plan(req: ExitPlanRequest, auth: bool = Depends(verify_api_key)):
    """Compute a stop/target plan with statutory cost netting."""
    try:
        e = D(req.entry, "entry")
        stop_param = D(req.stop_param, "stop_param") if req.stop_param is not None else None
        target_param = D(req.target_param, "target_param") if req.target_param is not None else None
        or_high = D(req.or_high, "or_high") if req.or_high is not None else None
        or_low = D(req.or_low, "or_low") if req.or_low is not None else None
        atr = D(req.atr, "atr") if req.atr is not None else None

        stop_rule = _normalize_stop_rule(req.stop_rule)

        day = datetime.date.today()
        if req.date:
            try:
                day = datetime.date.fromisoformat(req.date)
            except ValueError:
                raise PlanError("date wants YYYY-MM-DD, not %r" % req.date)

        c = compute_plan(
            entry=e,
            stop_rule=stop_rule,
            stop_param=stop_param,
            target_rule=req.target_rule,
            target_param=target_param,
            or_high=or_high,
            or_low=or_low,
            atr=atr,
            atr_bars=req.atr_bars,
            day=day,
            qty=req.qty,
            broker=req.broker,
            exchange=req.exchange,
        )

        cal = get_default_calendar()
        flat_by = DEFAULTS["flat_by"]
        now_ist = datetime.datetime.now(IST)
        entry_time = now_ist.time()

        # Warn if entry is at/after flat-by
        fb_h, fb_m = flat_by.split(":")
        flat_t = datetime.time(int(fb_h), int(fb_m))
        warnings = []
        if entry_time >= flat_t:
            warnings.append("Entry at %s is at/after flat-by %s IST: no time to hold intraday." % (entry_time.strftime("%H:%M"), flat_by))

        plan = {
            "symbol": req.symbol.upper(),
            "date": day.isoformat(),
            "setup": "orb" if (or_high is not None and or_low is not None) else "level",
            "entry": float(c["entry"]),
            "stop": float(c["stop"]),
            "stop_rule": c["stop_rule"],
            "stop_label": c["stop_label"],
            "stop_detail": c["stop_detail"],
            "target": float(c["target"]),
            "target_r": float(c["target_r"]),
            "target_label": c["target_label"],
            "risk_per_share": float(c["risk"]),
            "reward_risk": float(c["reward_risk"]),
            "net_reward_risk": float(c["net_reward_risk"]),
            "net_reward_per_share": float(c["net_reward"]),
            "breakeven": float(c["breakeven"]),
            "breakeven_diff": float(c["breakeven_diff"]),
            "total_hurdle": float(c["total_hurdle"]),
            "slippage": float(c["slippage"]),
            "statutory_costs": c["statutory_costs"],
            "flat_by": flat_by,
            "created_at": now_ist.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "note": "A stop is a plan, not a guarantee: a gap or a fast market can fill past it.",
            "warnings": warnings,
        }

        plans = _load_plans()
        plans[req.symbol.upper()] = plan
        _save_plans(plans)

        return plan
    except PlanError as pe:
        raise HTTPException(status_code=400, detail=str(pe))


@router.get("/plan/{symbol}", response_model=ExitPlanResponse)
def get_exit_plan(symbol: str):
    """Get the latest saved exit plan for a symbol."""
    plans = _load_plans()
    plan = plans.get(symbol.upper())
    if not plan:
        raise HTTPException(status_code=404, detail="No exit plan for %s. Create one with POST /api/exit/plan" % symbol)
    return plan
