from fastapi import APIRouter

from core import upstox_data
from core.data_fetcher import NIFTY50_SYMBOLS

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
    movers = upstox_data.get_top_movers(NIFTY50_SYMBOLS, limit=10)
    return {"gainers": [_mover_row(q) for q in movers.get("gainers", [])]}


@router.get("/top-losers")
def top_losers():
    movers = upstox_data.get_top_movers(NIFTY50_SYMBOLS, limit=10)
    return {"losers": [_mover_row(q) for q in movers.get("losers", [])]}
