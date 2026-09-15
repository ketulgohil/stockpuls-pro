import json
import os
from typing import Optional
from datetime import datetime


PORTFOLIO_FILE = "data/portfolio.json"
WATCHLIST_FILE = "data/watchlist.json"


def _load_json(filepath: str) -> dict:
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {}


def _save_json(filepath: str, data: dict):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def get_portfolio() -> dict:
    data = _load_json(PORTFOLIO_FILE)
    return data.get("holdings", [])


def add_holding(symbol: str, quantity: float, buy_price: float) -> dict:
    data = _load_json(PORTFOLIO_FILE)
    holdings = data.get("holdings", [])

    for holding in holdings:
        if holding["symbol"] == symbol:
            total_qty = holding["quantity"] + quantity
            total_cost = (holding["quantity"] * holding["buyPrice"]) + (quantity * buy_price)
            holding["buyPrice"] = round(total_cost / total_qty, 2)
            holding["quantity"] = total_qty
            holding["updatedAt"] = datetime.now().isoformat()
            _save_json(PORTFOLIO_FILE, data)
            return holding

    new_holding = {
        "symbol": symbol,
        "quantity": quantity,
        "buyPrice": buy_price,
        "buyDate": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat()
    }
    holdings.append(new_holding)
    data["holdings"] = holdings
    _save_json(PORTFOLIO_FILE, data)
    return new_holding


def remove_holding(symbol: str) -> bool:
    data = _load_json(PORTFOLIO_FILE)
    holdings = data.get("holdings", [])
    original_len = len(holdings)
    holdings = [h for h in holdings if h["symbol"] != symbol]
    if len(holdings) < original_len:
        data["holdings"] = holdings
        _save_json(PORTFOLIO_FILE, data)
        return True
    return False


def get_watchlist() -> list[dict]:
    data = _load_json(WATCHLIST_FILE)
    return data.get("symbols", [])


def add_to_watchlist(symbol: str, name: str = "") -> dict:
    data = _load_json(WATCHLIST_FILE)
    symbols = data.get("symbols", [])

    for s in symbols:
        if s["symbol"] == symbol:
            return s

    new_entry = {
        "symbol": symbol,
        "name": name or symbol.replace(".NS", ""),
        "addedAt": datetime.now().isoformat()
    }
    symbols.append(new_entry)
    data["symbols"] = symbols
    _save_json(WATCHLIST_FILE, data)
    return new_entry


def remove_from_watchlist(symbol: str) -> bool:
    data = _load_json(WATCHLIST_FILE)
    symbols = data.get("symbols", [])
    original_len = len(symbols)
    symbols = [s for s in symbols if s["symbol"] != symbol]
    if len(symbols) < original_len:
        data["symbols"] = symbols
        _save_json(WATCHLIST_FILE, data)
        return True
    return False
