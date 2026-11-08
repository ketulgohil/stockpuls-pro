"""Price Alerts API (port of trader-alerts from Indian Day Trader).

Price alerts, stop/target alerts, opening bell, and MIS square-off reminder.
Rules ring once per trigger. Advisory only — no automated execution.

Endpoints:
  GET  /api/alerts/clock              NSE open/closed status + session clock
  POST /api/alerts/quote/{symbol}     Fetch + save a quote
  POST /api/alerts/rules              Add a price/stop/target/pct/time alert
  GET  /api/alerts/rules              List active alerts
  POST /api/alerts/check              Check which alerts fired (since last check)
  DELETE /api/alerts/rules/{alert_id} Remove an alert rule
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core import upstox_data
from core.trader_core import (
    IST,
    get_default_calendar,
    get_session_phase,
    is_trading_day,
)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ALERTS_FILE = os.path.join(DATA_DIR, "alerts.json")
ALERT_STATE_FILE = os.path.join(DATA_DIR, "alert_state.json")

OPEN = datetime.time(9, 15)
CLOSE = datetime.time(15, 30)
MIS_SQUARE_OFF = "15:15"


class AlertError(Exception):
    pass


class QuoteRequest(BaseModel):
    symbol: str


class AlertRule(BaseModel):
    symbol: str
    type: str  # above, below, target, stop, pct_move, opening_bell, time
    price: Optional[float] = None
    pct: Optional[float] = None
    ref: Optional[float] = None
    at: Optional[str] = None  # HH:MM IST for 'time' type
    label: Optional[str] = None
    rearm: bool = False
    date: Optional[str] = None  # YYYY-MM-DD (plan-specific date)


class AlertCheckResponse(BaseModel):
    rang: list[dict]
    checked_at: str


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return default


def _save_json(path, doc):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def _alert_id(symbol, atype, price, at):
    blob = "%s|%s|%s|%s" % (symbol, atype, price, at)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


@router.get("/clock")
def alert_clock():
    """NSE market clock: open/closed, session phase, IST time."""
    now = datetime.datetime.now(IST)
    cal = get_default_calendar()
    trading = cal.is_trading_day(now.date())
    phase = get_session_phase(now)
    is_open = trading and phase in ("pre-open", "orb", "active", "pre-close")

    # Next open
    next_open = None
    d = now.date()
    for i in range(1, 16):
        nd = d + datetime.timedelta(days=i)
        if cal.is_trading_day(nd):
            next_open = "%s 09:15 IST" % nd.isoformat()
            break

    return {
        "ist_time": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "date": d.isoformat(),
        "is_trading_day": trading,
        "session_phase": phase,
        "is_open": is_open,
        "market_open": "09:15 IST",
        "market_close": "15:30 IST",
        "mis_square_off": MIS_SQUARE_OFF + " IST",
        "next_open": next_open,
    }


@router.post("/quote/{symbol}")
def alert_quote(symbol: str, req: QuoteRequest):
    """Fetch and save a quote for alert reference."""
    sym = (req.symbol or symbol).upper()
    try:
        q = upstox_data.get_quote(sym)
        if not q:
            raise HTTPException(status_code=404, detail="No quote for %s" % sym)
        doc = {
            "symbol": sym,
            "price": q.get("price"),
            "change": q.get("change"),
            "change_percent": q.get("changePercent"),
            "fetched": datetime.datetime.now(IST).isoformat(),
            "source": "upstox",
        }
        _save_json(ALERTS_FILE.replace("alerts.json", "prices.json"), doc)
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rules")
def add_alert_rule(rule: AlertRule):
    """Add a price/stop/target/pct/time alert rule."""
    try:
        sym = rule.symbol.upper()
        rules = _load_json(ALERTS_FILE, {"rules": []})

        # Validate type
        valid_types = ("above", "below", "target", "stop", "pct_move", "opening_bell", "time")
        if rule.type not in valid_types:
            raise HTTPException(status_code=400, detail="invalid type: %s" % rule.type)

        if rule.type in ("above", "below", "target", "stop") and rule.price is None:
            raise HTTPException(status_code=400, detail="type %s requires a price" % rule.type)
        if rule.type == "pct_move" and rule.pct is None:
            raise HTTPException(status_code=400, detail="pct_move requires a pct value")
        if rule.type == "time" and not rule.at:
            raise HTTPException(status_code=400, detail="time type requires an at (HH:MM)")

        aid = _alert_id(sym, rule.type, rule.price, rule.at)
        entry = {
            "id": aid,
            "symbol": sym,
            "type": rule.type,
            "price": rule.price,
            "pct": rule.pct,
            "ref": rule.ref,
            "at": rule.at,
            "label": rule.label or ("%s alert on %s" % (rule.type, sym)),
            "rearm": rule.rearm,
            "date": rule.date,
            "created": datetime.datetime.now(IST).isoformat(),
            "rung": False,
            "rung_at": None,
        }
        rules["rules"] = [r for r in rules["rules"] if r.get("id") != aid] + [entry]
        _save_json(ALERTS_FILE, rules)
        return {"id": aid, "message": "alert rule added", "rule": entry}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules")
def list_alert_rules():
    """List all alert rules."""
    return _load_json(ALERTS_FILE, {"rules": []})


@router.delete("/rules/{alert_id}")
def remove_alert_rule(alert_id: str):
    """Remove an alert rule by ID."""
    rules = _load_json(ALERTS_FILE, {"rules": []})
    before = len(rules["rules"])
    rules["rules"] = [r for r in rules["rules"] if r.get("id") != alert_id]
    if len(rules["rules"]) == before:
        raise HTTPException(status_code=404, detail="alert rule %s not found" % alert_id)
    _save_json(ALERTS_FILE, rules)
    return {"id": alert_id, "message": "alert rule removed"}


@router.post("/check", response_model=AlertCheckResponse)
def check_alerts():
    """Check which alerts have fired since last check. Each rings once."""
    try:
        now = datetime.datetime.now(IST)
        rules = _load_json(ALERTS_FILE, {"rules": []})
        state = _load_json(ALERT_STATE_FILE, {})
        rang = []
        checked_at = now.isoformat()

        today = now.date().isoformat()
        phase = get_session_phase(now)

        for r in rules.get("rules", []):
            if r.get("rung") and not r.get("rearm"):
                continue
            sym = r.get("symbol")
            atype = r.get("type")
            date_filter = r.get("date")
            if date_filter and date_filter != today:
                continue

            fired = False
            msg = ""

            if atype == "opening_bell":
                if phase == "orb" and not state.get(sym + "|opening_bell|" + today):
                    fired = True
                    msg = "NSE opening bell (09:15 IST)"

            elif atype == "time":
                if r.get("at"):
                    hh, mm = r["at"].split(":")
                    at_t = datetime.time(int(hh), int(mm))
                    now_t = now.time()
                    # Ring once when clock passes the time
                    key = sym + "|time|" + r["at"] + "|" + today
                    if now_t >= at_t and not state.get(key):
                        fired = True
                        msg = r.get("label") or ("%s IST reminder" % r["at"])

            elif atype in ("above", "below", "target", "stop") and r.get("price") is not None:
                q = upstox_data.get_quote(sym)
                if not q:
                    continue
                price = q.get("price")
                threshold = r["price"]
                key = sym + "|" + atype + "|" + str(threshold) + "|" + today
                if atype in ("above", "target"):
                    if price is not None and price >= threshold and not state.get(key):
                        fired = True
                        msg = "%s at or above ₹%s (current ₹%s)" % (sym, threshold, price)
                elif atype in ("below", "stop"):
                    if price is not None and price <= threshold and not state.get(key):
                        fired = True
                        msg = "%s at or below ₹%s (current ₹%s)" % (sym, threshold, price)

            elif atype == "pct_move" and r.get("pct") is not None:
                q = upstox_data.get_quote(sym)
                if not q:
                    continue
                price = q.get("price")
                prev = q.get("previousClose") or price
                if prev and price is not None and prev > 0:
                    move_pct = ((price - prev) / prev) * 100
                    key = sym + "|pct_move|" + str(r["pct"]) + "|" + today
                    direction = r.get("ref") or ("up" if move_pct >= 0 else "down")
                    if abs(move_pct) >= r["pct"] and not state.get(key):
                        fired = True
                        msg = "%s moved %.2f%% %s from previous close ₹%s (current ₹%s)" % (
                            sym, abs(move_pct), direction, prev, price)

            if fired:
                r["rung"] = True
                r["rung_at"] = checked_at
                rang.append({
                    "id": r.get("id"),
                    "symbol": sym,
                    "type": atype,
                    "message": msg,
                    "rung_at": checked_at,
                })
                state_key = r.get("id") or sym + "|" + atype
                state[state_key] = True

        # Persist updated rules (rung flags) and state
        _save_json(ALERTS_FILE, rules)
        _save_json(ALERT_STATE_FILE, state)

        return {"rang": rang, "checked_at": checked_at}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
