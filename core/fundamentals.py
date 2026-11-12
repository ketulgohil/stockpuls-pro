from datetime import datetime
from typing import Optional
from core import upstox_data
from core.data_fetcher import ALL_SYMBOLS, get_stock_info
from core.downstox import get_fii_dii


def get_earnings_calendar(days: int = 30) -> list[dict]:
    """Earnings calendar data is not available from Upstox / Downstox."""
    return []


def get_dividend_stocks() -> list[dict]:
    symbols = ALL_SYMBOLS

    dividend_stocks = []

    for symbol in symbols:
        try:
            info = get_stock_info(symbol)
            if not info:
                continue

            div_yield = info.get("dividendYield")
            price = info.get("currentPrice")

            if div_yield and div_yield > 0:
                dividend_stocks.append({
                    "symbol": symbol,
                    "name": info.get("name", symbol.replace(".NS", "")),
                    "price": price,
                    "dividendYield": round(div_yield * 100, 2),
                    "dividendRate": None,
                    "payoutRatio": None,
                    "exDividendDate": None,
                    "sector": info.get("sector", "Unknown")
                })
        except Exception:
            continue

    dividend_stocks.sort(key=lambda x: x.get("dividendYield", 0), reverse=True)
    return dividend_stocks


def get_fii_dii_data() -> dict:
    try:
        data = get_fii_dii()
        fii = data.get("fii", {}) if isinstance(data, dict) else {}
        dii = data.get("dii", {}) if isinstance(data, dict) else {}

        return {
            "date": data.get("date", "") if isinstance(data, dict) else "",
            "fii": {
                "buyValue": fii.get("buyValue", 0),
                "sellValue": fii.get("sellValue", 0),
                "netValue": fii.get("netValue", 0),
            },
            "dii": {
                "buyValue": dii.get("buyValue", 0),
                "sellValue": dii.get("sellValue", 0),
                "netValue": dii.get("netValue", 0),
            },
            "marketStatus": data.get("marketStatus", {}) if isinstance(data, dict) else {},
            "note": "FII/DII data sourced from Downstox.",
        }
    except Exception as e:
        return {"error": str(e)}
