"""
Upstox-backed market data layer.

This module replaces yfinance for all Indian market data:
  * real-time / batch quotes
  * historical & intraday candles
  * market depth
  * instrument resolution (via the official Upstox instrument master)
  * option chain
  * instrument news

Fundamentals that Upstox does not expose (P/E, ROE, market cap, ...) are
fetched from the Downstox API.  Everything here is synchronous; an async
bridge lets FastAPI async endpoints use the same helpers safely.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import os
import re
import threading
import time
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from core.cache import stock_cache, price_cache, cached
from core.upstox.client import UpstoxClient

# ---------------------------------------------------------------------------
# Instrument master
# ---------------------------------------------------------------------------

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FULL_INSTRUMENTS_FILE = os.path.join(_BASE_DIR, "data", "upstox_instruments_full.json")
_INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
_INSTRUMENTS_TTL = 7 * 24 * 3600  # refresh weekly

_instruments: Optional[Dict[str, dict]] = None
_instruments_lock = threading.Lock()

_client: Optional[UpstoxClient] = None
_client_lock = threading.Lock()

# Indices / legacy ticker aliases -> Upstox instrument keys
SYMBOL_ALIASES: Dict[str, str] = {
    "^NSEI": "NSE_INDEX|Nifty 50",
    "^NIFTY": "NSE_INDEX|Nifty 50",
    "^NSEBANK": "NSE_INDEX|Nifty Bank",
    "^BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "^BSESN": "BSE_INDEX|SENSEX",
    "^INDIAVIX": "NSE_INDEX|India VIX",
    "^CNXIT": "NSE_INDEX|Nifty IT",
    "^NSEMDCP50": "NSE_INDEX|Nifty Midcap 50",
    "^NSEMDCP100": "NSE_INDEX|Nifty Midcap 50",
    "NIFTY": "NSE_INDEX|Nifty 50",
    "NIFTY 50": "NSE_INDEX|Nifty 50",
    "NIFTY50": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "BANK NIFTY": "NSE_INDEX|Nifty Bank",
    "SENSEX": "BSE_INDEX|SENSEX",
    "INDIA VIX": "NSE_INDEX|India VIX",
    "INDIAVIX": "NSE_INDEX|India VIX",
    "NIFTY IT": "NSE_INDEX|Nifty IT",
    "NIFTYIT": "NSE_INDEX|Nifty IT",
    "NIFTY MIDCAP 50": "NSE_INDEX|Nifty Midcap 50",
    "NIFTY MIDCAP 100": "NSE_INDEX|Nifty Midcap 50",
}

# Index symbols shown on the dashboard / market overview
INDEX_SYMBOLS = [
    "^NSEI",
    "^BSESN",
    "^NSEBANK",
    "^CNXIT",
    "^NSEMDCP50",
]


def _load_env_file() -> None:
    """Load key=value pairs from the project .env without extra dependencies."""
    env_path = os.path.join(_BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


def _download_instruments() -> Dict[str, dict]:
    """Download the official NSE instrument master and keep only equities."""
    req = urllib.request.Request(_INSTRUMENTS_URL, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=60).read()
    records = json.loads(gzip.decompress(raw))

    mapped: Dict[str, dict] = {}
    for rec in records:
        if rec.get("segment") != "NSE_EQ":
            continue
        if rec.get("instrument_type") not in ("EQ", "BE", "BZ"):
            continue
        sym = rec.get("trading_symbol")
        if not sym:
            continue
        mapped[sym.upper()] = {
            "instrument_key": rec.get("instrument_key", ""),
            "name": rec.get("name", sym),
            "isin": rec.get("isin", ""),
            "short_name": rec.get("short_name", sym),
        }
    return mapped


def ensure_instruments() -> Dict[str, dict]:
    """Load the NSE equity instrument map (local cache, weekly refresh)."""
    global _instruments
    if _instruments is not None:
        return _instruments

    with _instruments_lock:
        if _instruments is not None:
            return _instruments

        data: Dict[str, dict] = {}
        try:
            if os.path.exists(_FULL_INSTRUMENTS_FILE):
                if time.time() - os.path.getmtime(_FULL_INSTRUMENTS_FILE) < _INSTRUMENTS_TTL:
                    with open(_FULL_INSTRUMENTS_FILE, "r") as fh:
                        data = json.load(fh)
        except Exception:
            data = {}

        if not data:
            try:
                data = _download_instruments()
                if data:
                    os.makedirs(os.path.dirname(_FULL_INSTRUMENTS_FILE), exist_ok=True)
                    with open(_FULL_INSTRUMENTS_FILE, "w") as fh:
                        json.dump(data, fh)
            except Exception as exc:  # pragma: no cover - network failure path
                print(f"Upstox instrument master unavailable: {exc}")
                data = {}

        _instruments = data
        return _instruments


def get_client() -> UpstoxClient:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _load_env_file()
                ensure_instruments()
                _client = UpstoxClient()
    return _client


# ---------------------------------------------------------------------------
# Async bridge
# ---------------------------------------------------------------------------

def run_async(coro):
    """Run an async coroutine from sync code, even inside a running loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    box: Dict[str, Any] = {}

    def _target():
        try:
            box["value"] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001 - propagate to caller
            box["error"] = exc

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box.get("value")


