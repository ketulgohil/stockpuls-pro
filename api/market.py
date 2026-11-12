from fastapi import APIRouter, Query

from core import upstox_data
from core.data_fetcher import ALL_SYMBOLS

router = APIRouter(prefix="/api/market", tags=["market"])

INDEX_META = {
    "^NSEI": {"name": "NIFTY 50", "exchange": "NSE"},
    "^BSESN": {"name": "SENSEX", "exchange": "BSE"},
    "^NSEBANK": {"name": "NIFTY Bank", "exchange": "NSE"},
    "^CNXIT": {"name": "NIFTY IT", "exchange": "NSE"},
    "^NSEMDCP50": {"name": "NIFTY Midcap", "exchange": "NSE"},
}


@router.get("")
def market_overview():
    quotes = upstox_data.get_market_indices(list(INDEX_META))

    results = []
    for symbol, info in INDEX_META.items():
        quote = quotes.get(symbol)
        if not quote:
            continue
        results.append({
            "symbol": symbol,
            "name": info["name"],
            "exchange": info["exchange"],
            "price": quote.get("price", 0),
            "change": quote.get("change", 0),
            "changePercent": quote.get("changePercent", 0),
            "dayHigh": quote.get("dayHigh") or None,
            "dayLow": quote.get("dayLow") or None,
            "previousClose": quote.get("previousClose") or None
        })

    return {"indices": results}


def _mover_row(quote: dict) -> dict:
    symbol = quote.get("symbol", "")
    return {
        "symbol": symbol,
        "name": symbol.replace(".NS", ""),
        "price": quote.get("price", 0),
        "changePercent": quote.get("changePercent", 0)
    }


@router.get("/top-gainers")
def top_gainers():
    movers = upstox_data.get_top_movers(ALL_SYMBOLS, limit=10)
    return {"gainers": [_mover_row(q) for q in movers.get("gainers", [])]}


@router.get("/top-losers")
def top_losers():
    movers = upstox_data.get_top_movers(ALL_SYMBOLS, limit=10)
    return {"losers": [_mover_row(q) for q in movers.get("losers", [])]}


@router.get("/quotes")
def market_quotes(symbols: str = Query("", description="Comma-separated symbols")):
    """Batch quote lookup used as a REST fallback when the WebSocket is unavailable."""
    requested = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not requested:
        requested = list(INDEX_META)
    requested = requested[:200]

    quotes = upstox_data.get_quotes(requested)
    prices = {}
    for symbol, quote in quotes.items():
        prices[symbol] = {
            "price": quote.get("price", 0),
            "change": quote.get("change", 0),
            "changePercent": quote.get("changePercent", 0),
        }
    return {"prices": prices, "count": len(prices)}


@router.get("/pulse")
def market_pulse():
    quotes = upstox_data.get_market_indices(list(INDEX_META))
    changes = []
    for symbol in INDEX_META:
        quote = quotes.get(symbol)
        if quote and "changePercent" in quote:
            changes.append(quote["changePercent"])

    avg_change = sum(changes) / len(changes) if changes else 0.0
    score = int(min(max(50 + (avg_change * 25), 0), 100))

    if score >= 65:
        label = "Bullish"
        color = "#10b981"
    elif score <= 35:
        label = "Bearish"
        color = "#ef4444"
    else:
        label = "Neutral"
        color = "#f59e0b"

    return {
        "score": score,
        "label": label,
        "color": color,
        "avgChange": round(avg_change, 2)
    }
