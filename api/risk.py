"""Risk Manager API (port of trader-risk from Indian Day Trader).

Pre-trade risk gate: checks proposed orders against risk limits and
returns an immutable PASS/BLOCK decision with machine-readable reason codes.
Advisory only — PASS is NOT an executed trade.

Endpoints:
  POST /api/risk/check        Check proposed orders against risk limits
"""

from __future__ import annotations

import copy
import datetime
import hashlib
import json
import os
import re
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.trader_core import (
    IST,
    calculate_intraday_costs,
    get_default_calendar,
    is_trading_day,
    parse_ist_timestamp,
)

router = APIRouter(prefix="/api/risk", tags=["risk-manager"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
RISK_FILE = os.path.join(DATA_DIR, "risk.json")

DEFAULTS = {
    "budget": 500000.0,
    "cash_buffer_pct": 10.0,
    "max_position_pct": 25.0,
    "max_order_inr": 200000.0,
    "min_order_inr": 500.0,
    "max_loss_per_trade_inr": 5000.0,
    "max_daily_loss_inr": 15000.0,
    "max_trades_per_day": 3,
    "max_orders_per_day": 10,
    "min_reward_risk": 1.0,
    "require_stop": True,
    "no_entries_before": "09:30",
    "no_entries_after": "15:00",
    "flat_by": "15:15",
    "paper": True,
    "blocked": [],
    "allow_options": False,
    "allow_margin": False,
    "allow_short": False,
    "max_adv_pct": 1.5,
    "max_bar_vol_pct": 5.0,
    "slippage_pct": 0.05,
    "kill_switch": False,
    "proposal_ttl_seconds": 60,
    "exchange": "NSE",
    "broker": "discount",
}

TICK_SIZE = Decimal("0.05")
HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


class RiskError(Exception):
    pass


class OrderInput(BaseModel):
    symbol: str
    side: str = "buy"
    qty: Optional[int] = None
    quantity: Optional[int] = None
    notional: Optional[float] = None
    type: str = "limit"
    order_type: Optional[str] = None
    time_in_force: str = "day"
    limit_price: Optional[float] = None
    price: Optional[float] = None
    stop_price: Optional[float] = None
    stop_loss_stop_price: Optional[float] = None
    take_profit_limit_price: Optional[float] = None
    exchange: Optional[str] = None
    product: Optional[str] = None
    product_type: Optional[str] = None
    created_at: Optional[str] = None
    plan: Optional[dict] = None
    market_data: Optional[dict] = None


class RiskCheckRequest(BaseModel):
    orders: list[OrderInput]
    config: Optional[dict] = None
    portfolio: Optional[dict] = None
    prices: Optional[dict] = None
    state: Optional[dict] = None
    today: Optional[str] = None
    now: Optional[str] = None


def _d(v):
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None


def money(x):
    if x is None:
        return "₹0.00"
    try:
        return "₹{:,.2f}".format(float(x))
    except (TypeError, ValueError):
        return "₹" + str(x)


def check_tick_size(price, tick=TICK_SIZE):
    if price is None:
        return True
    try:
        dp = Decimal(str(price))
        remainder = (dp / tick) % Decimal("1")
        return remainder == Decimal("0")
    except Exception:
        return False


def fingerprint(order):
    core_fields = (
        "symbol", "side", "qty", "notional", "type", "time_in_force", "limit_price",
        "stop_price", "trail_price", "trail_percent", "extended_hours", "client_order_id",
        "order_class", "take_profit_limit_price", "stop_loss_stop_price",
        "stop_loss_limit_price", "advanced_instructions",
    )
    core = {k: order[k] for k in core_fields if k in order and order[k] is not None}
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def compute_orders_hash(orders):
    blob = json.dumps(orders, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def parse_now(text):
    if not text:
        return datetime.datetime.now(datetime.timezone.utc).astimezone(IST)
    if isinstance(text, datetime.datetime):
        if text.tzinfo is None:
            return text.replace(tzinfo=IST)
        return text.astimezone(IST)
    try:
        return parse_ist_timestamp(text)
    except Exception:
        raise RiskError("--now wants a valid ISO time like \"2026-10-30 10:15\"")


def hhmm(value, key):
    if value in (None, "", False):
        return None
    m = HHMM.match(str(value).strip())
    if not m:
        raise RiskError("%s must be an IST time like \"09:30\", got %r" % (key, value))
    return datetime.time(int(m.group(1)), int(m.group(2)))


def window_check(now_ist, c):
    reasons, reason_codes, warns = [], [], []
    d = now_ist.date()
    t = now_ist.time().replace(second=0, microsecond=0)

    if d.weekday() >= 5:
        reasons.append("window: market is closed on weekends (Saturday/Sunday)")
        reason_codes.append("MARKET_CLOSED_WEEKEND")
        return reasons, reason_codes, warns

    if not is_trading_day(d):
        cal = get_default_calendar()
        hname = cal.holidays.get(d.isoformat(), "holiday")
        reasons.append("window: market is closed today (NSE/BSE holiday: %s)" % d.isoformat())
        reason_codes.append("MARKET_CLOSED_HOLIDAY")
        return reasons, reason_codes, warns

    market_open = datetime.time(9, 15)
    market_close = datetime.time(15, 30)
    if t < market_open or t >= market_close:
        reasons.append("window: the market is closed (%s IST; regular session is 09:15 to 15:30)" % t.strftime("%H:%M"))
        reason_codes.append("OUTSIDE_TRADING_WINDOW")
        return reasons, reason_codes, warns

    before = hhmm(c.get("no_entries_before"), "no_entries_before")
    after = hhmm(c.get("no_entries_after"), "no_entries_after")

    if before is not None and t < before:
        reasons.append("window: no new entries before %s IST (it is %s)" % (before.strftime("%H:%M"), t.strftime("%H:%M")))
        reason_codes.append("OUTSIDE_TRADING_WINDOW")
    elif after is not None and t >= after:
        reasons.append("window: no new entries after %s IST (it is %s)" % (after.strftime("%H:%M"), t.strftime("%H:%M")))
        reason_codes.append("OUTSIDE_TRADING_WINDOW")

    return reasons, reason_codes, warns


def parse_portfolio(portfolio, cfg):
    warnings = []
    if portfolio is None:
        budget = _d(cfg.get("budget"))
        if not budget or budget <= Decimal("0"):
            return None, warnings, "PORTFOLIO_UNRESOLVED"
        return {
            "cash": budget,
            "shares": {},
            "values": {},
            "realized_daily_pnl": Decimal("0.0"),
            "unrealized_daily_pnl": Decimal("0.0"),
        }, warnings, None

    if not isinstance(portfolio, dict):
        return None, warnings, "PORTFOLIO_UNRESOLVED"

    positions = portfolio.get("positions", [])
    if not isinstance(positions, list):
        return None, warnings, "PORTFOLIO_UNRESOLVED"

    cash = _d(portfolio.get("cash"))
    if cash is None:
        cash = _d(cfg.get("budget"))
        if cash is None:
            return None, warnings, "PORTFOLIO_UNRESOLVED"

    realized_daily = _d(portfolio.get("realized_daily_pnl")) or Decimal("0.0")
    unrealized_daily = _d(portfolio.get("unrealized_daily_pnl")) or Decimal("0.0")

    shares, values = {}, {}
    for p in positions:
        if not isinstance(p, dict):
            return None, warnings, "PORTFOLIO_UNRESOLVED"
        t = str(p.get("ticker") or p.get("symbol") or "").upper()
        if not t:
            continue
        n = _d(p.get("shares") if p.get("shares") is not None else p.get("qty"))
        if n is None:
            n = sum(_d(l.get("cost")) or Decimal("0") for l in p.get("lots", []) if isinstance(l, dict))
        shares[t] = shares.get(t, Decimal("0")) + n
        basis = sum(_d(l.get("cost")) or Decimal("0") for l in p.get("lots", []) if isinstance(l, dict))
        values[t] = basis

    return {
        "cash": cash,
        "shares": shares,
        "values": values,
        "realized_daily_pnl": realized_daily,
        "unrealized_daily_pnl": unrealized_daily,
    }, warnings, None


def placed_today(state, today):
    out = []
    for rec in (state or {}).get("orders", []):
        rd = str(rec.get("date") or str(rec.get("at", ""))[:10])
        if rec.get("status") in ("placed", "filled", "FILLED", "USER_REPORTED_FILLED") and rd == today:
            out.append(rec)
    return out


@router.post("/check")
def risk_check(req: RiskCheckRequest):
    """Check proposed orders against risk limits. Returns PASS/BLOCK verdicts."""
    try:
        c = dict(DEFAULTS)
        if req.config:
            c.update(req.config)

        if "max_loss_per_trade_usd" in c and "max_loss_per_trade_inr" not in req.config:
            c["max_loss_per_trade_inr"] = c["max_loss_per_trade_usd"]
        if "max_daily_loss_usd" in c and "max_daily_loss_inr" not in req.config:
            c["max_daily_loss_inr"] = c["max_daily_loss_usd"]

        prices = {str(k).upper(): Decimal(str(v)) for k, v in (req.prices or {}).items() if _d(v) is not None}
        now_ist = parse_now(req.now)
        today = req.today or now_ist.date().isoformat()

        top_warn = []
        acct, acct_warns, port_err = parse_portfolio(req.portfolio, c)
        top_warn.extend(acct_warns)

        blocked = {str(b).upper() for b in c.get("blocked") or []}
        done_today = placed_today(req.state, today)
        count_today = len(done_today)
        entries_today = [r for r in done_today if str(r.get("side", "")).lower() == "buy"]

        loss_today = Decimal("0.0")
        for r in entries_today:
            ml = _d(r.get("max_loss"))
            if ml is not None:
                loss_today += ml

        max_daily_loss = _d(c.get("max_daily_loss_inr"))
        daily_loss_halted = False

        if acct:
            tot_loss = acct["realized_daily_pnl"] + acct["unrealized_daily_pnl"]
            if max_daily_loss and tot_loss < Decimal("0") and abs(tot_loss) >= max_daily_loss:
                daily_loss_halted = True
                top_warn.append("Daily loss ceiling breached: realized + unrealized loss ₹%s >= ceiling ₹%s"
                                % (abs(tot_loss), max_daily_loss))

        kill_switch_active = bool(c.get("kill_switch", False))
        if kill_switch_active:
            top_warn.append("EMERGENCY KILL SWITCH ACTIVE: all new proposals blocked")

        seen = set()
        results = []
        batch_entries = 0
        batch_loss = Decimal("0.0")

        input_hash = compute_orders_hash([o.model_dump() for o in req.orders])
        ttl_seconds = int(c.get("proposal_ttl_seconds", 60))

        for i, o in enumerate(req.orders, 1):
            reasons, reason_codes, warns, info = [], [], [], []
            later, later_codes = [], []

            od = o.model_dump()
            raw_sym = od.get("symbol") or ""
            sym = str(raw_sym).strip().upper()
            exchange = str(od.get("exchange") or c.get("exchange") or "NSE").upper()
            product = str(od.get("product") or od.get("product_type") or "MIS").upper()
            raw_side = od.get("side") or ""
            side = str(raw_side).strip().lower()
            typ = str(od.get("type") or od.get("order_type") or "limit").strip().lower()
            tif = str(od.get("time_in_force") or "day").strip().lower()

            raw_qty = od.get("qty") if od.get("qty") is not None else od.get("quantity")
            notional = od.get("notional")
            plan = od.get("plan") if isinstance(od.get("plan"), dict) else {}
            mkt = od.get("market_data") if isinstance(od.get("market_data"), dict) else {}

            # Format & Asset
            if not sym:
                reasons.append("format: no symbol")
                reason_codes.append("INVALID_SYMBOL")
            elif "/" in sym:
                reasons.append("asset: %s is an unsupported asset (equities only)" % sym)
                reason_codes.append("UNSUPPORTED_ASSET")

            if side not in ("buy", "sell"):
                reasons.append("format: side must be buy or sell, got %r" % raw_side)
                reason_codes.append("INVALID_SIDE")

            qty = None
            if raw_qty is not None:
                if isinstance(raw_qty, bool):
                    reasons.append("format: quantity cannot be boolean")
                    reason_codes.append("INVALID_QUANTITY")
                else:
                    try:
                        fq = float(raw_qty)
                        iq = int(fq)
                        if fq != iq or iq <= 0:
                            reasons.append("format: quantity must be positive integer shares, got %r" % raw_qty)
                            reason_codes.append("INVALID_QUANTITY")
                        else:
                            qty = iq
                    except (ValueError, TypeError):
                        reasons.append("format: invalid quantity %r" % raw_qty)
                        reason_codes.append("INVALID_QUANTITY")

            if notional is not None and (typ != "market" or tif != "day"):
                reasons.append("format: notional order must be market day order")
                reason_codes.append("INVALID_FORMAT")

            if port_err:
                reasons.append("portfolio: unresolved or corrupted portfolio state")
                reason_codes.append(port_err)

            if kill_switch_active:
                later.append("kill switch: emergency kill switch is active")
                later_codes.append("KILL_SWITCH_ACTIVE")

            entry_val = (
                _d(od.get("limit_price")) or _d(od.get("price")) or
                _d(od.get("stop_price")) or _d(plan.get("entry")) or prices.get(sym)
            )
            ref_from = "limit" if od.get("limit_price") else ("plan" if plan.get("entry") else "price")

            for pk in ("qty", "quantity", "notional", "limit_price", "stop_price",
                       "take_profit_limit_price", "stop_loss_stop_price", "stop_loss_limit_price",
                       "price", "trigger_price"):
                pv = od.get(pk)
                if pv is not None:
                    dpv = _d(pv)
                    if dpv is not None and not check_tick_size(dpv):
                        reasons.append("tick size: %s ₹%s violates NSE ₹0.05 tick size" % (pk, pv))
                        reason_codes.append("TICK_SIZE_VIOLATION")

            held_shares = Decimal("0.0")
            held_value = Decimal("0.0")
            if acct:
                held_shares = acct["shares"].get(sym, Decimal("0.0"))
                held_value = acct["values"].get(sym, Decimal("0.0"))

            exiting = False
            if side == "sell" and held_shares > Decimal("0"):
                if qty is not None:
                    exiting = Decimal(str(qty)) <= held_shares
                elif notional is not None:
                    exiting = Decimal(str(notional)) <= held_value
            elif side == "buy" and held_shares < Decimal("0") and qty is not None:
                exiting = Decimal(str(qty)) <= abs(held_shares)

            kind = "exit" if exiting else "entry"

            if side == "sell" and kind == "entry" and not c.get("allow_short", False):
                reasons.append("short: short selling is prohibited in cash equity intraday")
                reason_codes.append("SHORT_SELLING_PROHIBITED")

            created_str = od.get("created_at")
            if created_str and kind == "entry":
                try:
                    cdt = parse_ist_timestamp(created_str)
                    age = (now_ist - cdt).total_seconds()
                    if age > ttl_seconds:
                        later.append("proposal expired: created %d seconds ago (max TTL %ds)" % (int(age), ttl_seconds))
                        later_codes.append("PROPOSAL_EXPIRED")
                except Exception:
                    later.append("proposal: invalid creation timestamp %r" % created_str)
                    later_codes.append("PROPOSAL_EXPIRED")

            lower_circuit = _d(mkt.get("lower_circuit"))
            if lower_circuit and entry_val and kind == "entry":
                proximity_bound = lower_circuit * Decimal("1.015")
                if entry_val <= proximity_bound:
                    later.append("circuit: entry ₹%s is within 1.5%% of lower circuit ₹%s" % (entry_val, lower_circuit))
                    later_codes.append("CIRCUIT_LIMIT_PROXIMITY")

            adv_20d = None
            if mkt.get("adv_20d") is not None:
                adv_20d = float(mkt.get("adv_20d"))
            vol_5m = None
            if mkt.get("volume_5m") is not None:
                vol_5m = float(mkt.get("volume_5m"))
            max_adv_pct = float(c.get("max_adv_pct", 1.5))
            max_bar_vol_pct = float(c.get("max_bar_vol_pct", 5.0))

            if kind == "entry" and qty:
                if adv_20d and adv_20d > 0:
                    max_allowed_adv = int(adv_20d * (max_adv_pct / 100.0))
                    if qty > max_allowed_adv:
                        later.append("liquidity: %d shares exceeds %.1f%% of 20-day ADV (%d allowed)"
                                     % (qty, max_adv_pct, max_allowed_adv))
                        later_codes.append("LIQUIDITY_ADV_EXCEEDED")
                if vol_5m and vol_5m > 0:
                    max_allowed_vol = int(vol_5m * (max_bar_vol_pct / 100.0))
                    if qty > max_allowed_vol:
                        later.append("liquidity: %d shares exceeds %.1f%% of 5-minute volume (%d allowed)"
                                     % (qty, max_bar_vol_pct, max_allowed_vol))
                        later_codes.append("LIQUIDITY_BAR_VOLUME_EXCEEDED")

            stop = _d(od.get("stop_loss_stop_price") or plan.get("stop"))
            target = _d(od.get("take_profit_limit_price") or plan.get("target"))
            max_loss = None
            risk_ps = None
            rr = None

            if kind == "entry":
                if not stop:
                    if c.get("require_stop", True):
                        later.append("stop: no stop-loss provided (\"require_stop\": true)")
                        later_codes.append("STOP_REQUIRED")
                elif entry_val:
                    long_side = side == "buy"
                    if long_side and stop >= entry_val:
                        later.append("stop: stop ₹%s must be below entry ₹%s for a BUY" % (stop, entry_val))
                        later_codes.append("INVALID_STOP")
                    elif not long_side and stop <= entry_val:
                        later.append("stop: stop ₹%s must be above entry ₹%s for a SELL" % (stop, entry_val))
                        later_codes.append("INVALID_STOP")
                    else:
                        risk_ps = abs(entry_val - stop)
                        if qty:
                            max_loss = Decimal(str(qty)) * risk_ps

                        max_loss_cap = _d(c.get("max_loss_per_trade_inr"))
                        if max_loss_cap and max_loss and max_loss > max_loss_cap:
                            later.append("loss: %d shares x ₹%s risk = ₹%s, exceeding max loss per trade ₹%s"
                                         % (qty, risk_ps, max_loss, max_loss_cap))
                            later_codes.append("MAX_LOSS_PER_TRADE_EXCEEDED")

                        if target:
                            if long_side and target <= entry_val:
                                later.append("target: target ₹%s must be above entry ₹%s" % (target, entry_val))
                                later_codes.append("INVALID_TARGET")
                            elif not long_side and target >= entry_val:
                                later.append("target: target ₹%s must be below entry ₹%s" % (target, entry_val))
                                later_codes.append("INVALID_TARGET")
                            else:
                                reward = abs(target - entry_val)
                                rr = round(float(reward / risk_ps), 2)
                                min_rr = float(c.get("min_reward_risk") or 1.0)
                                if rr < min_rr - 1e-9:
                                    later.append("reward:risk: %.2f is under your minimum %.2f" % (rr, min_rr))
                                    later_codes.append("REWARD_RISK_INSUFFICIENT")

            if kind == "entry" and entry_val and target and qty and qty > 0:
                try:
                    cost_eval_date = now_ist.date()
                    broker_tariff = str(c.get("broker") or "discount").lower()
                    if broker_tariff not in ("discount", "zero", "flat20"):
                        broker_tariff = "discount"
                    cost_res = calculate_intraday_costs(
                        buy_price=entry_val,
                        sell_price=target,
                        qty=int(qty),
                        exchange=exchange,
                        segment="EQ",
                        broker_schedule=broker_tariff,
                        effective_date=cost_eval_date,
                    )
                    gross_profit = abs(target - entry_val) * Decimal(str(qty))
                    slip_pct = Decimal(str(c.get("slippage_pct", 0.05))) / Decimal("100")
                    slippage_amt = slip_pct * (entry_val + target) * Decimal(str(qty))
                    total_deductions = cost_res.total_costs + slippage_amt
                    net_profit = gross_profit - total_deductions

                    if net_profit <= Decimal("0"):
                        later.append("cost hurdle: expected gross profit ₹%s does not clear statutory costs ₹%s and slippage ₹%s"
                                     % (gross_profit, cost_res.total_costs, slippage_amt))
                        later_codes.append("COST_HURDLE_FAILED")
                except Exception as e:
                    later.append("fee schedule error: %s" % e)
                    later_codes.append("FEE_SCHEDULE_INVALID")

            order_value = None
            if qty and entry_val:
                order_value = Decimal(str(qty)) * entry_val
            elif notional is not None:
                order_value = _d(notional)

            if acct and kind == "entry" and order_value:
                total_acct = acct["cash"] + sum(acct["values"].values())
                max_pos_pct = Decimal(str(c.get("max_position_pct", 25)))
                pos_cap = total_acct * max_pos_pct / Decimal("100")
                projected_pos = held_value + order_value
                if total_acct > Decimal("0") and projected_pos > pos_cap:
                    later.append("position: order ₹%s would bring position to ₹%s (%.1f%% of ₹%s account, cap %s%%)"
                                 % (order_value, projected_pos, float(projected_pos / total_acct * 100), total_acct, max_pos_pct))
                    later_codes.append("POSITION_CAP_EXCEEDED")

            if kind == "entry":
                if daily_loss_halted:
                    later.append("daily loss: daily portfolio loss ceiling is reached; new trades halted")
                    later_codes.append("DAILY_LOSS_CEILING_BREACHED")

                if max_daily_loss and max_loss:
                    used_loss = loss_today + batch_loss
                    if used_loss + max_loss > max_daily_loss:
                        later.append("daily loss: ₹%s already at risk today plus ₹%s for this trade > ₹%s daily limit"
                                     % (used_loss, max_loss, max_daily_loss))
                        later_codes.append("DAILY_LOSS_LIMIT_EXCEEDED")

                cap_t = int(c.get("max_trades_per_day") or 0)
                if cap_t and len(entries_today) + batch_entries >= cap_t:
                    later.append("trades: %d entries already placed/passed today, daily limit is %d"
                                 % (len(entries_today) + batch_entries, cap_t))
                    later_codes.append("MAX_TRADES_EXCEEDED")

                later.extend(window_check(now_ist, c)[0])
                later_codes.extend(window_check(now_ist, c)[1])

            key = (sym, side)
            if key in seen:
                later.append("duplicate: duplicate order for %s %s in this batch" % (side.upper(), sym))
                later_codes.append("DUPLICATE_ORDER")
            placed_keys = {(str(r.get("symbol", "")).upper(), str(r.get("side", "")).lower()) for r in done_today}
            if key in placed_keys:
                later.append("duplicate: %s %s was already placed today" % (side.upper(), sym))
                later_codes.append("DUPLICATE_ORDER")
            seen.add(key)

            if kind == "entry":
                reasons.extend(later)
                reason_codes.extend(later_codes)
            else:
                warns.extend("exit, not blocked: " + x for x in later)

            verdict = "BLOCK" if reasons else "PASS"
            if verdict == "PASS" and kind == "entry":
                batch_entries += 1
                if max_loss:
                    batch_loss += max_loss
                if acct and order_value:
                    acct["cash"] -= order_value
                    acct["values"][sym] = acct["values"].get(sym, Decimal("0.0")) + order_value
                    if qty:
                        acct["shares"][sym] = held_shares + Decimal(str(qty))

            results.append({
                "index": i,
                "symbol": sym,
                "exchange": exchange,
                "product": product,
                "side": side.upper(),
                "kind": kind,
                "qty": qty,
                "amount": ("%d shares" % qty) if qty else (money(order_value) if order_value else "-"),
                "value_inr": round(float(order_value), 2) if order_value else None,
                "entry_ref": round(float(entry_val), 2) if entry_val else None,
                "entry_ref_from": ref_from,
                "stop": round(float(stop), 2) if stop else None,
                "target": round(float(target), 2) if target else None,
                "risk_per_share": round(float(risk_ps), 2) if risk_ps else None,
                "max_loss": round(float(max_loss), 2) if max_loss else None,
                "reward_risk": rr,
                "fingerprint": fingerprint(od),
                "verdict": verdict,
                "reasons": reasons,
                "reason_codes": reason_codes,
                "warnings": warns,
            })

        cash_after = float(acct["cash"]) if acct else 0.0

        # Persist result
        os.makedirs(DATA_DIR, exist_ok=True)
        res = {
            "schema_version": "1.0.0",
            "policy_version": "1.0.0",
            "is_advisory": True,
            "advisory_note": "PASS is an advisory safety approval for the exact proposal, NOT an executed trade. Execution requires explicit human confirmation via trader-broker.",
            "input_artifact_hash": input_hash,
            "date": today,
            "now_ist": now_ist.strftime("%Y-%m-%d %H:%M:%S%z"),
            "created_at": now_ist.isoformat(),
            "expires_at": (now_ist + datetime.timedelta(seconds=ttl_seconds)).isoformat(),
            "daily_loss_halted": daily_loss_halted,
            "paper": bool(c.get("paper", True)),
            "results": results,
            "pass": sum(1 for r in results if r["verdict"] == "PASS"),
            "block": sum(1 for r in results if r["verdict"] == "BLOCK"),
            "warnings": top_warn,
            "cash_after": round(cash_after, 2),
            "today": {
                "orders_placed": count_today,
                "entries_placed": len(entries_today),
                "loss_at_risk": round(float(loss_today), 2),
                "daily_loss_limit": float(max_daily_loss) if max_daily_loss else None,
            },
        }
        tmp = RISK_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, RISK_FILE)

        return res
    except RiskError as re:
        raise HTTPException(status_code=400, detail=str(re))