# ---------------------------------------------------------------------------
# Symbol helpers
# ---------------------------------------------------------------------------

def normalize_symbol(symbol: str) -> str:
    """Convert any legacy/yfinance/Upstox symbol into an Upstox instrument key."""
    if not symbol:
        return ""

    raw = str(symbol).strip()
    if "|" in raw:
        return raw

    upper = raw.upper()
    if upper in SYMBOL_ALIASES:
        return SYMBOL_ALIASES[upper]

    clean = upper.replace(".NS", "").replace(".BO", "").strip()
    if clean in SYMBOL_ALIASES:
        return SYMBOL_ALIASES[clean]

    instruments = ensure_instruments()
    entry = instruments.get(clean)
    if entry:
        return entry["instrument_key"]

    # BSE indices / unknown symbols: keep a deterministic fallback
    if clean.startswith("^"):
        return f"NSE_INDEX|{clean.lstrip('^')}"
    return f"NSE_EQ|{clean}"


def canonical_symbol(symbol: str) -> str:
    """Return a clean equity ticker, e.g. RELIANCE.NS -> RELIANCE."""
    raw = str(symbol or "").strip()
    if "|" in raw:
        raw = raw.split("|")[-1]
    return raw.upper().replace(".NS", "").replace(".BO", "").strip()


def to_display_symbol(symbol: str) -> str:
    """Normalise any input to the `TICKER.NS` convention used by the app."""
    if not symbol:
        return ""
    raw = str(symbol).strip()
    if raw.startswith("^") or "|" in raw:
        return raw
    clean = canonical_symbol(raw)
    return f"{clean}.NS"


def instrument_name(symbol: str) -> str:
    clean = canonical_symbol(symbol)
    entry = ensure_instruments().get(clean)
    if entry:
        return entry.get("short_name") or entry.get("name") or clean
    return clean


def instrument_display_name(symbol: str) -> str:
    """Best display name for UI lists.

    Upstox master short name first; falls back to the full name (suffix
    stripped) when the short name is missing or is just the ticker, and
    finally to the Downstox profile for symbols not in the master at all.
    """
    clean = canonical_symbol(symbol)
    entry = ensure_instruments().get(clean)
    if entry:
        short = entry.get("short_name") or ""
        if short and short != clean:
            return short
        full = (entry.get("name") or "").strip()
        full = re.sub(r"\s+(LIMITED|LTD\.?)\s*$", "", full, flags=re.IGNORECASE)
        if full:
            return full
    profile = get_stock_profile(symbol)
    if profile.get("name"):
        return profile["name"]
    return clean


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------

