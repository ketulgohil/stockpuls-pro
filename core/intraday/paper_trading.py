import os
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger("paper_trading")

class PaperTradingDesk:
    """
    Paper Trading & Active Risk Management Desk supporting virtual capital,
    live MTM P&L tracking, and automated stop-loss / target breach monitoring.
    """
    def __init__(self, initial_capital: float = 10000000.0, storage_file: str = "data/paper_trading_portfolio.json"):
        self.initial_capital = initial_capital
        self.storage_file = storage_file
        self.cash = initial_capital
        self.positions: List[dict] = []
        self._load_state()

    def _load_state(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r") as f:
                    data = json.load(f)
                    self.initial_capital = data.get("initial_capital", self.initial_capital)
                    self.cash = data.get("cash", self.cash)
                    self.positions = data.get("positions", [])
            except Exception as e:
                logger.error(f"Failed to load paper trading state from {self.storage_file}: {e}")

    def _save_state(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.storage_file)), exist_ok=True)
        try:
            data = {
                "initial_capital": self.initial_capital,
                "cash": self.cash,
                "positions": self.positions,
                "updated_at": datetime.now().isoformat()
            }
            with open(self.storage_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save paper trading state to {self.storage_file}: {e}")

    def execute_buy(
        self,
        symbol: str,
        quantity: int,
        stop_loss: float,
        target: float,
        notes: str = "",
        entry_price: Optional[float] = None,
        engine: Optional[Any] = None
    ) -> dict:
        clean_symbol = symbol.upper().replace(".NS", "").replace(".BO", "").strip()

        price = entry_price
        if price is None and engine is not None:
            quotes = engine.get_latest_quotes()
            quote = quotes.get(clean_symbol, {})
            price = quote.get("last_price") or quote.get("ltp") or quote.get("price")

        if price is None or price <= 0:
            raise ValueError(f"Valid entry price required to execute buy for {clean_symbol}")

        total_cost = price * quantity
        if self.cash < total_cost:
            raise ValueError(f"Insufficient cash: have {self.cash}, need {total_cost}")

        self.cash -= total_cost
        position_id = str(uuid.uuid4())[:8]

        position = {
            "id": position_id,
            "symbol": clean_symbol,
            "quantity": quantity,
            "entry_price": price,
            "stop_loss": stop_loss,
            "target": target,
            "notes": notes,
            "status": "OPEN",
            "current_price": price,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "created_at": datetime.now().isoformat(),
            "closed_at": None,
            "exit_reason": None,
            "exit_price": None
        }

        self.positions.append(position)
        self._save_state()
        logger.info(f"Executed BUY paper trade for {quantity} {clean_symbol} @ {price} (SL: {stop_loss}, Target: {target})")
        return position

    def update_mtm(self, current_quotes: Dict[str, dict], engine: Optional[Any] = None) -> List[dict]:
        events = []
        engine_quotes = engine.get_latest_quotes() if engine else {}

        for pos in self.positions:
            if pos["status"] != "OPEN":
                continue

            symbol = pos["symbol"]
            # Lookup quote
            q = current_quotes.get(symbol) or current_quotes.get(symbol + ".NS") or current_quotes.get(symbol.replace(".NS", ""))
            if not q:
                q = engine_quotes.get(symbol) or engine_quotes.get(symbol + ".NS") or engine_quotes.get(symbol.replace(".NS", ""))

            ltp = None
            if q:
                ltp = q.get("last_price") or q.get("ltp") or q.get("price") or q.get("close")

            if ltp is not None and ltp > 0:
                pos["current_price"] = ltp
                entry = pos["entry_price"]
                qty = pos["quantity"]
                pos["unrealized_pnl"] = (ltp - entry) * qty

                stop_loss = pos["stop_loss"]
                target = pos["target"]

                # Check stop loss hit
                if ltp <= stop_loss:
                    pos["status"] = "CLOSED"
                    pos["exit_price"] = ltp
                    pos["closed_at"] = datetime.now().isoformat()
                    pos["exit_reason"] = "STOP_LOSS_HIT"
                    pos["realized_pnl"] = (ltp - entry) * qty
                    self.cash += (qty * ltp)

                    events.append({
                        "event": "STOP_LOSS_HIT",
                        "position_id": pos["id"],
                        "symbol": symbol,
                        "exit_price": ltp,
                        "realized_pnl": pos["realized_pnl"],
                        "timestamp": pos["closed_at"]
                    })
                    logger.warning(f"Stop loss hit for {symbol} (ID: {pos['id']}) at LTP {ltp} <= SL {stop_loss}")

                # Check target hit
                elif ltp >= target:
                    pos["status"] = "CLOSED"
                    pos["exit_price"] = ltp
                    pos["closed_at"] = datetime.now().isoformat()
                    pos["exit_reason"] = "TARGET_HIT"
                    pos["realized_pnl"] = (ltp - entry) * qty
                    self.cash += (qty * ltp)

                    events.append({
                        "event": "TARGET_HIT",
                        "position_id": pos["id"],
                        "symbol": symbol,
                        "exit_price": ltp,
                        "realized_pnl": pos["realized_pnl"],
                        "timestamp": pos["closed_at"]
                    })
                    logger.info(f"Target hit for {symbol} (ID: {pos['id']}) at LTP {ltp} >= Target {target}")

        self._save_state()
        return events

    def close_position(
        self,
        position_id: str,
        exit_price: Optional[float] = None,
        reason: str = "MANUAL",
        engine: Optional[Any] = None
    ) -> dict:
        target_pos = None
        for pos in self.positions:
            if pos["id"] == position_id and pos["status"] == "OPEN":
                target_pos = pos
                break

        if not target_pos:
            raise ValueError(f"Open position with ID {position_id} not found")

        symbol = target_pos["symbol"]
        price = exit_price
        if price is None:
            if engine is not None:
                quotes = engine.get_latest_quotes()
                q = quotes.get(symbol) or quotes.get(symbol + ".NS")
                if q:
                    price = q.get("last_price") or q.get("ltp") or q.get("price")
            if price is None:
                price = target_pos["current_price"]

        target_pos["status"] = "CLOSED"
        target_pos["exit_price"] = price
        target_pos["closed_at"] = datetime.now().isoformat()
        target_pos["exit_reason"] = reason

        entry = target_pos["entry_price"]
        qty = target_pos["quantity"]
        target_pos["realized_pnl"] = (price - entry) * qty
        target_pos["unrealized_pnl"] = 0.0

        self.cash += (qty * price)
        self._save_state()
        logger.info(f"Closed paper position {position_id} ({symbol}) at exit price {price} (Reason: {reason})")
        return target_pos

    def get_summary(self) -> dict:
        invested = 0.0
        current_value = 0.0
        unrealized_pnl = 0.0
        realized_pnl = 0.0
        open_count = 0
        closed_count = 0

        for pos in self.positions:
            if pos["status"] == "OPEN":
                open_count += 1
                invested += pos["entry_price"] * pos["quantity"]
                current_value += pos["current_price"] * pos["quantity"]
                unrealized_pnl += pos.get("unrealized_pnl", 0.0)
            elif pos["status"] == "CLOSED":
                closed_count += 1
                realized_pnl += pos.get("realized_pnl", 0.0)

        total_portfolio_value = self.cash + current_value

        return {
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "invested": invested,
            "current_value": current_value,
            "total_portfolio_value": total_portfolio_value,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "open_positions_count": open_count,
            "closed_positions_count": closed_count,
            "positions": self.positions
        }
