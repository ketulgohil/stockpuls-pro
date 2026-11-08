from datetime import datetime
from core import upstox_data
from core.data_fetcher import get_stock_info


TOP_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR",
    "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT", "AXISBANK",
    "BAJFINANCE", "MARUTI", "TITAN", "SUNPHARMA", "ASIANPAINT", "WIPRO",
    "TMPV", "HCLTECH", "ULTRACEMCO", "NTPC", "POWERGRID", "ONGC",
    "TATASTEEL", "JSWSTEEL", "ADANIPORTS", "TECHM", "INDUSINDBK", "DRREDDY"
]


def get_upcoming_results() -> list:
    """Earnings calendar is not available from Upstox / Downstox."""
    return []


def get_stock_financials(symbol: str) -> dict:
    try:
        info = get_stock_info(f"{symbol}.NS") or {}
        return {
            "symbol": symbol,
            "name": info.get("name", symbol),
            "marketCap": info.get("marketCap", 0),
            "trailingPE": info.get("pe"),
            "forwardPE": None,
            "priceToBook": info.get("pb"),
            "revenueGrowth": None,
            "earningsGrowth": None,
            "profitMargins": None,
            "returnOnEquity": info.get("roe"),
            "debtToEquity": None,
            "currentRatio": None,
            "earningsPerShare": None,
            "bookValue": info.get("bookValue"),
            "dividendYield": info.get("dividendYield"),
            "revenue": None,
            "netIncome": None,
            "totalDebt": None,
            "totalCash": None,
            "freeCashflow": None,
        }
    except Exception:
        return {"symbol": symbol, "error": "Could not fetch financials"}