def _quote_to_legacy(symbol: str, quote: dict) -> dict:
    last = float(quote.get("last_price") or 0.0)
    prev = float(quote.get("close") or 0.0)
    change = float(quote.get("net_change") or 0.0)
    if not change:
        change = round(last - prev, 2)
    change_pct = quote.get("change_percent")
    if change_pct is None:
        change_pct = round((change / prev) * 100, 2) if prev else 0.0
    return {
        "symbol": symbol,
        "price": round(last, 2),
        "previousClose": round(prev, 2),
        "open": round(float(quote.get("open") or 0.0), 2),
        "dayHigh": round(float(quote.get("high") or 0.0), 2),
        "dayLow": round(float(quote.get("low") or 0.0), 2),
        "volume": int(quote.get("volume") or 0),
        "change": round(change, 2),
        "changePercent": round(float(change_pct or 0.0), 2),
        "vwap": round(float(quote.get("vwap") or 0.0), 2),
        "timestamp": quote.get("timestamp", ""),
    }


def get_quotes(symbols: List[str]) -> Dict[str, dict]:
    """Fetch batch quotes. Keys are the symbols as passed in."""
    if not symbols:
        return {}
    client = get_client()
    quotes = run_async(client.get_quotes(list(symbols))) or {}

    result: Dict[str, dict] = {}
    for sym in symbols:
        clean = canonical_symbol(sym)
        quote = quotes.get(sym) or quotes.get(clean)
        if quote:
            result[sym] = _quote_to_legacy(sym, quote)
    return result


def get_quote(symbol: str) -> Optional[dict]:
    quotes = get_quotes([symbol])
    return quotes.get(symbol)


@cached(price_cache)
def get_live_price(symbol: str) -> Optional[dict]:
    return get_quote(symbol)


def get_market_indices(symbols: Optional[List[str]] = None) -> Dict[str, dict]:
    symbols = symbols or INDEX_SYMBOLS
    quotes = get_quotes(symbols)
    labels = {
        "^NSEI": "NIFTY 50",
        "^BSESN": "SENSEX",
        "^NSEBANK": "BANK NIFTY",
        "^CNXIT": "NIFTY IT",
        "^NSEMDCP50": "NIFTY MIDCAP 50",
    }
    out: Dict[str, dict] = {}
    for sym in symbols:
        q = quotes.get(sym)
        if q:
            q = dict(q)
            q["name"] = labels.get(sym, sym)
            out[sym] = q
    return out


def get_top_movers(symbols: List[str], limit: int = 5) -> dict:
    quotes = get_quotes(symbols)
    rows = list(quotes.values())
    gainers = sorted(rows, key=lambda q: q.get("changePercent", 0), reverse=True)[:limit]
    losers = sorted(rows, key=lambda q: q.get("changePercent", 0))[:limit]
    return {"gainers": gainers, "losers": losers}


# ---------------------------------------------------------------------------
# Candles
# ---------------------------------------------------------------------------

_PERIOD_DAYS = {
    "1d": 3,
    "5d": 10,
    "1mo": 35,
    "3mo": 100,
    "6mo": 200,
    "1y": 400,
    "2y": 750,
    "5y": 1900,
    "10y": 3700,
    "ytd": 400,
    "max": 3700,
    # Intraday periods: only recent days are available for intraday bars
    "5m": 1,
    "15m": 1,
    "30m": 1,
    "1h": 1,
}

_INTERVAL_MAP = {
    "1m": "1minute",
    "5m": "1minute",
    "15m": "1minute",
    "30m": "30minute",
    "1h": "30minute",
    "1d": "day",
    "1wk": "week",
    "1mo": "month",
    "day": "day",
    "week": "week",
    "month": "month",
}

_RESAMPLE_RULE = {"5m": "5min", "15m": "15min", "1h": "60min"}


