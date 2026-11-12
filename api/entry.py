"""Entry Timer API (port of trader-entry from Indian Day Trader).

Watches a setup bar by bar and reports the moment to get in:
  - ORB: first completed bar after the range that CLOSES strictly above the
    range high AND has volume >= 1.25x the opening-range average volume.
  - Level: first completed bar closing above a given price.

Endpoints:
  POST /api/entry/check        Check a symbol's entry status right now
"""

from __future__ import annotations

import datetime
import json
import os
import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from core import upstox_data
from core.trader_core import (
    IST,
    validate_candle,
    Candle,
    get_default_calendar,
    is_trading_day,
)
from core.auth import verify_api_key

router = APIRouter(prefix="/api/entry", tags=["entry-timer"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ENTRY_FILE = os.path.join(DATA_DIR, "entry.json")

DEFAULTS = {"no_entries_before": "09:30", "no_entries_after": "14:30"}
DEFAULT_MIN_VOLUME_X = 1.25
INTERVALS = {"1m": 60, "5m": 300}
OPEN = datetime.time(9, 15)
CLOSE = datetime.time(15, 30)


class EntryError(Exception):
    pass


class EntryCheckRequest(BaseModel):
    symbol: str = "RELIANCE.NS"
    setup: str = "orb"  # orb, level
    or_minutes: int = 15
    interval: str = "5m"  # 5m, 1m
    level: Optional[float] = None
    min_volume_x: float = DEFAULT_MIN_VOLUME_X


class EntryCheckResponse(BaseModel):
    symbol: str
    setup: str
    side: str
    date: str
    interval: str
    or_minutes: int
    now: str
    status: str
    phase: str
    reason: str
    opening_range: Optional[dict] = None
    level: Optional[float] = None
    trigger: Optional[dict] = None
    last: Optional[dict] = None
    forming: Optional[dict] = None


def _load_entry_history() -> list:
    """Triggered-entry history (oldest first). Migrates the old single-doc file."""
    if not os.path.exists(ENTRY_FILE):
        return []
    try:
        with open(ENTRY_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return []
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _save_entry(doc: dict) -> None:
    """Append a triggered entry to the history (newest last), capped at 50."""
    history = _load_entry_history()
    history.append(doc)
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = ENTRY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(history[-50:], fh, indent=2)
        fh.write("\n")
    os.replace(tmp, ENTRY_FILE)


def r2(x):
    return None if x is None else round(float(x), 2) + 0.0


def evaluate(chart_bars, now_utc, setup="orb", or_minutes=15, interval="5m",
             level=None, min_volume_x=DEFAULT_MIN_VOLUME_X):
    """Pure function: entry status from one session's 5m/1m bars."""
    cfg = dict(DEFAULTS)
    if min_volume_x is None:
        min_volume_x = DEFAULT_MIN_VOLUME_X
    if interval not in INTERVALS:
        raise EntryError("--interval is 5m or 1m")
    step = INTERVALS[interval]
    if setup not in ("orb", "level"):
        raise EntryError("--setup is orb or level")
    if setup == "level" and level is None:
        raise EntryError("--setup level needs --level PRICE")

    n_or = or_minutes * 60 // step
    local = now_utc.astimezone(IST)
    day = local.date()
    cal = get_default_calendar()

    res = {
        "symbol": chart_bars.get("symbol", ""),
        "setup": setup,
        "side": "buy",
        "date": day.isoformat(),
        "interval": interval,
        "or_minutes": or_minutes,
        "now": local.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "waiting",
        "phase": "",
        "reason": "",
        "opening_range": None,
        "level": None,
        "trigger": None,
        "last": None,
        "forming": None,
        "min_volume_x": min_volume_x,
    }

    ok = is_trading_day(day)
    if not ok:
        res.update(status="no-data", phase="closed", reason="NSE closed today")
        return res

    open_dt = datetime.datetime.combine(day, OPEN, tzinfo=IST)
    close_dt = datetime.datetime.combine(day, CLOSE, tzinfo=IST)
    before = datetime.datetime.combine(day, datetime.time(9, 30), tzinfo=IST)
    cutoff = datetime.datetime.combine(day, datetime.time(14, 30), tzinfo=IST)
    or_end = open_dt + datetime.timedelta(minutes=or_minutes)

    res.update(
        opens="09:15", closes="15:30",
        no_entries_before="09:30", no_entries_after="14:30",
    )

    # Build bars by slot
    by_slot = {}
    bars_raw = chart_bars.get("data", [])
    for row in bars_raw:
        ts_str = row.get("date", "")
        try:
            if " " in ts_str:
                bar_dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M").replace(tzinfo=IST)
            else:
                bar_dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d").replace(tzinfo=IST)
        except ValueError:
            continue
        if bar_dt.date() != day or not (open_dt <= bar_dt < close_dt):
            continue
        slot = int((bar_dt - open_dt).total_seconds() // step)
        by_slot[slot] = {
            "o": float(row.get("open", 0)),
            "h": float(row.get("high", 0)),
            "l": float(row.get("low", 0)),
            "c": float(row.get("close", 0)),
            "v": int(row.get("volume", 0) or 0),
            "et": bar_dt,
            "end": bar_dt + datetime.timedelta(seconds=step),
            "slot": slot,
            "t": int(bar_dt.timestamp()),
        }

    bars, pending = [], None
    now_ts = int(local.timestamp())
    for slot in sorted(by_slot):
        b = by_slot[slot]
        end_ts = b["t"] + step
        if end_ts <= now_ts:
            c_obj = Candle(
                timestamp=b["et"], open=b["o"], high=b["h"], low=b["l"],
                close=b["c"], volume=b["v"], is_complete=True,
            )
            valid, _ = validate_candle(c_obj, require_complete=True, interval_seconds=step,
                                       validate_alignment=True, allow_zero_volume=True,
                                       current_time=local)
            if valid:
                bars.append(b)
            else:
                pending = b
                res["forming"] = {"bar_start": b["et"].strftime("%H:%M"),
                                  "closes": b["end"].strftime("%I:%M %p"),
                                  "price": r2(b["c"])}
        elif b["et"] <= local:
            res["forming"] = {"bar_start": b["et"].strftime("%H:%M"),
                              "closes": b["end"].strftime("%I:%M %p"),
                              "price": r2(b["c"])}

    if local < open_dt:
        res.update(phase="pre-open",
                   reason="NSE opens at 09:15 IST")
        return res

    or_bars = [b for b in bars if b["slot"] < n_or]
    avg_vol = (sum(b["v"] for b in or_bars) / float(len(or_bars))) if or_bars else None
    if or_bars:
        res["opening_range"] = {
            "high": r2(max(b["h"] for b in or_bars)),
            "low": r2(min(b["l"] for b in or_bars)),
            "minutes": or_minutes,
            "bars": len(or_bars),
            "of": n_or,
            "complete": local >= or_end,
            "avg_volume": int(round(avg_vol)) if avg_vol else 0,
        }

    if setup == "orb":
        if local < or_end:
            res.update(phase="forming",
                       reason="%d of %d range bars closed; range set at %s" % (
                           len(or_bars), n_or, or_end.strftime("%H:%M")))
            return res
        if not or_bars:
            res.update(status="no-data", phase="open", reason="No bars available for the opening range")
            return res
        lvl = max(b["h"] for b in or_bars)
    else:
        lvl = float(level)
    res["level"] = r2(lvl)

    first_slot = n_or if setup == "orb" else 0
    trig, thin = None, []
    for b in bars:
        if b["slot"] < first_slot or b["end"] < before or b["end"] > cutoff:
            continue
        if b["c"] > lvl:
            vx = (b["v"] / avg_vol) if avg_vol else None
            if min_volume_x and (vx is None or vx < min_volume_x):
                thin.append(b)
                continue
            trig = b
            break

    last = bars[-1] if bars else None
    if last:
        res["last"] = {
            "bar_start": last["et"].strftime("%H:%M"),
            "close": r2(last["c"]),
            "vs_level_pct": r2(100.0 * (last["c"] / lvl - 1)),
        }

    if trig:
        vx = (trig["v"] / avg_vol) if avg_vol else None
        res.update(
            status="triggered",
            phase="open" if local < close_dt else "after-close",
            reason="the %s bar closed above %s" % (
                trig["et"].strftime("%H:%M"), "the range high" if setup == "orb" else "the level"),
        )
        res["trigger"] = {
            "time": trig["end"].strftime("%I:%M %p"),
            "close_time": trig["end"].strftime("%H:%M"),
            "bar_start": trig["et"].strftime("%H:%M"),
            "bar_index": trig["slot"],
            "price": r2(trig["c"]),
            "close": trig["c"],
            "volume": trig["v"],
            "volume_x": r2(vx),
            "pct_over": r2(100.0 * (trig["c"] / lvl - 1)),
        }
        res["minutes_since"] = int((local - trig["end"]).total_seconds() // 60)
        return res

    if not bars:
        res.update(status="no-data", phase="open", reason="No bars available for %s yet" % day.isoformat())
        return res

    what = "close above the range high ₹%.2f" % lvl if setup == "orb" else "close above ₹%.2f" % lvl
    if local >= cutoff:
        res.update(
            status="expired",
            phase="after-cutoff",
            reason="no %s by %s, the last time for a new entry" % (what, cutoff.strftime("%H:%M")),
        )
        return res

    res["phase"] = "open"
    if last and last["c"] > lvl and last in thin:
        avg = res.get("opening_range", {}).get("avg_volume")
        res["reason"] = "the %s bar closed above at ₹%.2f but on %.2fx the range's volume, under your %.2fx" % (
            last["et"].strftime("%H:%M"), last["c"],
            last["v"] / float(avg) if avg else 0, min_volume_x)
    elif last:
        gap = lvl - last["c"]
        res["reason"] = "last close ₹%.2f (%s bar), ₹%.2f %s %s (%+.2f%%)" % (
            last["c"], last["et"].strftime("%H:%M"), abs(gap),
            "under" if gap >= 0 else "over",
            "the range high ₹%.2f" % lvl if setup == "orb" else "the level ₹%.2f" % lvl,
            100.0 * (last["c"] / lvl - 1),
        )
    return res


@router.post("/check", response_model=EntryCheckResponse)
def entry_check(req: EntryCheckRequest, auth: bool = Depends(verify_api_key)):
    """Check a symbol's entry status right now."""
    try:
        sym = req.symbol.upper()
        clean = sym.replace(".NS", "").replace(".BO", "")

        now_utc = datetime.datetime.now(datetime.timezone.utc)

        # Fetch 5m intraday data
        df = upstox_data.get_stock_data(sym, period="1d", interval="5m")
        if df is None or df.empty:
            raise EntryError("No intraday data available for %s" % sym)

        chart = {"symbol": sym, "data": []}
        for idx, row in df.iterrows():
            ts_str = idx.strftime("%Y-%m-%d %H:%M") if hasattr(idx, "strftime") else str(idx)[:16]
            chart["data"].append({
                "date": ts_str,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]) if "Volume" in row and row["Volume"] is not None else 0,
            })

        res = evaluate(chart, now_utc, setup=req.setup, or_minutes=req.or_minutes,
                       interval=req.interval, level=req.level,
                       min_volume_x=req.min_volume_x)

        # Strip internal keys (none in this adapted version)
        public_res = {k: v for k, v in res.items()}

        if req.setup == "orb" and res.get("trigger"):
            _save_entry(public_res)

        return public_res
    except EntryError as ee:
        raise HTTPException(status_code=400, detail=str(ee))


@router.get("/history")
def entry_history(auth: bool = Depends(verify_api_key)):
    """Most recent triggered entries (newest first)."""
    history = _load_entry_history()
    history.reverse()
    return {"entries": history, "count": len(history)}
