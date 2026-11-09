"""Budget Manager API (port of trader-budget from Indian Day Trader).

Position sizing for Indian equity day trades. Sizes whole integer shares
to budget and max-loss-per-trade in INR (₹), accounting for Indian
statutory transaction costs and slippage. Produces a bracket order
proposal (NSE MIS LIMIT). Advisory only — nothing is placed.

Endpoints:
  POST /api/budget/size        Size a trade from an exit plan
  POST /api/budget/size/weights Split a budget across weighted tickers
"""

from __future__ import annotations

import datetime
import json
import os
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from core.trader_core import calculate_intraday_costs, CostError, IST
from core.auth import verify_api_key

router = APIRouter(prefix="/api/budget", tags=["budget-manager"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ORDERS_FILE = os.path.join(DATA_DIR, "budget_orders.json")

CENT = Decimal("0.01")
DEFAULTS = {
    "budget": None,
    "cash_buffer_pct": Decimal("10"),
    "max_position_pct": Decimal("25"),
    "max_order_inr": None,
    "min_order_inr": None,
    "max_loss_per_trade_inr": Decimal("5000"),
    "max_daily_loss_inr": Decimal("15000"),
    "max_trades_per_day": 3,
    "max_orders_per_day": 10,
    "min_reward_risk": Decimal("1.0"),
    "require_stop": True,
    "no_entries_before": "09:30",
    "no_entries_after": "15:00",
    "flat_by": "15:15",
    "fractional": False,
    "exchange": "NSE",
    "product": "MIS",
    "order_type": "LIMIT",
    "variety": "REGULAR",
    "broker": "paper",
    "broker_schedule": "discount",
    "paper": True,
    "blocked": [],
    "slippage_rate": Decimal("0.0005"),
}

SETUP_WORDS = {"orb": "opening-range breakout", "flag": "flag", "bounce": "oversold bounce"}


class SizeError(Exception):
    pass


class SizeRequest(BaseModel):
    symbol: str
    entry: float
    stop: float
    target: float
    setup: str = "orb"
    date: Optional[str] = None
    entry_time: Optional[str] = None
    qty: int = 100
    broker: str = "discount"
    exchange: str = "NSE"
    budget: Optional[float] = None
    limit_price: Optional[float] = None
    latest_price: Optional[float] = None
    cash: Optional[float] = None


class SizeResponse(BaseModel):
    symbol: str
    exchange: str
    product: str
    order_type: str
    variety: str
    side: str
    setup: str
    entry: float
    stop: float
    target: float
    risk_per_share: float
    reward_risk: float
    qty: int
    bound_by: str
    cost: float
    max_loss: float
    total_loss_at_stop: float
    costs: dict
    slippage: float
    flat_by: str
    refusal: Optional[str] = None
    order_proposal: Optional[dict] = None


class WeightRow(BaseModel):
    ticker: str
    weight: float
    name: Optional[str] = ""


class WeightsRequest(BaseModel):
    weights: list[WeightRow]
    budget: Optional[float] = None


def D(x, what="a number"):
    if x is None:
        return None
    if isinstance(x, Decimal):
        return x
    try:
        s = str(x).strip().lstrip("₹").lstrip("$").replace(",", "")
        return Decimal(s)
    except (InvalidOperation, ValueError):
        raise SizeError("%s is not a valid number: %s" % (what, x))


def round_cent(x):
    return D(x).quantize(CENT, rounding=ROUND_HALF_UP)


def money(x):
    d = round_cent(x)
    if d == d.to_integral():
        return "₹%s" % format(d, ",.0f")
    return "₹%s" % format(d, ",.2f")


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    cfg_path = os.path.join(DATA_DIR, "trader_config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as fh:
                cfg.update(json.load(fh))
        except (ValueError, OSError):
            pass
    return cfg


def size_trade(plan: dict, cfg: dict, budget: Optional[Decimal] = None,
               limit: Optional[Decimal] = None, price: Optional[Decimal] = None,
               cash: Optional[Decimal] = None, today: Optional[str] = None) -> dict:
    c = dict(DEFAULTS)
    c.update(cfg or {})

    sym = str(plan.get("symbol") or "").strip().upper()
    if not sym:
        raise SizeError("the plan has no symbol")

    side = str(plan.get("side") or "buy").strip().lower()
    if side != "buy":
        raise SizeError("this pack sizes long (buy) day trades only; the plan says %r" % side)

    if today and plan.get("date") and str(plan["date"]) != str(today):
        raise SizeError("the plan is for %s and today is %s in IST: make a new plan" % (plan["date"], today))

    entry_plan = D(plan.get("entry"), "entry")
    stop = D(plan.get("stop"), "stop")
    target = D(plan.get("target"), "target")
    for name, v in (("entry", entry_plan), ("stop", stop), ("target", target)):
        if v is None or v <= Decimal("0"):
            raise SizeError("the plan needs a positive %s" % name)

    blocked = {str(b).upper() for b in (c.get("blocked") or [])}
    if sym in blocked:
        raise SizeError("%s is on your blocked list" % sym)

    budget_raw = budget if budget is not None else c.get("budget")
    if budget_raw is None or D(budget_raw) <= Decimal("0"):
        raise SizeError('no budget: pass budget or set "budget" in config')
    budget = D(budget_raw)

    buf_pct = D(c.get("cash_buffer_pct", 10))
    if not (Decimal("0") <= buf_pct < Decimal("100")):
        raise SizeError("cash_buffer_pct must be between 0 and 100")

    if limit is not None:
        ref = round_cent(limit)
        ref_from = "limit"
    elif price is not None and round_cent(price) > round_cent(entry_plan):
        ref = round_cent(price)
        ref_from = "price"
    else:
        ref = round_cent(entry_plan)
        ref_from = "plan"

    stop = round_cent(stop)
    target = round_cent(target)

    if stop >= ref:
        raise SizeError("the stop %s is not below the entry %s" % (money(stop), money(ref)))
    if target <= ref:
        raise SizeError("the target %s is not above the entry %s" % (money(target), money(ref)))

    risk_per_share = ref - stop
    reward_per_share = target - ref
    reward_risk = (reward_per_share / risk_per_share).quantize(CENT, rounding=ROUND_HALF_UP)

    cash_buffer = (budget * buf_pct / Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP)
    available = budget - cash_buffer

    if cash is not None:
        cash_dec = D(cash)
        if cash_dec - cash_buffer < available:
            available = cash_dec - cash_buffer
    available = max(available.quantize(CENT, rounding=ROUND_HALF_UP), Decimal("0.00"))

    limits = []
    max_loss = D(c.get("max_loss_per_trade_inr"))
    if max_loss is not None and max_loss > Decimal("0"):
        shares_loss = int(max_loss // risk_per_share)
        shares_loss = (shares_loss // 1) * 1
        limits.append({
            "name": "max loss",
            "inr": max_loss,
            "per": risk_per_share,
            "shares": shares_loss,
            "how": "%s max loss / %s risk a share" % (money(max_loss), money(risk_per_share)),
        })

    cap_pct = D(c.get("max_position_pct"))
    if cap_pct is not None and cap_pct > Decimal("0"):
        cap = (budget * cap_pct / Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP)
        shares_cap = int(cap // ref)
        limits.append({
            "name": "position cap",
            "inr": cap,
            "per": ref,
            "shares": shares_cap,
            "how": "%s%% of %s = %s / %s" % (format(cap_pct.normalize(), "f"), money(budget), money(cap), money(ref)),
        })

    max_order = D(c.get("max_order_inr"))
    if max_order is not None and max_order > Decimal("0"):
        shares_order = int(max_order // ref)
        limits.append({
            "name": "max order",
            "inr": max_order,
            "per": ref,
            "shares": shares_order,
            "how": "%s / %s" % (money(max_order), money(ref)),
        })

    shares_cash = int(available // ref)
    limits.append({
        "name": "cash",
        "inr": available,
        "per": ref,
        "shares": shares_cash,
        "how": "%s / %s" % (money(available), money(ref)),
    })

    min_limit_shares = min(l["shares"] for l in limits)
    qty = max(0, min_limit_shares)
    bound_candidates = [l["name"] for l in limits if l["shares"] == qty]
    bound_by = bound_candidates[0] if bound_candidates else "cash"

    broker_sched = str(c.get("broker_schedule") or "discount").lower()
    slippage_rate = D(c.get("slippage_rate") or "0.0005")

    try:
        eval_date = datetime.date.fromisoformat(today) if today else datetime.date.today()
    except ValueError:
        eval_date = datetime.date.today()

    costs = None
    slippage = Decimal("0.00")
    total_loss_at_stop = (risk_per_share * Decimal(qty)).quantize(CENT, rounding=ROUND_HALF_UP)

    if qty > 0 and max_loss is not None:
        while qty > 0:
            try:
                costs = calculate_intraday_costs(
                    buy_price=ref,
                    sell_price=stop,
                    qty=qty,
                    exchange=str(c.get("exchange", "NSE")),
                    segment="EQ",
                    broker_schedule=broker_sched,
                    effective_date=eval_date,
                )
                costs_val = costs.total_costs
            except (CostError, Exception):
                costs_val = Decimal("0.00")
            slippage = ((ref + stop) * slippage_rate * Decimal(qty)).quantize(CENT, rounding=ROUND_HALF_UP)
            gross_risk = (risk_per_share * Decimal(qty)).quantize(CENT, rounding=ROUND_HALF_UP)
            total_loss_at_stop = gross_risk + costs_val + slippage
            if total_loss_at_stop <= max_loss:
                break
            qty -= 1
            bound_by = "max loss"
    elif qty > 0:
        try:
            costs = calculate_intraday_costs(
                buy_price=ref,
                sell_price=stop,
                qty=qty,
                exchange=str(c.get("exchange", "NSE")),
                segment="EQ",
                broker_schedule=broker_sched,
                effective_date=eval_date,
            )
            costs_val = costs.total_costs
        except (CostError, Exception):
            costs_val = Decimal("0.00")
        slippage = ((ref + stop) * slippage_rate * Decimal(qty)).quantize(CENT, rounding=ROUND_HALF_UP)
        gross_risk = (risk_per_share * Decimal(qty)).quantize(CENT, rounding=ROUND_HALF_UP)
        total_loss_at_stop = gross_risk + costs_val + slippage

    for l in limits:
        l["binds"] = (l["name"] == bound_by)

    cost = (ref * Decimal(qty)).quantize(CENT, rounding=ROUND_HALF_UP)
    refusal = None

    if qty == 0:
        if bound_by == "max loss":
            refusal = ("one share risks %s (entry %s minus stop %s), more than your %s max loss per trade. "
                       "No order. Skip this trade, or plan a closer stop." % (
                           money(risk_per_share), money(ref), money(stop), money(max_loss)))
        else:
            bound_limit = [l for l in limits if l["name"] == bound_by][0]
            refusal = "one share of %s costs %s, more than your %s limit (%s). No order." % (
                sym, money(ref), bound_by, bound_limit["how"])
    elif c.get("min_reward_risk") and reward_risk < D(c["min_reward_risk"]):
        refusal = ("reward:risk %.2f is under your minimum %s, so trader-risk would block it. No order." % (
            reward_risk, format(D(c["min_reward_risk"]).normalize(), "f")))
    elif c.get("min_order_inr") and cost < D(c["min_order_inr"]):
        refusal = "%d share of %s is %s, under your %s minimum order. No order." % (
            qty, sym, money(cost), money(D(c["min_order_inr"])))

    product = str(plan.get("product") or c.get("product_type") or c.get("product") or "MIS").strip().upper()

    return {
        "symbol": sym,
        "exchange": str(c.get("exchange", "NSE")),
        "product": product,
        "order_type": "limit" if limit is not None else str(c.get("order_type", "LIMIT")).lower(),
        "variety": str(c.get("variety", "REGULAR")).upper(),
        "side": "buy",
        "setup": plan.get("setup", ""),
        "date": plan.get("date") or today,
        "entry_plan": round_cent(entry_plan),
        "entry": ref,
        "entry_from": ref_from,
        "stop": stop,
        "target": target,
        "risk_per_share": risk_per_share,
        "reward_risk": reward_risk,
        "budget": budget,
        "cash_buffer_pct": buf_pct,
        "cash_buffer": cash_buffer,
        "cash_available": available,
        "max_loss_budget": max_loss,
        "max_loss_per_trade_inr": max_loss,
        "limits": [{k: (float(v) if isinstance(v, Decimal) else v) for k, v in l.items()} for l in limits],
        "qty": int(qty),
        "bound_by": bound_by,
        "cost": cost,
        "max_loss": (risk_per_share * Decimal(qty)).quantize(CENT, rounding=ROUND_HALF_UP),
        "total_loss_at_stop": total_loss_at_stop,
        "costs": costs.to_dict() if costs else {},
        "slippage": slippage,
        "flat_by": plan.get("flat_by") or c.get("flat_by") or "15:15",
        "refusal": refusal,
    }


def bracket_order(s: dict) -> Optional[dict]:
    if s.get("refusal") or s.get("qty", 0) <= 0:
        return None
    date_str = str(s.get("date") or datetime.date.today().isoformat()).replace("-", "")
    order_id = "%s-01" % date_str
    setup = SETUP_WORDS.get(s["setup"], s["setup"] or "day trade")
    qty_val = int(s["qty"])

    bound_expl = {
        "max loss": "%s max loss per trade" % money(s["max_loss_budget"] or 0),
        "position cap": "position cap",
        "max order": "max order",
        "cash": "cash after buffer",
    }.get(s["bound_by"], s["bound_by"])

    why = ("%s on %s: %d shares, bound by your %s (%d x %s risk = %s at the stop incl. costs)" % (
        setup, s["symbol"], qty_val, bound_expl,
        qty_val, money(s["risk_per_share"]), money(s["total_loss_at_stop"])))

    order_type_str = s.get("order_type", "LIMIT").upper()
    return {
        "id": order_id,
        "symbol": s["symbol"],
        "exchange": s["exchange"],
        "product": s["product"],
        "order_type": order_type_str,
        "type": order_type_str,
        "variety": s.get("variety", "REGULAR"),
        "side": "BUY",
        "quantity": qty_val,
        "qty": qty_val,
        "price": "%.2f" % s["entry"],
        "limit_price": "%.2f" % s["entry"],
        "trigger_price": "%.2f" % s["stop"],
        "stop_loss_stop_price": "%.2f" % s["stop"],
        "take_profit_limit_price": "%.2f" % s["target"],
        "order_class": "bracket",
        "time_in_force": "DAY",
        "status": "PROPOSED",
        "is_proposal": True,
        "note": "Sizing proposal only; not an executed trade or approved order.",
        "why": why,
        "costs_breakdown": s.get("costs", {}),
        "slippage_allowance": str(s.get("slippage", Decimal("0.00"))),
        "risk_budget": str(s.get("max_loss_budget", Decimal("0.00"))),
        "total_loss_at_stop": str(s.get("total_loss_at_stop", Decimal("0.00"))),
        "plan": {
            "entry": float(s["entry"]),
            "stop": float(s["stop"]),
            "target": float(s["target"]),
            "risk_per_share": float(s["risk_per_share"]),
            "max_loss": float(s["total_loss_at_stop"]),
            "setup": s.get("setup", ""),
            "entry_time": s.get("entry_time", ""),
            "flat_by": s.get("flat_by", "15:15"),
        },
    }


@router.post("/size", response_model=SizeResponse)
def size_trade_endpoint(req: SizeRequest, auth: bool = Depends(verify_api_key)):
    """Size a day trade to budget and max loss. Returns a bracket order proposal."""
    try:
        plan = {
            "symbol": req.symbol,
            "entry": req.entry,
            "stop": req.stop,
            "target": req.target,
            "setup": req.setup,
            "date": req.date,
            "entry_time": req.entry_time,
            "side": "buy",
            "exchange": req.exchange,
            "qty": req.qty,
        }
        cfg = load_config()
        budget = D(req.budget) if req.budget is not None else None
        limit = D(req.limit_price) if req.limit_price is not None else None
        price = D(req.latest_price) if req.latest_price is not None else None
        cash = D(req.cash) if req.cash is not None else None

        s = size_trade(plan, cfg, budget, limit, price, cash, req.date)
        order = bracket_order(s)

        if order:
            os.makedirs(DATA_DIR, exist_ok=True)
            tmp = ORDERS_FILE + ".tmp"
            doc = {
                "schema_version": "1.0.0",
                "created_by": "trader-budget",
                "created_at": datetime.datetime.now(IST).isoformat(),
                "status": "PROPOSED",
                "paper": bool(cfg.get("paper", True)),
                "currency": "INR",
                "orders": [order],
            }
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, indent=2)
                fh.write("\n")
            os.replace(tmp, ORDERS_FILE)

        return {
            "symbol": s["symbol"],
            "exchange": s["exchange"],
            "product": s["product"],
            "order_type": s["order_type"],
            "variety": s["variety"],
            "side": s["side"],
            "setup": s["setup"],
            "entry": float(s["entry"]),
            "stop": float(s["stop"]),
            "target": float(s["target"]),
            "risk_per_share": float(s["risk_per_share"]),
            "reward_risk": float(s["reward_risk"]),
            "qty": s["qty"],
            "bound_by": s["bound_by"],
            "cost": float(s["cost"]),
            "max_loss": float(s["max_loss"]),
            "total_loss_at_stop": float(s["total_loss_at_stop"]),
            "costs": s.get("costs", {}),
            "slippage": float(s["slippage"]),
            "flat_by": s["flat_by"],
            "refusal": s.get("refusal"),
            "order_proposal": order,
        }
    except SizeError as se:
        raise HTTPException(status_code=400, detail=str(se))


@router.post("/size/weights")
def size_weights(req: WeightsRequest):
    """Split a budget across weighted tickers (portfolio mode)."""
    try:
        cfg = load_config()
        budget = D(req.budget) if req.budget is not None else cfg.get("budget")
        if budget is None or D(budget) <= Decimal("0"):
            raise SizeError('no budget: pass budget or set "budget" in config')
        budget = D(budget)

        buf_pct = D(cfg.get("cash_buffer_pct", 10))
        cap_pct = D(cfg.get("max_position_pct", 25))
        min_order = D(cfg.get("min_order_inr", 500) or 0)

        rows = []
        seen = set()
        for w in req.weights:
            t = w.ticker.strip().upper()
            if t in seen:
                raise SizeError("%s is listed twice in the weights" % t)
            seen.add(t)
            wt = D(w.weight)
            if wt <= Decimal("0"):
                continue
            rows.append({"ticker": t, "name": w.name or "", "weight": wt})

        if not rows:
            raise SizeError("nothing to size: no valid weights")

        total = sum(r["weight"] for r in rows)
        for r in rows:
            r["weight"] = (Decimal("100") * r["weight"] / total).quantize(CENT, rounding=ROUND_HALF_UP)

        cash_buffer = (budget * buf_pct / Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP)
        investable = budget - cash_buffer
        cap = (budget * cap_pct / Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP)

        positions = []
        invested = Decimal("0.00")
        for r in rows:
            target_amt = min(cap, (investable * r["weight"] / Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP))
            positions.append({
                "ticker": r["ticker"],
                "name": r["name"],
                "weight": float(r["weight"]),
                "inr": float(target_amt),
                "shares": 0,
                "capped": target_amt >= cap,
            })
            invested += target_amt

        return {
            "budget": float(budget),
            "cash_buffer_pct": float(buf_pct),
            "cash_buffer": float(cash_buffer),
            "investable": float(investable),
            "max_position_pct": float(cap_pct),
            "cap": float(cap),
            "positions": positions,
            "invested": float(invested),
            "idle": float(investable - invested),
        }
    except SizeError as se:
        raise HTTPException(status_code=400, detail=str(se))