@cached(stock_cache)
def get_stock_data(symbol: str, period: str = "6mo", interval: str = "1d") -> Optional[pd.DataFrame]:
    """Return an OHLCV DataFrame with the same shape yfinance used to return."""
    client = get_client()
    days = _PERIOD_DAYS.get(period, 200)
    today = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    upstox_interval = _INTERVAL_MAP.get(interval, "day")
    # Intraday intervals: Upstox historical-candle endpoint with from_date/to_date
    # range returns empty. Use to_date only (recent intraday data) instead.
    is_intraday = interval in ("1m", "5m", "15m", "30m", "1h")

    try:
        raw = run_async(
            client.get_candles(
                symbol,
                interval=upstox_interval,
                to_date=today,
                **({"from_date": from_date} if not is_intraday else {}),
            )
        )
    except Exception as exc:
        print(f"Error fetching {symbol}: {exc}")
        return None

    if not raw:
        return None

    df = pd.DataFrame(raw)
    if df.empty or "close" not in df.columns:
        return None

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("Asia/Kolkata")
    df = df.set_index("timestamp").sort_index()
    df = df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )

    if interval in _RESAMPLE_RULE:
        df = (
            df.resample(_RESAMPLE_RULE[interval])
            .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
            .dropna(subset=["Open", "Close"])
        )

    df = df[["Open", "High", "Low", "Close", "Volume"]].astype({"Volume": "int64"})
    if interval in ("1d", "1wk", "1mo", "day", "week", "month"):
        df.index = df.index.strftime("%Y-%m-%d")
    else:
        df.index = df.index.strftime("%Y-%m-%d %H:%M")
    return df.copy()


# ---------------------------------------------------------------------------
# Fundamentals (Upstox + Downstox)
# ---------------------------------------------------------------------------

def _downstox_stock(symbol: str) -> dict:
    try:
        from core.downstox import get_stock_detail

        payload = get_stock_detail(canonical_symbol(symbol))
        if isinstance(payload, dict) and payload.get("success"):
            return payload
    except Exception:
        pass
    return {}


@cached(stock_cache)
def get_stock_profile(symbol: str) -> dict:
    """Display name + sector from Downstox fundamentals (cached 5 min).

    Fallback for symbols the Upstox instrument map lacks (or names too
    generically), and for sectors the static SECTOR_MAP doesn't cover.
    """
    payload = _downstox_stock(symbol) or {}
    stock = payload.get("stock") or {}
    name = (stock.get("name") or "").strip()
    name = re.sub(r"\s+(LIMITED|LTD\.?)\s*$", "", name, flags=re.IGNORECASE)
    return {
        "name": name,
        "sector": payload.get("sector") or stock.get("sector") or "Others",
    }


