import yfinance as yf
from datetime import datetime, timedelta


TOP_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR",
    "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT", "AXISBANK",
    "BAJFINANCE", "MARUTI", "TITAN", "SUNPHARMA", "ASIANPAINT", "WIPRO",
    "TATAMOTORS", "HCLTECH", "ULTRACEMCO", "NTPC", "POWERGRID", "ONGC",
    "TATASTEEL", "JSWSTEEL", "ADANIPORTS", "TECHM", "INDUSINDBK", "DRREDDY"
]


def get_upcoming_results() -> list:
    results = []
    today = datetime.now()

    for stock in TOP_STOCKS:
        try:
            ticker = yf.Ticker(f"{stock}.NS")
            cal = ticker.calendar

            if cal is not None and hasattr(cal, 'Earnings Date'):
                earnings_dates = cal.get('Earnings Date', [])
                if earnings_dates:
                    for date in earnings_dates:
                        if hasattr(date, 'date'):
                            date_obj = date.date()
                        else:
                            date_obj = date

                        if isinstance(date_obj, str):
                            date_obj = datetime.strptime(date_obj, "%Y-%m-%d")

                        days_until = (date_obj - today).days
                        if -7 <= days_until <= 30:
                            results.append({
                                "symbol": stock,
                                "date": date_obj.strftime("%Y-%m-%d"),
                                "daysUntil": max(0, days_until),
                                "status": "Upcoming" if days_until > 0 else "Recent"
                            })
                            break
        except Exception:
            continue

    if not results:
        pass

    results.sort(key=lambda x: x["daysUntil"])
    return results[:15]


def get_stock_financials(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info or {}

        return {
            "symbol": symbol,
            "name": info.get("shortName", symbol),
            "marketCap": info.get("marketCap", 0),
            "trailingPE": info.get("trailingPE"),
            "forwardPE": info.get("forwardPE"),
            "priceToBook": info.get("priceToBook"),
            "revenueGrowth": info.get("revenueGrowth"),
            "earningsGrowth": info.get("earningsGrowth"),
            "profitMargins": info.get("profitMargins"),
            "returnOnEquity": info.get("returnOnEquity"),
            "debtToEquity": info.get("debtToEquity"),
            "currentRatio": info.get("currentRatio"),
            "earningsPerShare": info.get("trailingEps"),
            "bookValue": info.get("bookValue"),
            "dividendYield": info.get("dividendYield"),
            "revenue": info.get("totalRevenue"),
            "netIncome": info.get("netIncomeToCommon"),
            "totalDebt": info.get("totalDebt"),
            "totalCash": info.get("totalCash"),
            "freeCashflow": info.get("freeCashflow"),
        }
    except Exception:
        return {"symbol": symbol, "error": "Could not fetch financials"}
