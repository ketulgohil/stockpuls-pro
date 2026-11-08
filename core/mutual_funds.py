from typing import Optional

from core.downstox import get_mf_schemes, get_mf_scheme_detail


# Popular Indian Mutual Funds (used for display names / category mapping)
MF_FUNDS = {
    "HDFC Mid-Cap Opportunities Fund": "HDFC Mid-Cap Opportunities Fund-Growth",
    "SBI Small Cap Fund": "SBI Small Cap Fund-Growth",
    "Mirae Asset Large Cap Fund": "Mirae Asset Large Cap Fund-Growth",
    "Axis Bluechip Fund": "Axis Bluechip Fund-Growth",
    "ICICI Prudential Bluechip Fund": "ICICI Prudential Bluechip Fund-Growth",
    "Nippon India Small Cap Fund": "Nippon India Small Cap Fund-Growth",
    "Parag Parikh Flexi Cap Fund": "Parag Parikh Flexi Cap Fund-Growth",
    "HDFC Flexi Cap Fund": "HDFC Flexi Cap Fund-Growth",
    "UTI Nifty Index Fund": "UTI Nifty Index Fund-Growth",
    "SBI Nifty Index Fund": "SBI Nifty Index Fund-Growth",
    "Kotak Equity Opps Fund": "Kotak Equity Opportunities Fund-Growth",
    "L&T Midcap Fund": "L&T Midcap Fund-Growth",
    "Aditya Birla Sun Life Digital India Fund": "Aditya Birla Sun Life Digital India Fund-Growth",
    "Tata Digital India Fund": "Tata Digital India Fund-Growth",
    "Navi Nifty 50 Index Fund": "Navi Nifty 50 Index Fund-Growth",
}

MF_CATEGORIES = {
    "Large Cap": [
        "Mirae Asset Large Cap Fund",
        "Axis Bluechip Fund",
        "ICICI Prudential Bluechip Fund",
    ],
    "Index": [
        "UTI Nifty Index Fund",
        "SBI Nifty Index Fund",
        "Navi Nifty 50 Index Fund",
    ],
    "Mid Cap": [
        "HDFC Mid-Cap Opportunities Fund",
        "L&T Midcap Fund",
    ],
    "Small Cap": [
        "SBI Small Cap Fund",
        "Nippon India Small Cap Fund",
    ],
    "Flexi Cap": [
        "Parag Parikh Flexi Cap Fund",
        "HDFC Flexi Cap Fund",
    ],
    "Large & Mid Cap": [
        "Kotak Equity Opps Fund",
    ],
    "Sectoral / Thematic": [
        "Aditya Birla Sun Life Digital India Fund",
        "Tata Digital India Fund",
    ],
}


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _get_downstox_mf_schemes(page: int = 1, limit: int = 20) -> list:
    data = get_mf_schemes(page=page, limit=limit)
    if isinstance(data, dict) and data.get("schemes"):
        return data["schemes"]
    return []


def _get_downstox_mf_scheme_detail(code: str) -> Optional[dict]:
    data = get_mf_scheme_detail(str(code))
    if isinstance(data, dict) and data.get("success"):
        return data
    return None


def _resolve_scheme(fund_name: str) -> Optional[dict]:
    """Find a Downstox scheme by name (or scheme code)."""
    query = (fund_name or "").strip()
    if not query:
        return None

    if query.isdigit():
        detail = _get_downstox_mf_scheme_detail(query)
        if not detail:
            return None
        meta = detail.get("meta", {}) or {}
        return {
            "scheme_code": str(meta.get("scheme_code", query)),
            "scheme_name": meta.get("scheme_name", query),
            "category": meta.get("category", ""),
        }

    search = MF_FUNDS.get(query, query).lower()
    for scheme in _get_downstox_mf_schemes(page=1, limit=100):
        name = str(scheme.get("scheme_name", "")).lower()
        if search and search in name:
            return scheme
    return None