@cached(stock_cache)
def get_stock_info(symbol: str) -> Optional[dict]:
    """Combined fundamentals + live snapshot for a stock."""
    display = to_display_symbol(symbol)
    clean = canonical_symbol(symbol)
    payload = _downstox_stock(symbol)
    stock = payload.get("stock", {}) if payload else {}
    fundamentals = payload.get("fundamentals", {}) if payload else {}

    quote = get_quote(display) or {}

    high_52 = low_52 = None
    try:
        yearly = get_stock_data(display, period="1y", interval="1d")
        if yearly is not None and not yearly.empty:
            high_52 = round(float(yearly["High"].max()), 2)
            low_52 = round(float(yearly["Low"].min()), 2)
    except Exception:
        pass

    mcap_crore = fundamentals.get("mcap")
    market_cap = int(mcap_crore * 1e7) if mcap_crore else 0
    div_yield = fundamentals.get("divYield")
    if div_yield is not None:
        div_yield = float(div_yield) / 100.0

    sector = payload.get("sector") or stock.get("sector") or "Unknown"
    name = stock.get("name") or instrument_name(symbol)

    if not name and not quote:
        return None

    return {
        "symbol": display,
        "name": name,
        "sector": sector,
        "industry": sector,
        "marketCap": market_cap,
        "pe": fundamentals.get("pe"),
        "pb": fundamentals.get("priceToBook"),
        "dividendYield": div_yield,
        "roe": fundamentals.get("roe"),
        "roce": fundamentals.get("roce"),
        "bookValue": fundamentals.get("bookValue"),
        "fiftyTwoWeekHigh": high_52,
        "fiftyTwoWeekLow": low_52,
        "currentPrice": quote.get("price") or fundamentals.get("cmp"),
        "previousClose": quote.get("previousClose") or payload.get("live", {}).get("previousClose"),
        "open": quote.get("open") or payload.get("live", {}).get("open"),
        "dayHigh": quote.get("dayHigh") or payload.get("live", {}).get("high"),
        "dayLow": quote.get("dayLow") or payload.get("live", {}).get("low"),
        "volume": quote.get("volume") or payload.get("live", {}).get("volume"),
        "isin": stock.get("isin"),
        "instrumentKey": stock.get("instrumentToken"),
    }


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_stocks(query: str) -> List[dict]:
    query = (query or "").upper().strip()
    if not query:
        return []

    instruments = ensure_instruments()
    scored: List[tuple] = []
    for sym, entry in instruments.items():
        name = entry.get("name", sym)
        short = entry.get("short_name", "")
        name_u = name.upper()
        short_u = short.upper()

        if sym == query:
            score = 0
        elif sym.startswith(query):
            score = 1
        elif short_u.startswith(query):
            score = 2
        elif query in sym:
            score = 3
        elif query in name_u or query in short_u:
            score = 4
        else:
            continue
        scored.append((score, sym, entry))

    scored.sort(key=lambda row: (row[0], row[1]))
    return [
        {
            "symbol": f"{sym}.NS",
            "name": entry.get("name", sym),
            "exchange": "NSE",
            "sector": "Unknown",
        }
        for _, sym, entry in scored[:15]
    ]


# ---------------------------------------------------------------------------
# Option chain
# ---------------------------------------------------------------------------

def _option_expiries(instrument_key: str) -> List[str]:
    client = get_client()
    url = f"https://api.upstox.com/v2/option/contract"
    params = {"instrument_key": instrument_key}
    import httpx

    try:
        resp = httpx.get(url, params=params, headers=client._get_headers(), timeout=15.0)
        if resp.status_code != 200:
            return []
        data = resp.json().get("data", [])
        return sorted({row.get("expiry") for row in data if row.get("expiry")})
    except Exception:
        return []


