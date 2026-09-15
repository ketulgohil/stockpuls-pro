import pandas as pd
import numpy as np
from typing import Optional
from core.data_fetcher import get_stock_data, ALL_SYMBOLS


def calculate_correlation(symbols: list[str], period: str = "6mo") -> dict:
    prices = {}
    
    for symbol in symbols:
        try:
            df = get_stock_data(symbol, period=period)
            if df is not None and not df.empty:
                prices[symbol.replace(".NS", "")] = df["Close"]
        except:
            continue
    
    if len(prices) < 2:
        return {"error": "Need at least 2 stocks with data"}
    
    df_prices = pd.DataFrame(prices)
    df_prices = df_prices.dropna()
    
    if df_prices.empty:
        return {"error": "No common dates found"}
    
    correlation = df_prices.corr()
    
    result = {
        "symbols": list(prices.keys()),
        "correlation": {}
    }
    
    for sym1 in correlation.columns:
        result["correlation"][sym1] = {}
        for sym2 in correlation.columns:
            result["correlation"][sym1][sym2] = round(float(correlation.loc[sym1, sym2]), 3)
    
    return result


def get_most_correlated(symbol: str, limit: int = 10) -> list[dict]:
    symbol = symbol if symbol.endswith(".NS") else symbol + ".NS"
    
    df_main = get_stock_data(symbol, period="6mo")
    if df_main is None or df_main.empty:
        return []
    
    results = []
    test_symbols = [s for s in ALL_SYMBOLS if s != symbol][:30]
    
    for other_symbol in test_symbols:
        try:
            df_other = get_stock_data(other_symbol, period="6mo")
            if df_other is not None and not df_other.empty:
                combined = pd.DataFrame({
                    "main": df_main["Close"],
                    "other": df_other["Close"]
                }).dropna()
                
                if len(combined) > 20:
                    corr = combined["main"].corr(combined["other"])
                    results.append({
                        "symbol": other_symbol,
                        "name": other_symbol.replace(".NS", ""),
                        "correlation": round(float(corr), 3)
                    })
        except:
            continue
    
    results.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    return results[:limit]
