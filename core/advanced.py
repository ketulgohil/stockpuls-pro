from typing import Optional
from core import upstox_data
from core.data_fetcher import ALL_SYMBOLS, SECTOR_MAP


def get_heatmap_data() -> dict:
    sector_stocks = {}
    for symbol in ALL_SYMBOLS[:50]:
        sector = "Others"
        for s, members in SECTOR_MAP.items():
            if symbol.replace(".NS", "") in members:
                sector = s
                break
        if sector not in sector_stocks:
            sector_stocks[sector] = []
        sector_stocks[sector].append(symbol)

    heatmap = []

    all_stocks = [s for stocks in sector_stocks.values() for s in stocks]
    quotes = upstox_data.get_quotes(all_stocks) or {}

    for sector, stocks in sector_stocks.items():
        sector_data = {"name": sector, "stocks": []}
        sector_change = 0
        count = 0

        for symbol in stocks[:8]:
            q = quotes.get(symbol)
            if not q:
                continue
            change_pct = float(q.get("changePercent", 0) or 0)
            price = float(q.get("price", 0) or 0)

            sector_data["stocks"].append({
                "symbol": symbol,
                "name": symbol.replace(".NS", ""),
                "change": round(change_pct, 2),
                "price": round(price, 2)
            })
            sector_change += change_pct
            count += 1

        sector_data["avgChange"] = round(sector_change / max(count, 1), 2)
        sector_data["stockCount"] = len(sector_data["stocks"])
        heatmap.append(sector_data)

    heatmap.sort(key=lambda x: x["avgChange"], reverse=True)
    return {"sectors": heatmap}


def get_global_markets() -> dict:
    """Global indices / currencies / commodities are not available from Upstox."""
    return {
        "markets": [],
        "available": False,
        "error": "Global market data is not available with the current data provider (Upstox). Indian indices are available via /api/market.",
    }


def get_promoter_data(symbol: str) -> dict:
    """Promoter / institutional holding data is not exposed by Upstox."""
    return {
        "symbol": symbol,
        "name": symbol.replace(".NS", ""),
        "promoterHolding": None,
        "institutionHolding": None,
        "mutualFundHolding": None,
        "floatShares": None,
        "sharesOutstanding": None,
        "shortRatio": None,
        "shortPercentOfFloat": None,
        "available": False,
        "error": "Promoter/institutional holding data is not available with the current data provider.",
    }
