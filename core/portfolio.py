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


def sell_holding(symbol: str, quantity: float, price: Optional[float] = None) -> dict:
    """Sell part or all of a holding.

    Quantity is reduced; when it reaches zero the holding is removed.
    An optional sell price records a realized-P&L trade entry, which the
    /api/portfolio/realized endpoint reports.
    """
    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        return {"error": "Quantity to sell must be a number"}
    if quantity <= 0:
        return {"error": "Quantity to sell must be positive"}

    data = _load_json(PORTFOLIO_FILE)
    holdings = data.get("holdings", [])
    holding = next((h for h in holdings if h["symbol"] == symbol), None)
    if not holding:
        return {"error": f"Holding {symbol} not found"}

    if quantity > holding["quantity"] + 1e-9:
        return {"error": f"Cannot sell {quantity:g} — you hold {holding['quantity']:g} of {symbol}"}

    sell_price = float(price) if price and float(price) > 0 else None
    realized = round((sell_price - holding["buyPrice"]) * quantity, 2) if sell_price else None

    remaining = round(holding["quantity"] - quantity, 6)

    trades = data.setdefault("trades", [])
    trades.append({
        "symbol": symbol,
        "quantity": quantity,
        "price": sell_price,
        "buyPrice": holding["buyPrice"],
        "realizedPnl": realized,
        "soldAt": datetime.now().isoformat(),
    })

    if remaining <= 1e-9:
        data["holdings"] = [h for h in holdings if h["symbol"] != symbol]
        msg = f"Sold all {quantity:g} of {symbol}"
    else:
        holding["quantity"] = remaining
        holding["updatedAt"] = datetime.now().isoformat()
        msg = f"Sold {quantity:g} of {symbol} — {remaining:g} remaining"

    _save_json(PORTFOLIO_FILE, data)
    if realized is not None:
        msg += f" (realized P&L ₹{realized})"
    return {"message": msg, "remainingQuantity": max(remaining, 0.0), "realizedPnl": realized}


def get_realized_trades() -> list[dict]:
    data = _load_json(PORTFOLIO_FILE)
    return data.get("trades", [])


def add_dividend(symbol: str, amount: float, date: Optional[str] = None, note: str = "") -> dict:
    """Record a dividend received for a symbol (total amount in ₹)."""
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {"error": "Dividend amount must be a number"}
    if amount <= 0:
        return {"error": "Dividend amount must be positive"}

    data = _load_json(PORTFOLIO_FILE)
    dividends = data.setdefault("dividends", [])
    dividends.append({
        "symbol": symbol,
        "amount": round(amount, 2),
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "note": note or "",
        "recordedAt": datetime.now().isoformat(),
    })
    _save_json(PORTFOLIO_FILE, data)
    total = round(sum(d["amount"] for d in dividends), 2)
    return {"message": f"Dividend ₹{round(amount, 2)} recorded for {symbol}", "totalDividends": total}


def apply_corp_action(symbol: str, ratio: float, action_type: str = "split", date: Optional[str] = None) -> dict:
    """Apply a stock split / bonus issue to a holding.

    A ratio of N means each existing share becomes N shares: quantity is
    multiplied by N and the average buy price divided by N, so the total
    invested value (and P&L %) is preserved.
    """
    try:
        ratio = float(ratio)
    except (TypeError, ValueError):
        return {"error": "Ratio must be a number"}
    if ratio <= 0:
        return {"error": "Ratio must be positive"}
    if action_type not in ("split", "bonus"):
        return {"error": "Action type must be 'split' or 'bonus'"}

    data = _load_json(PORTFOLIO_FILE)
    holding = next((h for h in data.get("holdings", []) if h["symbol"] == symbol), None)
    if not holding:
        return {"error": f"Holding {symbol} not found"}

    old_qty = holding["quantity"]
    old_avg = holding["buyPrice"]
    new_qty = round(old_qty * ratio, 6)
    new_avg = round(old_avg / ratio, 2)

    holding["quantity"] = new_qty
    holding["buyPrice"] = new_avg
    holding["updatedAt"] = datetime.now().isoformat()

    data.setdefault("corpActions", []).append({
        "symbol": symbol,
        "type": action_type,
        "ratio": ratio,
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "before": {"quantity": old_qty, "avgPrice": old_avg},
        "after": {"quantity": new_qty, "avgPrice": new_avg},
        "recordedAt": datetime.now().isoformat(),
    })
    _save_json(PORTFOLIO_FILE, data)
    return {
        "message": f"Applied {ratio:g}:1 {action_type} to {symbol} — qty {old_qty:g} → {new_qty:g}, avg ₹{old_avg} → ₹{new_avg}",
        "holding": holding,
    }


def get_dividend_records() -> dict:
    data = _load_json(PORTFOLIO_FILE)
    dividends = data.get("dividends", [])
    total = round(sum(d.get("amount", 0) for d in dividends), 2)
    return {
        "dividends": dividends,
        "corpActions": data.get("corpActions", []),
        "totalDividends": total,
    }


def get_dismissed_events() -> list:
    """IDs of auto-detected event suggestions the user dismissed."""
    return _load_json(PORTFOLIO_FILE).get("dismissedEvents", [])


def add_dismissed_event(event_id: str) -> dict:
    data = _load_json(PORTFOLIO_FILE)
    dismissed = data.setdefault("dismissedEvents", [])
    if event_id not in dismissed:
        dismissed.append(event_id)
        # Keep the list bounded — old dismissals are meaningless after a while.
        data["dismissedEvents"] = dismissed[-500:]
        _save_json(PORTFOLIO_FILE, data)
    return {"message": "Event dismissed", "dismissedCount": len(data["dismissedEvents"])}


DEFAULT_WATCHLIST_SYMBOLS = [
    {"symbol": "RELIANCE.NS", "name": "Reliance Industries"},
    {"symbol": "TCS.NS", "name": "Tata Consultancy Services"},
    {"symbol": "INFY.NS", "name": "Infosys"},
    {"symbol": "HDFCBANK.NS", "name": "HDFC Bank"},
    {"symbol": "ICICIBANK.NS", "name": "ICICI Bank"},
    {"symbol": "SBIN.NS", "name": "State Bank of India"},
    {"symbol": "BHARTIARTL.NS", "name": "Bharti Airtel"},
    {"symbol": "TATAMOTORS.NS", "name": "Tata Motors"}
]


def get_watchlist() -> list[dict]:
    data = _load_json(WATCHLIST_FILE)
    symbols = data.get("symbols", [])
    if not symbols:
        data["symbols"] = DEFAULT_WATCHLIST_SYMBOLS
        _save_json(WATCHLIST_FILE, data)
        return DEFAULT_WATCHLIST_SYMBOLS
    return symbols


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
