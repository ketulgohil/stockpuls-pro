import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from core.intraday.orb import ORBScanner

logger = logging.getLogger("intraday_backtest")

class IntradayBacktester:
    """
    Intraday Strategy Backtester for evaluating Opening Range Breakout (ORB)
    and other intraday strategies on historical 5-minute candles.
    """
    def __init__(self, initial_capital: float = 1000000.0, quantity_per_trade: int = 100):
        self.initial_capital = initial_capital
        self.quantity_per_trade = quantity_per_trade
        self.orb_scanner = ORBScanner()

    def run_orb_backtest(self, symbol: str, candles_5m: List[dict]) -> dict:
        """
        Run ORB backtest on a series of 5-minute candles.
        Group candles by date, compute 09:15-09:30 ORB, detect breakout,
        simulate trade until target/stop-loss or EOD square-off.
        """
        if not candles_5m:
            return {
                "symbol": symbol,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_profit": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "trades": []
            }

        # Ensure candles are sorted by timestamp
        sorted_candles = sorted(candles_5m, key=lambda c: c.get("timestamp", ""))

        # Group by date (YYYY-MM-DD)
        days_dict: Dict[str, List[dict]] = {}
        for c in sorted_candles:
            ts_str = c.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                date_key = dt.date().isoformat()
            except Exception:
                date_key = ts_str[:10] if len(ts_str) >= 10 else "unknown"

            if date_key not in days_dict:
                days_dict[date_key] = []
            days_dict[date_key].append(c)

        trades = []
        total_pnl = 0.0
        winning_trades = 0
        losing_trades = 0
        peak_capital = self.initial_capital
        max_drawdown = 0.0
        current_capital = self.initial_capital

        for date_key, day_candles in days_dict.items():
            # Find ORB candles (09:15 to 09:30)
            orb_candles = []
            trade_candles = []
            for c in day_candles:
                ts_str = c.get("timestamp", "")
                try:
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    t = dt.time()
                except Exception:
                    t = None

                if t and t.hour == 9 and t.minute < 30:
                    orb_candles.append(c)
                else:
                    trade_candles.append(c)

            if not orb_candles:
                # If no explicit 9:15-9:30 candles, take first 3 candles as ORB
                orb_candles = day_candles[:3]
                trade_candles = day_candles[3:]

            if not orb_candles:
                continue

            orb_high = max(c.get("high", 0.0) for c in orb_candles)
            orb_low = min(c.get("low", float("inf")) for c in orb_candles)
            spread = orb_high - orb_low

            if spread <= 0:
                continue

            in_trade = False
            trade = None

            # Scan trade candles for breakout and management
            for i, c in enumerate(trade_candles):
                if not in_trade:
                    close_price = c.get("close", 0.0)
                    high_price = c.get("high", 0.0)
                    # Check breakout condition (close > orb_high or high > orb_high)
                    if close_price > orb_high or high_price > orb_high:
                        entry_price = max(orb_high, c.get("open", orb_high))
                        if close_price > orb_high:
                            entry_price = close_price
                        stop_loss = orb_low
                        target_1 = entry_price + 1.5 * spread
                        qty = self.quantity_per_trade

                        in_trade = True
                        trade = {
                            "symbol": symbol,
                            "date": date_key,
                            "entry_time": c.get("timestamp"),
                            "entry_price": entry_price,
                            "stop_loss": stop_loss,
                            "target": target_1,
                            "quantity": qty,
                            "status": "OPEN",
                            "exit_time": None,
                            "exit_price": None,
                            "exit_reason": None,
                            "pnl": 0.0
                        }
                else:
                    high = c.get("high", 0.0)
                    low = c.get("low", 0.0)
                    close = c.get("close", 0.0)
                    ts = c.get("timestamp")

                    hit_sl = low <= trade["stop_loss"]
                    hit_target = high >= trade["target"]

                    if hit_sl and hit_target:
                        if abs(trade["stop_loss"] - low) < abs(high - trade["target"]):
                            exit_price = trade["stop_loss"]
                            exit_reason = "STOP_LOSS_HIT"
                        else:
                            exit_price = trade["target"]
                            exit_reason = "TARGET_HIT"
                    elif hit_sl:
                        exit_price = trade["stop_loss"]
                        exit_reason = "STOP_LOSS_HIT"
                    elif hit_target:
                        exit_price = trade["target"]
                        exit_reason = "TARGET_HIT"
                    elif i == len(trade_candles) - 1:
                        exit_price = close
                        exit_reason = "EOD_SQUARE_OFF"
                    else:
                        continue

                    trade["exit_time"] = ts
                    trade["exit_price"] = exit_price
                    trade["status"] = "CLOSED"
                    trade["exit_reason"] = exit_reason
                    pnl = (exit_price - trade["entry_price"]) * trade["quantity"]
                    trade["pnl"] = pnl

                    total_pnl += pnl
                    current_capital += pnl
                    if current_capital > peak_capital:
                        peak_capital = current_capital
                    drawdown = peak_capital - current_capital
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown

                    if pnl > 0:
                        winning_trades += 1
                    else:
                        losing_trades += 1

                    trades.append(trade)
                    in_trade = False
                    break

            if in_trade and trade:
                last_c = trade_candles[-1] if trade_candles else orb_candles[-1]
                exit_price = last_c.get("close", trade["entry_price"])
                trade["exit_time"] = last_c.get("timestamp")
                trade["exit_price"] = exit_price
                trade["status"] = "CLOSED"
                trade["exit_reason"] = "EOD_SQUARE_OFF"
                pnl = (exit_price - trade["entry_price"]) * trade["quantity"]
                trade["pnl"] = pnl

                total_pnl += pnl
                current_capital += pnl
                if current_capital > peak_capital:
                    peak_capital = current_capital
                drawdown = peak_capital - current_capital
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

                if pnl > 0:
                    winning_trades += 1
                else:
                    losing_trades += 1

                trades.append(trade)

        total_trades = winning_trades + losing_trades
        win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0

        gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
        gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.9 if gross_profit > 0 else 0.0)

        return {
            "symbol": symbol,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "total_profit": round(total_pnl, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown": round(max_drawdown, 2),
            "trades": trades
        }
