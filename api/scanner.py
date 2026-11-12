"""Market Scanner API (port of trader-scanner from Indian Day Trader).

Scans Nifty 50 charts for setups on NSE/BSE:
  - Daily pre-market setups (breakout_20d, bull_flag, reclaim_ma20, oversold, oversold_bounce)
  - Opening-range breakout (ORB) intraday scans

Endpoints:
  GET  /api/scanner/universe     Nifty 50 universe list
  POST /api/scanner/daily        Pre-market daily setups
  POST /api/scanner/orb          Intraday ORB breakouts
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
from core.data_fetcher import NIFTY50_SYMBOLS, ALL_SYMBOLS
from core.trader_core import (
    IST,
    get_default_calendar,
    is_trading_day,
)
from core.auth import verify_api_key

router = APIRouter(prefix="/api/scanner", tags=["scanner"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SCANS_FILE = os.path.join(DATA_DIR, "scanner_scans.json")

DEFAULT_PRICE_FLOOR = 50.0
MIN_RANGE_RATIO = 0.003
MAX_RANGE_RATIO = 0.030
MIN_DAILY_BARS = 30
DEFAULT_MIN_VOLUME = 100000

SETUPS = [
    ("breakout_20d", "20-day closing-high breakout"),
    ("bull_flag", "bull flag"),
    ("reclaim_ma20", "reclaimed the 20-day average"),
    ("oversold", "oversold (RSI under 30)"),
    ("oversold_bounce", "oversold bounce"),
]
LABEL = dict(SETUPS)

OPEN = datetime.time(9, 15)
CLOSE = datetime.time(15, 30)
BAR_MIN = 5


class ScannerError(Exception):
    pass


class DailyScanRequest(BaseModel):
    symbols: Optional[list[str]] = None
    min_price: float = DEFAULT_PRICE_FLOOR
    min_volume: int = DEFAULT_MIN_VOLUME
    limit: Optional[int] = None


class OrbScanRequest(BaseModel):
    symbols: Optional[list[str]] = None
    or_minutes: int = 15
    min_price: float = DEFAULT_PRICE_FLOOR
    min_volume: int = 0
    min_range_ratio: float = MIN_RANGE_RATIO
    max_range_ratio: float = MAX_RANGE_RATIO
    max_confirm: int = 200
    at: Optional[str] = None  # HH:MM IST cutoff
    until: Optional[str] = None  # HH:MM IST no entries after


def _save_scan(doc: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = SCANS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, SCANS_FILE)


def rsi(closes, n=14):
    """Wilder's RSI on closes."""
    if len(closes) < n + 1:
        return None
    g = [max(0.0, closes[i] - closes[i - 1]) for i in range(1, len(closes))]
    lo = [max(0.0, closes[i - 1] - closes[i]) for i in range(1, len(closes))]
    ag, al = sum(g[:n]) / n, sum(lo[:n]) / n
    for i in range(n, len(g)):
        ag = (ag * (n - 1) + g[i]) / n
        al = (al * (n - 1) + lo[i]) / n
    return 100 - 100 / (1 + ag / al) if al else 100.0


def find_setups(closes):
    """closes (oldest first, >= 30) -> (setup keys, numbers)."""
    c = closes
    last = c[-1]
    hi20 = max(c[-21:-1])
    ma20 = sum(c[-20:]) / 20.0
    ma20_prev = sum(c[-21:-1]) / 20.0
    run = c[-6] / c[-16] - 1 if len(c) >= 16 else 0
    rng5 = (max(c[-5:]) - min(c[-5:])) / last if last else 0
    r = rsi(c)
    r_prev = rsi(c[:-1])
    tags = []
    if last > hi20:
        tags.append("breakout_20d")
    if run > 0.10 and rng5 < 0.05:
        tags.append("bull_flag")
    if c[-2] < ma20_prev and last > ma20:
        tags.append("reclaim_ma20")
    if r is not None and r < 30:
        tags.append("oversold")
    if r_prev is not None and r_prev < 30 and last > c[-2]:
        tags.append("oversold_bounce")
    return tags, {
        "rsi": r,
        "rsi_prev": r_prev,
        "high20": hi20,
        "ma20": ma20,
        "run_pct": run * 100,
        "range5_pct": rng5 * 100,
    }


@router.get("/universe")
def scanner_universe():
    """Return the Nifty 50 universe (symbol, name)."""
    from core.data_fetcher import ALL_SYMBOLS, SECTOR_MAP
    universe = []
    for sym in ALL_SYMBOLS:
        name = sym.replace(".NS", "")
        universe.append({
            "symbol": sym,
            "name": name,
            "sector": SECTOR_MAP.get(sym, "Unknown"),
        })
    return {"count": len(universe), "universe": universe}


