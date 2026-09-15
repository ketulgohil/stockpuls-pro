import pandas as pd
import numpy as np
from typing import Optional
from core.data_fetcher import get_stock_data
from core.indicators import add_all_indicators, rsi, macd, sma, ema


def backtest_rsi(
    symbol: str,
    period: str = "1y",
    rsi_buy: float = 30,
    rsi_sell: float = 70,
    initial_capital: float = 100000
) -> dict:
    df = get_stock_data(symbol, period=period)
    if df is None or df.empty:
        return {"error": "No data found"}
    
    df["RSI"] = rsi(df["Close"])
    
    capital = initial_capital
    shares = 0
    trades = []
    equity_curve = []
    entry_price = 0
    
    for i in range(14, len(df)):
        rsi_val = df["RSI"].iloc[i]
        price = df["Close"].iloc[i]
        date = df.index[i]
        
        if pd.isna(rsi_val):
            equity_curve.append({"date": date, "equity": capital + shares * price})
            continue
        
        if rsi_val < rsi_buy and shares == 0:
            shares = int(capital / price)
            entry_price = price
            capital -= shares * price
            trades.append({
                "date": date,
                "type": "BUY",
                "price": round(price, 2),
                "rsi": round(rsi_val, 2),
                "shares": shares
            })
        
        elif rsi_val > rsi_sell and shares > 0:
            capital += shares * price
            pnl = (price - entry_price) * shares
            pnl_percent = ((price - entry_price) / entry_price) * 100
            trades.append({
                "date": date,
                "type": "SELL",
                "price": round(price, 2),
                "rsi": round(rsi_val, 2),
                "shares": shares,
                "pnl": round(pnl, 2),
                "pnl_percent": round(pnl_percent, 2)
            })
            shares = 0
        
        equity_curve.append({"date": date, "equity": round(capital + shares * price, 2)})
    
    final_equity = capital + shares * df["Close"].iloc[-1]
    total_return = ((final_equity - initial_capital) / initial_capital) * 100
    
    winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
    losing_trades = [t for t in trades if t.get("pnl", 0) < 0]
    
    return {
        "symbol": symbol,
        "strategy": f"RSI ({rsi_buy}/{rsi_sell})",
        "period": period,
        "initial_capital": initial_capital,
        "final_equity": round(final_equity, 2),
        "total_return": round(total_return, 2),
        "total_trades": len([t for t in trades if t["type"] == "SELL"]),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": round(len(winning_trades) / max(len([t for t in trades if t["type"] == "SELL"]), 1) * 100, 2),
        "trades": trades,
        "equity_curve": equity_curve
    }


def backtest_macd(
    symbol: str,
    period: str = "1y",
    initial_capital: float = 100000
) -> dict:
    df = get_stock_data(symbol, period=period)
    if df is None or df.empty:
        return {"error": "No data found"}
    
    macd_line, signal_line, _ = macd(df["Close"])
    df["MACD"] = macd_line
    df["MACD_Signal"] = signal_line
    
    capital = initial_capital
    shares = 0
    trades = []
    equity_curve = []
    entry_price = 0
    
    for i in range(26, len(df)):
        macd_val = df["MACD"].iloc[i]
        signal_val = df["MACD_Signal"].iloc[i]
        prev_macd = df["MACD"].iloc[i-1]
        prev_signal = df["MACD_Signal"].iloc[i-1]
        price = df["Close"].iloc[i]
        date = df.index[i]
        
        if pd.isna(macd_val) or pd.isna(prev_macd):
            equity_curve.append({"date": date, "equity": capital + shares * price})
            continue
        
        if prev_macd < prev_signal and macd_val > signal_val and shares == 0:
            shares = int(capital / price)
            entry_price = price
            capital -= shares * price
            trades.append({
                "date": date,
                "type": "BUY",
                "price": round(price, 2),
                "macd": round(macd_val, 2),
                "shares": shares
            })
        
        elif prev_macd > prev_signal and macd_val < signal_val and shares > 0:
            capital += shares * price
            pnl = (price - entry_price) * shares
            pnl_percent = ((price - entry_price) / entry_price) * 100
            trades.append({
                "date": date,
                "type": "SELL",
                "price": round(price, 2),
                "macd": round(macd_val, 2),
                "shares": shares,
                "pnl": round(pnl, 2),
                "pnl_percent": round(pnl_percent, 2)
            })
            shares = 0
        
        equity_curve.append({"date": date, "equity": round(capital + shares * price, 2)})
    
    final_equity = capital + shares * df["Close"].iloc[-1]
    total_return = ((final_equity - initial_capital) / initial_capital) * 100
    
    winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
    losing_trades = [t for t in trades if t.get("pnl", 0) < 0]
    
    return {
        "symbol": symbol,
        "strategy": "MACD Crossover",
        "period": period,
        "initial_capital": initial_capital,
        "final_equity": round(final_equity, 2),
        "total_return": round(total_return, 2),
        "total_trades": len([t for t in trades if t["type"] == "SELL"]),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": round(len(winning_trades) / max(len([t for t in trades if t["type"] == "SELL"]), 1) * 100, 2),
        "trades": trades,
        "equity_curve": equity_curve
    }