def _returns_from_nav_history(nav_values: list[float]) -> dict:
    """Approximate period returns from a descending NAV history."""
    current = nav_values[0]

    def period_return(days: int) -> float:
        if len(nav_values) <= 1:
            return 0.0
        base = nav_values[min(days, len(nav_values) - 1)]
        if base <= 0:
            return 0.0
        return round(((current / base) - 1) * 100, 2)

    return {
        "1W": period_return(5),
        "1M": period_return(22),
        "3M": period_return(66),
        "6M": period_return(132),
        "1Y": period_return(252),
    }


def get_mf_nav(fund_name: str) -> Optional[dict]:
    try:
        scheme = _resolve_scheme(fund_name)
        if not scheme:
            return {
                "available": False,
                "name": fund_name,
                "error": (
                    "Fund NAV lookup is not available with the current data provider. "
                    "Use the mutual fund scheme list instead."
                ),
            }

        detail = _get_downstox_mf_scheme_detail(scheme["scheme_code"])
        if not detail:
            return {
                "available": False,
                "name": fund_name,
                "error": "Could not fetch NAV history from the current data provider.",
            }

        nav_values = [
            _to_float(row.get("nav"))
            for row in detail.get("data", [])
            if _to_float(row.get("nav")) > 0
        ]
        if not nav_values:
            return {
                "available": False,
                "name": fund_name,
                "error": "No NAV history available for this fund.",
            }

        current_nav = nav_values[0]
        prev_nav = nav_values[1] if len(nav_values) > 1 else current_nav
        meta = detail.get("meta", {}) or {}

        return {
            "name": scheme.get("scheme_name") or meta.get("scheme_name", fund_name),
            "nav": round(current_nav, 2),
            "dailyChange": round(current_nav - prev_nav, 2),
            "dailyChangePct": round(((current_nav - prev_nav) / prev_nav) * 100, 2) if prev_nav else 0,
            "returns": _returns_from_nav_history(nav_values),
            "category": scheme.get("category") or get_fund_category(fund_name),
            "schemeCode": str(scheme.get("scheme_code", "")),
        }
    except Exception as e:
        print(f"Error fetching mutual fund NAV for {fund_name}: {e}")
        return {
            "available": False,
            "name": fund_name,
            "error": "Could not fetch mutual fund data from the current data provider.",
        }


def get_fund_category(fund_name: str) -> str:
    for cat, funds in MF_CATEGORIES.items():
        if fund_name in funds:
            return cat
    return "Other"


def get_all_mf_data() -> list:
    results = []

    for scheme in _get_downstox_mf_schemes(page=1, limit=20):
        results.append({
            "name": scheme.get("scheme_name", ""),
            "nav": _to_float(scheme.get("nav")),
            "dailyChange": 0,
            "dailyChangePct": 0,
            "returns": {
                "1M": _to_float(scheme.get("return_1m")),
                "3M": _to_float(scheme.get("return_3m")),
                "1Y": _to_float(scheme.get("return_1y")),
                "3Y": _to_float(scheme.get("return_3y")),
            },
            "category": scheme.get("category", "Other"),
            "schemeCode": scheme.get("scheme_code", ""),
        })

    return results


def calculate_sip(monthly_amount: float, annual_return: float, years: int) -> dict:
    monthly_return = annual_return / (12 * 100)
    months = years * 12

    total_invested = monthly_amount * months
    future_value = 0

    for i in range(months):
        future_value = (future_value + monthly_amount) * (1 + monthly_return)

    wealth_gained = future_value - total_invested

    return {
        "monthlyAmount": monthly_amount,
        "annualReturn": annual_return,
        "years": years,
        "totalInvested": round(total_invested, 2),
        "futureValue": round(future_value, 2),
        "wealthGained": round(wealth_gained, 2),
        "returnMultiple": round(future_value / total_invested, 2) if total_invested > 0 else 0
    }