@router.post("/daily")
def scanner_daily(req: DailyScanRequest, auth: bool = Depends(verify_api_key)):
    """Pre-market daily setups scan across Nifty 50 (daily closes)."""
    try:
        now = datetime.datetime.now(IST)
        cal = get_default_calendar()
        if not cal.is_trading_day(now.date()):
            raise ScannerError("Market is closed today (%s). Daily scan runs on trading days." % now.date())

        symbols = req.symbols or ALL_SYMBOLS
        if req.limit:
            symbols = symbols[:req.limit]

        hits = []
        counts = {"requested": len(symbols), "fetched": 0, "illiquid": 0, "short": 0, "scanned": 0, "hits": 0}

        for sym in symbols:
            clean = sym.replace(".NS", "")
            df = upstox_data.get_stock_data(sym, period="1y", interval="1d")
            counts["fetched"] += 1
            if df is None or df.empty or len(df) < MIN_DAILY_BARS:
                counts["short"] += 1
                continue

            closes = [float(x) for x in df["Close"].tolist()]
            highs = [float(x) for x in df["High"].tolist()]
            lows = [float(x) for x in df["Low"].tolist()]
            dates = df.index.tolist()

            last_close = closes[-1]
            last_date = dates[-1]
            if hasattr(last_date, "strftime"):
                last_date_str = last_date.strftime("%Y-%m-%d")
            else:
                last_date_str = str(last_date)[:10]

            # Price / volume floor
            info = upstox_data.get_quote(sym)
            price = info.get("price") if info else last_close
            volume = info.get("volume") if info else 0
            if price is None or price < req.min_price:
                counts["illiquid"] += 1
                continue
            if req.min_volume > 0 and (volume is None or volume < req.min_volume):
                counts["illiquid"] += 1
                continue

            counts["scanned"] += 1
            tags, nums = find_setups(closes)
            if tags:
                hits.append({
                    "symbol": sym,
                    "setups": tags,
                    "price": round(last_close, 2),
                    "close_date": last_date_str,
                    "rsi": round(nums["rsi"], 1) if nums["rsi"] is not None else None,
                    "volume": int(volume) if volume else None,
                    "high20": round(nums["high20"], 2),
                    "ma20": round(nums["ma20"], 2),
                })

        hits.sort(key=lambda h: (-(h["price"] * (h["volume"] or 0)), h["symbol"]))
        counts["hits"] = len(hits)

        doc = {
            "created_by": "trader-scanner",
            "created_at": now.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "mode": "daily",
            "as_of": last_date_str if hits else None,
            "universe": len(symbols),
            "scanned": counts["scanned"],
            "failed": counts["requested"] - counts["fetched"],
            "source": "upstox",
            "filters": {"min_price": req.min_price, "min_volume": req.min_volume},
            "note": "A scan is a list of charts that match a rule, not a list of stocks to buy.",
            "hits": hits,
            "counts": counts,
        }
        _save_scan(doc)
        return doc
    except ScannerError as se:
        raise HTTPException(status_code=400, detail=str(se))


