from datetime import datetime, timedelta
from typing import Optional
import json
import urllib.request
import urllib.error

from core import upstox_data
from core.data_fetcher import get_stock_info


DOWNSTOX_IPO_URL = "https://downstox.com/api/ipo/gmp"


def get_ipo_data() -> list[dict]:
    try:
        req = urllib.request.Request(DOWNSTOX_IPO_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        if data.get("success") and data.get("rows"):
            ipos = []
            for row in data["rows"]:
                ipos.append({
                    "name": row.get("company", ""),
                    "symbol": row.get("norm", "").upper(),
                    "price_band": f"\u20b9{row['priceBand']}" if row.get("priceBand") else "TBA",
                    "gmp": f"+₹{row['gmp']}" if row.get("gmp") else "-",
                    "gmp_pct": f"{row['gainPct']}%" if row.get("gainPct") else "-",
                    "est_listing": f"\u20b9{row['estListing']}" if row.get("estListing") else "-",
                    "date": row.get("date", ""),
                    "type": row.get("type", ""),
                    "status": row.get("type", ""),
                    "last_updated": row.get("status", ""),
                })
            return ipos
    except Exception as e:
        pass

    return []


def get_stock_financials(symbol: str) -> dict:
    """Fundamentals sourced from Downstox via get_stock_info."""
    try:
        info = get_stock_info(symbol)
        if not info:
            return {"symbol": symbol, "error": "Could not fetch financials"}

        return {
            "symbol": symbol,
            "name": info.get("name", symbol),
            "marketCap": info.get("marketCap"),
            "enterpriseValue": None,
            "trailingPE": info.get("pe"),
            "forwardPE": None,
            "pegRatio": None,
            "priceToBook": info.get("pb"),
            "priceToSales": None,
            "dividendYield": info.get("dividendYield"),
            "profitMargins": None,
            "returnOnEquity": info.get("roe"),
            "returnOnAssets": None,
            "revenueGrowth": None,
            "earningsGrowth": None,
            "debtToEquity": None,
            "currentRatio": None,
            "quickRatio": None,
            "freeCashflow": None,
            "operatingCashflow": None,
            "totalRevenue": None,
            "totalDebt": None,
            "totalCash": None,
            "bookValue": info.get("bookValue"),
            "earningsPerShare": None,
            "revenuePerShare": None,
            "quarterlyRevenue": [],
        }
    except Exception as e:
        return {"error": str(e)}


def get_dividend_history(symbol: str) -> dict:
    """Dividend history is not available from Upstox / Downstox."""
    return {
        "symbol": symbol,
        "name": symbol.replace(".NS", ""),
        "dividendYield": None,
        "dividendRate": None,
        "exDividendDate": None,
        "payoutRatio": None,
        "history": [],
        "available": False,
        "error": "Dividend history is not available with the current data provider.",
    }


def get_market_status() -> dict:
    now = datetime.now()
    ist_offset = timedelta(hours=5, minutes=30)
    ist_time = now + ist_offset

    market_open = ist_time.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = ist_time.replace(hour=15, minute=30, second=0, microsecond=0)
    pre_market_start = ist_time.replace(hour=9, minute=0, second=0, microsecond=0)

    is_weekday = ist_time.weekday() < 5

    if not is_weekday:
        status = "CLOSED"
        message = "Market closed (Weekend)"
    elif market_open <= ist_time <= market_close:
        status = "OPEN"
        message = "Market is open for trading"
    elif pre_market_start <= ist_time < market_open:
        status = "PRE_MARKET"
        message = "Pre-market session"
    elif ist_time > market_close:
        status = "AFTER_HOURS"
        message = "Market closed for today"
    else:
        status = "CLOSED"
        message = "Market opens at 9:15 AM IST"

    return {
        "status": status,
        "message": message,
        "currentTime": ist_time.strftime("%Y-%m-%d %H:%M:%S IST"),
        "marketOpen": "09:15 AM IST",
        "marketClose": "03:30 PM IST"
    }


def get_economic_calendar() -> list[dict]:
    today = datetime.now()
    events = []

    rbi_dates = [
        ("2026-10-01", "RBI Monetary Policy Decision", "High", "Rate decision"),
        ("2026-12-01", "RBI Policy Review", "High", "-"),
        ("2027-02-01", "Union Budget 2027", "High", "-"),
        ("2027-04-01", "RBI Policy Review", "High", "-"),
    ]

    for date_str, event, importance, expected in rbi_dates:
        event_date = datetime.strptime(date_str, "%Y-%m-%d")
        if event_date >= today:
            events.append({
                "date": date_str,
                "event": event,
                "importance": importance,
                "expected": expected,
                "daysUntil": (event_date - today).days,
            })

    monthly_events = [
        ("CPI Inflation", "High", "3.5-4.5%"),
        ("IIP Data", "Medium", "3.0-4.0%"),
        ("GST Collections", "Medium", "\u20b91.6-1.8 Lakh Cr"),
        ("Trade Deficit Data", "Medium", "-"),
    ]

    from datetime import timedelta
    for i in range(1, 6):
        month = today.month + i
        year = today.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        for event_name, importance, expected in monthly_events:
            events.append({
                "date": f"{year}-{month:02d}-15",
                "event": f"{event_name} ({datetime(year, month, 1).strftime('%b %Y')})",
                "importance": importance,
                "expected": expected,
                "daysUntil": (datetime(year, month, 15) - today).days,
            })

    events.sort(key=lambda x: x["daysUntil"])
    return [e for e in events if e["daysUntil"] >= 0][:15]
