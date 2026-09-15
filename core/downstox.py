import json
import urllib.request
import urllib.error
from typing import Optional

DOWNSTOX_BASE = "https://downstox.com/api"


def _fetch(endpoint: str) -> Optional[dict]:
    try:
        url = f"{DOWNSTOX_BASE}{endpoint}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def get_fii_dii() -> dict:
    data = _fetch("/fiidii/daily")
    if data and data.get("success"):
        return {
            "date": data.get("date", ""),
            "fii": data.get("fii", {}),
            "dii": data.get("dii", {}),
            "marketStatus": data.get("marketStatus", {}),
        }
    return {"error": "Could not fetch FII/DII data"}


def get_market_overview() -> dict:
    data = _fetch("/india-markets/overview")
    if data and data.get("success"):
        return {
            "indices": data.get("indices", {}),
            "sectors": data.get("sectors", []),
        }
    return {"error": "Could not fetch market overview"}


def get_market_sentiments() -> dict:
    data = _fetch("/markets/sentiments")
    if data and data.get("success"):
        return {"sentiments": data.get("data", {})}
    return {"error": "Could not fetch sentiments"}


def get_superinvestors() -> list:
    data = _fetch("/superinvestors/")
    if data:
        return data.get("investors", data.get("data", []))
    return []


def get_superinvestor_detail(slug: str) -> dict:
    data = _fetch(f"/superinvestors/{slug}")
    if data:
        return data
    return {"error": "Could not fetch investor data"}


def get_breakouts() -> dict:
    data = _fetch("/breakouts/")
    if data and data.get("success"):
        return {
            "generatedAt": data.get("generatedAt", ""),
            "universe": data.get("universe", {}),
            "periods": data.get("periods", []),
            "labels": data.get("labels", {}),
            "data": data.get("data", {}),
        }
    return {"error": "Could not fetch breakout data"}


def get_holidays() -> dict:
    data = _fetch("/holidays/")
    if data and data.get("success"):
        return {
            "marketStatus": data.get("marketStatus", {}),
            "upcoming": data.get("upcoming", []),
        }
    return {"error": "Could not fetch holidays"}


def get_dividend_aristocrats() -> list:
    data = _fetch("/dividend-aristocrats/")
    if data:
        return data.get("stocks", data.get("data", []))
    return []


def get_weekly_outlook() -> dict:
    data = _fetch("/weekly-outlook/")
    if data:
        return data
    return {"error": "Could not fetch weekly outlook"}


def get_announcements() -> list:
    data = _fetch("/announcements/")
    if data:
        return data.get("announcements", data.get("data", []))
    return []


# ===== NEW ENDPOINTS =====

def get_other_side() -> dict:
    data = _fetch("/other-side/")
    if data and data.get("regime"):
        return {
            "asOf": data.get("asOf", ""),
            "regime": data.get("regime", {}),
            "regimeLog": data.get("regimeLog", [])[:5],
        }
    return {"error": "Could not fetch data"}


def get_pre_open() -> dict:
    data = _fetch("/pre-open/base-rates")
    if data and data.get("success"):
        return {
            "sessions": data.get("sessions", 0),
            "rates": data.get("rates", {}),
            "firstSession": data.get("firstSession", ""),
            "lastSession": data.get("lastSession", ""),
            "note": data.get("note", ""),
        }
    return {"error": "Could not fetch pre-open data"}


def get_promises() -> list:
    data = _fetch("/promises/")
    if data and data.get("success"):
        return data.get("promises", [])
    return []


def get_stock_detail(symbol: str) -> dict:
    data = _fetch(f"/stocks/{symbol.upper()}")
    if data and data.get("success"):
        return data
    return {"error": "Could not fetch stock data"}


def get_us_multibaggers() -> dict:
    data = _fetch("/us-markets/multibaggers")
    if data and data.get("success"):
        return {
            "updatedAt": data.get("updatedAt", 0),
            "universeSize": data.get("universeSize", 0),
            "crazy": data.get("crazy", []),
            "multibaggers": data.get("multibaggers", []),
            "strong": data.get("strong", []),
        }
    return {"error": "Could not fetch US multibaggers"}


def get_mf_schemes(page: int = 1, limit: int = 20) -> dict:
    data = _fetch(f"/mf/schemes?page={page}&limit={limit}")
    if data and data.get("success"):
        return {
            "schemes": data.get("schemes", []),
            "total": data.get("total", 0),
            "page": data.get("page", page),
            "totalPages": data.get("totalPages", 0),
        }
    return {"error": "Could not fetch MF schemes"}


def get_mf_scheme_detail(code: str) -> dict:
    data = _fetch(f"/mf/scheme/{code}")
    if data:
        return data
    return {"error": "Could not fetch scheme data"}