@router.post("/orb")
def scanner_orb(req: OrbScanRequest, auth: bool = Depends(verify_api_key)):
    """Intraday opening-range breakout (ORB) scan across Nifty 50."""
    try:
        now = datetime.datetime.now(IST)
        cal = get_default_calendar()
        if not cal.is_trading_day(now.date()):
            raise ScannerError("Market is closed today. ORB scan runs on trading days.")

        # Parse cutoff time
        cutoff = now
        if req.at:
            try:
                hh, mm = req.at.split(":")
                cutoff = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
            except ValueError:
                raise ScannerError("--at wants an IST time like 10:15")
        if req.until:
            try:
                uh, um = req.until.split(":")
                until_t = datetime.time(int(uh), int(um))
                if cutoff.time() > until_t:
                    raise ScannerError("It is %s IST, after %s: no new entries." % (cutoff.strftime("%H:%M"), req.until))
            except ValueError:
                raise ScannerError("--until wants an IST time like 15:00")

        day = now.date()
        or_end = datetime.datetime.combine(day, OPEN, tzinfo=IST) + datetime.timedelta(minutes=req.or_minutes)
        first_close = or_end + datetime.timedelta(minutes=BAR_MIN)

        if cutoff < first_close:
            raise ScannerError(
                "It is %s IST: the %d-minute opening range runs 09:15 to %s and the first bar after it closes at %s."
                % (cutoff.strftime("%H:%M"), req.or_minutes, or_end.strftime("%H:%M"), first_close.strftime("%H:%M"))
            )

        n_range = req.or_minutes // BAR_MIN
        symbols = req.symbols or ALL_SYMBOLS
        if req.max_confirm:
            symbols = symbols[:req.max_confirm]

        hits = []
        counts = {"requested": len(symbols), "fetched": 0, "usable": 0, "illiquid": 0, "scanned": 0,
                  "candidates": 0, "confirmed": 0, "hits": 0}

        for sym in symbols:
            counts["fetched"] += 1
            df = upstox_data.get_stock_data(sym, period="1d", interval="5m")
            if df is None or df.empty:
                continue

            # Filter to today's session bars
            today_bars = []
            for idx, row in df.iterrows():
                ts = idx
                if hasattr(ts, "strftime"):
                    ts_str = ts.strftime("%Y-%m-%d %H:%M")
                else:
                    ts_str = str(ts)[:16]
                if not ts_str.startswith(day.isoformat()):
                    continue
                try:
                    bar_dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M").replace(tzinfo=IST)
                except ValueError:
                    continue
                if bar_dt.time() < OPEN or bar_dt.time() >= CLOSE:
                    continue
                today_bars.append({
                    "start": bar_dt,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]) if "Volume" in row and row["Volume"] is not None else 0,
                    "slot": int((bar_dt - datetime.datetime.combine(day, OPEN, tzinfo=IST)).total_seconds() // (BAR_MIN * 60)),
                })

            if not today_bars:
                continue
            counts["usable"] += 1

            # Check range completeness
            range_bars = [b for b in today_bars if b["slot"] < n_range]
            if len(range_bars) < n_range:
                continue

            # Last price / volume filter
            last_bar = today_bars[-1]
            info = upstox_data.get_quote(sym)
            price = info.get("price") if info else last_bar["close"]
            volume = sum(b["volume"] for b in today_bars)
            if price is None or price < req.min_price:
                counts["illiquid"] += 1
                continue
            if req.min_volume > 0 and volume < req.min_volume:
                counts["illiquid"] += 1
                continue

            counts["scanned"] += 1

            # ORB candidate: range high/low filters
            rng = range_bars
            oh = max(b["high"] for b in rng)
            ol = min(b["low"] for b in rng)
            if ol <= 0 or oh < req.min_price:
                continue
            ratio = (oh - ol) / ol
            if not (req.min_range_ratio <= ratio <= req.max_range_ratio):
                continue
            counts["candidates"] += 1

            # Find first bar after range closing strictly above range high
            hit = None
            for b in today_bars:
                if b["slot"] < n_range:
                    continue
                if b["close"] > oh:
                    closes_at = b["start"] + datetime.timedelta(minutes=BAR_MIN)
                    hit = {
                        "symbol": sym,
                        "setups": ["orb"],
                        "price": round(b["close"], 2),
                        "at": closes_at.strftime("%I:%M %p"),
                        "bar_start": b["start"].strftime("%H:%M"),
                        "bar_index": b["slot"],
                        "or_high": round(oh, 2),
                        "or_low": round(ol, 2),
                        "range_size": round(oh - ol, 2),
                        "range_ratio_pct": round(ratio * 100, 2),
                        "pct_over": round((b["close"] / oh - 1) * 100, 2),
                    }
                    break

            if hit:
                hits.append(hit)
                counts["confirmed"] += 1

        hits.sort(key=lambda x: x["bar_start"])
        counts["hits"] = len(hits)

        doc = {
            "created_by": "trader-scanner",
            "created_at": now.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "mode": "orb",
            "as_of": "%s %s IST" % (day.isoformat(), cutoff.strftime("%H:%M")),
            "universe": len(symbols),
            "scanned": counts["scanned"],
            "failed": counts["requested"] - counts["fetched"],
            "source": "upstox",
            "or_minutes": req.or_minutes,
            "interval": "5m",
            "filters": {
                "min_price": req.min_price,
                "min_volume": req.min_volume,
                "min_range_ratio": req.min_range_ratio,
                "max_range_ratio": req.max_range_ratio,
            },
            "note": "A scan is a list of charts that match a rule, not a list of stocks to buy.",
            "hits": hits,
            "counts": counts,
        }
        _save_scan(doc)
        return doc
    except ScannerError as se:
        raise HTTPException(status_code=400, detail=str(se))