def get_option_chain(symbol: str = "^NSEI", expiry: Optional[str] = None) -> dict:
    """Fetch the Upstox option chain, sorted by strike."""
    client = get_client()
    instrument_key = normalize_symbol(symbol)
    expiries = _option_expiries(instrument_key)
    if not expiries:
        return {"error": "No option contracts available", "calls": [], "puts": []}

    if expiry not in expiries:
        expiry = expiries[0]

    import httpx

    try:
        resp = httpx.get(
            "https://api.upstox.com/v2/option/chain",
            params={"instrument_key": instrument_key, "expiry_date": expiry},
            headers=client._get_headers(),
            timeout=20.0,
        )
        if resp.status_code != 200:
            return {"error": resp.text[:200], "calls": [], "puts": []}
        rows = resp.json().get("data", [])
    except Exception as exc:
        return {"error": str(exc), "calls": [], "puts": []}

    calls, puts = [], []
    spot = 0.0
    for row in rows:
        spot = row.get("underlying_spot_price") or spot
        strike = float(row.get("strike_price") or 0)
        for leg, bucket in (("call_options", calls), ("put_options", puts)):
            data = row.get(leg) or {}
            md = data.get("market_data") or {}
            greeks = data.get("option_greeks") or {}
            bucket.append(
                {
                    "strike": strike,
                    "lastPrice": float(md.get("ltp") or 0),
                    "change": round(float(md.get("ltp") or 0) - float(md.get("close_price") or 0), 2),
                    "volume": int(md.get("volume") or 0),
                    "openInterest": float(md.get("oi") or 0),
                    "impliedVolatility": float(greeks.get("iv") or 0),
                    "instrumentKey": data.get("instrument_key"),
                }
            )

    calls.sort(key=lambda x: x["strike"])
    puts.sort(key=lambda x: x["strike"])
    total_call_oi = sum(c["openInterest"] for c in calls)
    total_put_oi = sum(p["openInterest"] for p in puts)
    pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi else 0.0

    return {
        "underlying": canonical_symbol(symbol),
        "currentPrice": round(float(spot), 2),
        "expiry": expiry,
        "availableExpiries": expiries,
        "calls": calls,
        "puts": puts,
        "putCallRatio": pcr,
        "totalCallOI": total_call_oi,
        "totalPutOI": total_put_oi,
        "timestamp": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def get_instrument_news(symbol: str, limit: int = 10) -> List[dict]:
    """Stock-specific news from Upstox."""
    client = get_client()
    key = normalize_symbol(symbol)
    import httpx

    try:
        resp = httpx.get(
            "https://api.upstox.com/v2/news",
            params={"category": "instrument_keys", "instrument_keys": key},
            headers=client._get_headers(),
            timeout=15.0,
        )
        if resp.status_code != 200:
            return []
        payload = resp.json().get("data", {})
        items = payload.get(key) or []
        if not items and isinstance(payload, list):
            items = payload
        return [
            {
                "title": item.get("heading") or item.get("title", ""),
                "publisher": "Upstox",
                "link": item.get("url") or item.get("link", ""),
                "publishedAt": item.get("published_time") or item.get("published_at", ""),
                "summary": item.get("summary", ""),
            }
            for item in items[:limit]
        ]
    except Exception:
        return []


def get_market_news(limit: int = 20) -> List[dict]:
    """Market-wide news from Downstox."""
    try:
        from core.downstox import _fetch

        payload = _fetch("/news")
        if not payload:
            return []
        articles = payload.get("articles", []) if isinstance(payload, dict) else []
        return [
            {
                "title": a.get("title", ""),
                "publisher": a.get("source") or a.get("publisher", ""),
                "link": a.get("url") or a.get("link", ""),
                "publishedAt": a.get("publishedAt") or a.get("published_at", ""),
                "summary": a.get("summary") or a.get("description", ""),
            }
            for a in articles[:limit]
        ]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Market state
# ---------------------------------------------------------------------------

def get_market_status() -> dict:
    """Current NSE market status from Upstox (falls back to IST clock)."""
    client = get_client()
    import httpx

    try:
        resp = httpx.get(
            "https://api.upstox.com/v2/market/status/NSE",
            headers=client._get_headers(),
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            status = str(data.get("status", "")).upper()
            mapping = {
                "NORMAL_OPEN": "OPEN",
                "NORMAL_CLOSE": "CLOSED",
                "PRE_OPEN": "PRE_OPEN",
                "CLOSING_START": "CLOSING",
                "CLOSING_END": "CLOSING",
            }
            return {
                "status": mapping.get(status, status or "UNKNOWN"),
                "message": f"NSE market status: {status or 'unknown'}",
                "isMarketHours": status.startswith("NORMAL_OPEN"),
                "timestamp": datetime.now().isoformat(),
            }
    except Exception:
        pass

    # Fallback: deterministic IST schedule
    now = datetime.now()
    minutes = now.hour * 60 + now.minute
    if now.weekday() >= 5:
        status, message = "CLOSED", "Market closed (weekend)"
    elif minutes < 9 * 60:
        status, message = "CLOSED", "Market opens at 9:15 AM IST"
    elif minutes < 9 * 60 + 15:
        status, message = "PRE_OPEN", "Pre-open session"
    elif minutes <= 15 * 60 + 30:
        status, message = "OPEN", "Market is open"
    else:
        status, message = "CLOSED", "Market closed for the day"
    return {
        "status": status,
        "message": message,
        "isMarketHours": status == "OPEN",
        "timestamp": now.isoformat(),
    }
