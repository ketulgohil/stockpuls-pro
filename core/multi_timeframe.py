import pandas as pd
import numpy as np
from typing import Optional
from core.data_fetcher import get_stock_data
from core.indicators import add_all_indicators, rsi, macd, sma, ema


def multi_timeframe_analysis(symbol: str) -> dict:
    timeframes = {
        "daily": {"period": "3mo", "interval": "1d"},
        "weekly": {"period": "1y", "interval": "1wk"},
        "monthly": {"period": "2y", "interval": "1mo"}
    }
    
    results = {}
    
    for tf_name, tf_config in timeframes.items():
        try:
            df = get_stock_data(symbol, period=tf_config["period"], interval=tf_config["interval"])
            
            if df is None or df.empty:
                continue
            
            df = add_all_indicators(df)
            latest = df.iloc[-1]
            
            trend = "NEUTRAL"
            if pd.notna(latest.get("SMA_20")) and pd.notna(latest.get("SMA_50")):
                if latest["SMA_20"] > latest["SMA_50"]:
                    trend = "BULLISH"
                elif latest["SMA_20"] < latest["SMA_50"]:
                    trend = "BEARISH"
            
            results[tf_name] = {
                "price": round(float(latest["Close"]), 2),
                "trend": trend,
                "rsi": round(float(latest["RSI"]), 2) if pd.notna(latest.get("RSI")) else None,
                "macd": round(float(latest["MACD"]), 2) if pd.notna(latest.get("MACD")) else None,
                "sma20": round(float(latest["SMA_20"]), 2) if pd.notna(latest.get("SMA_20")) else None,
                "sma50": round(float(latest["SMA_50"]), 2) if pd.notna(latest.get("SMA_50")) else None,
                "sma200": round(float(latest["SMA_200"]), 2) if pd.notna(latest.get("SMA_200")) else None,
                "change": round(float(latest["Close"] - df["Close"].iloc[-2]), 2) if len(df) > 1 else 0
            }
        except Exception as e:
            print(f"Error in {tf_name}: {e}")
            continue
    
    overall_signal = "NEUTRAL"
    if results:
        bullish_count = sum(1 for r in results.values() if r["trend"] == "BULLISH")
        bearish_count = sum(1 for r in results.values() if r["trend"] == "BEARISH")
        
        if bullish_count > bearish_count:
            overall_signal = "BUY"
        elif bearish_count > bullish_count:
            overall_signal = "SELL"
    
    return {
        "symbol": symbol,
        "timeframes": results,
        "overallSignal": overall_signal
    }


def custom_strategy_backtest(
    symbol: str,
    strategy_name: str,
    buy_conditions: dict,
    sell_conditions: dict,
    period: str = "1y",
    initial_capital: float = 100000
) -> dict:
    df = get_stock_data(symbol, period=period)
    if df is None or df.empty:
        return {"error": "No data found"}
    
    df = add_all_indicators(df)
    
    capital = initial_capital
    shares = 0
    trades = []
    entry_price = 0
    
    for i in range(1, len(df)):
        row = df.iloc[i]
        price = row["Close"]
        date = df.index[i]
        
        buy_signal = True
        for indicator, condition in buy_conditions.items():
            val = row.get(indicator)
            if pd.isna(val):
                buy_signal = False
                break
            
            op = condition.get("op", ">")
            target = condition.get("value", 0)
            
            if op == ">" and not (val > target):
                buy_signal = False
                break
            elif op == "<" and not (val < target):
                buy_signal = False
                break
            elif op == ">=" and not (val >= target):
                buy_signal = False
                break
            elif op == "<=" and not (val <= target):
                buy_signal = False
                break
        
        sell_signal = True
        for indicator, condition in sell_conditions.items():
            val = row.get(indicator)
            if pd.isna(val):
                sell_signal = False
                break
            
            op = condition.get("op", ">")
            target = condition.get("value", 0)
            
            if op == ">" and not (val > target):
                sell_signal = False
                break
            elif op == "<" and not (val < target):
                sell_signal = False
                break
        
        if buy_signal and shares == 0:
            shares = int(capital / price)
            entry_price = price
            capital -= shares * price
            trades.append({
                "date": date,
                "type": "BUY",
                "price": round(price, 2),
                "shares": shares
            })
        
        elif sell_signal and shares > 0:
            capital += shares * price
            pnl = (price - entry_price) * shares
            trades.append({
                "date": date,
                "type": "SELL",
                "price": round(price, 2),
                "shares": shares,
                "pnl": round(pnl, 2),
                "pnl_percent": round(((price - entry_price) / entry_price) * 100, 2)
            })
            shares = 0
    
    final_equity = capital + shares * df["Close"].iloc[-1]
    total_return = ((final_equity - initial_capital) / initial_capital) * 100
    
    winning = [t for t in trades if t.get("pnl", 0) > 0]
    losing = [t for t in trades if t.get("pnl", 0) < 0]
    
    return {
        "symbol": symbol,
        "strategy": strategy_name,
        "period": period,
        "initial_capital": initial_capital,
        "final_equity": round(final_equity, 2),
        "total_return": round(total_return, 2),
        "total_trades": len([t for t in trades if t["type"] == "SELL"]),
        "win_rate": round(len(winning) / max(len([t for t in trades if t["type"] == "SELL"]), 1) * 100, 2),
        "trades": trades
    }
