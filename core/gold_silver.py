from typing import Optional

GOLD_UNAVAILABLE_ERROR = "Spot gold data is not available with the current data provider."
SILVER_UNAVAILABLE_ERROR = "Spot silver data is not available with the current data provider."
METALS_UNAVAILABLE_ERROR = "Spot metals data is not available with the current data provider."


def get_gold_prices() -> dict:
    return {
        "available": False,
        "symbol": "GC=F",
        "name": "Gold (USD/oz)",
        "currency": "USD",
        "error": GOLD_UNAVAILABLE_ERROR,
    }


def get_silver_prices() -> dict:
    return {
        "available": False,
        "symbol": "SI=F",
        "name": "Silver (USD/oz)",
        "currency": "USD",
        "error": SILVER_UNAVAILABLE_ERROR,
    }


def get_gold_etfs() -> list[dict]:
    # No free spot-metals/ETF source is wired into the current data provider.
    return []


def get_gold_nifty_ratio() -> dict:
    return {
        "available": False,
        "error": METALS_UNAVAILABLE_ERROR,
    }


def calculate_gold_value(weight_grams: float, purity: str = "24K") -> dict:
    purity_map = {
        "24K": 0.999,
        "22K": 0.916,
        "18K": 0.750,
        "14K": 0.585,
    }

    return {
        "available": False,
        "weight_grams": weight_grams,
        "purity": purity,
        "purity_factor": purity_map.get(purity, 0.999),
        "error": GOLD_UNAVAILABLE_ERROR,
    }