def backtest_sma_crossover(
    symbol: str,
    period: str = "1y",
    fast_period: int = 20,
    slow_period: int = 50,
    initial_capital: float = 100000
) -> dict:
    df = get_stock_data(symbol, period=period)
    if df is None or df.empty:
        return {"error": "No data found"}
    
    df["SMA_Fast"] = sma(df["Close"], fast_period)
    df["SMA_Slow"] = sma(df["Close"], slow_period)
    
    capital = initial_capital
    shares = 0
    trades = []
    equity_curve = []
    entry_price = 0
    
    for i in range(slow_period + 1, len(df)):
        fast_now = df["SMA_Fast"].iloc[i]
        slow_now = df["SMA_Slow"].iloc[i]
        fast_prev = df["SMA_Fast"].iloc[i-1]
        slow_prev = df["SMA_Slow"].iloc[i-1]
        price = df["Close"].iloc[i]
        date = df.index[i]
        
        if pd.isna(fast_now) or pd.isna(slow_now) or pd.isna(fast_prev):
            equity_curve.append({"date": date, "equity": capital + shares * price})
            continue
        
        if fast_prev < slow_prev and fast_now > slow_now and shares == 0:
            shares = int(capital / price)
            entry_price = price
            capital -= shares * price
            trades.append({
                "date": date,
                "type": "BUY",
                "price": round(price, 2),
                "shares": shares
            })
        
        elif fast_prev > slow_prev and fast_now < slow_now and shares > 0:
            capital += shares * price
            pnl = (price - entry_price) * shares
            pnl_percent = ((price - entry_price) / entry_price) * 100
            trades.append({
                "date": date,
                "type": "SELL",
                "price": round(price, 2),
                "shares": shares,
                "pnl": round(pnl, 2),
                "pnl_percent": round(pnl_percent, 2)
            })
            shares = 0
        
        equity_curve.append({"date": date, "equity": round(capital + shares * price, 2)})
    
    final_equity = capital + shares * df["Close"].iloc[-1]
    total_return = ((final_equity - initial_capital) / initial_capital) * 100
    
    winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
    losing_trades = [t for t in trades if t.get("pnl", 0) < 0]
    
    return {
        "symbol": symbol,
        "strategy": f"SMA Crossover ({fast_period}/{slow_period})",
        "period": period,
        "initial_capital": initial_capital,
        "final_equity": round(final_equity, 2),
        "total_return": round(total_return, 2),
        "total_trades": len([t for t in trades if t["type"] == "SELL"]),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": round(len(winning_trades) / max(len([t for t in trades if t["type"] == "SELL"]), 1) * 100, 2),
        "trades": trades,
        "equity_curve": equity_curve
    }
