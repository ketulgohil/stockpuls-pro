import pandas as pd
import numpy as np
from typing import Optional
from core.data_fetcher import get_stock_data


def detect_head_shoulders(df: pd.DataFrame) -> list[dict]:
    if df is None or len(df) < 50:
        return []
    
    patterns = []
    close = df["Close"].values
    high = df["High"].values
    
    for i in range(20, len(close) - 20):
        if (high[i] > high[i-10] and high[i] > high[i+10] and
            high[i-10] > high[i-20] and high[i+10] > high[i+20]):
            
            if abs(high[i-10] - high[i+10]) / high[i] < 0.05:
                patterns.append({
                    "type": "Head & Shoulders",
                    "date": df.index[i],
                    "price": round(float(close[i]), 2),
                    "signal": "SELL",
                    "description": "Bearish reversal pattern"
                })
    
    return patterns


def detect_double_top(df: pd.DataFrame) -> list[dict]:
    if df is None or len(df) < 40:
        return []
    
    patterns = []
    high = df["High"].values
    close = df["Close"].values
    
    for i in range(20, len(high) - 10):
        for j in range(i + 10, min(i + 30, len(high) - 5)):
            if (abs(high[i] - high[j]) / high[i] < 0.03 and
                high[i] > high[i-5] and high[i] > high[i+5] and
                high[j] > high[j-5] and high[j] > high[j+5]):
                
                neckline = min(close[i:j])
                if close[-1] < neckline:
                    patterns.append({
                        "type": "Double Top",
                        "date": df.index[j],
                        "price": round(float(close[j]), 2),
                        "signal": "SELL",
                        "description": "Bearish reversal pattern"
                    })
                break
    
    return patterns


def detect_double_bottom(df: pd.DataFrame) -> list[dict]:
    if df is None or len(df) < 40:
        return []
    
    patterns = []
    low = df["Low"].values
    close = df["Close"].values
    
    for i in range(20, len(low) - 10):
        for j in range(i + 10, min(i + 30, len(low) - 5)):
            if (abs(low[i] - low[j]) / low[i] < 0.03 and
                low[i] < low[i-5] and low[i] < low[i+5] and
                low[j] < low[j-5] and low[j] < low[j+5]):
                
                neckline = max(close[i:j])
                if close[-1] > neckline:
                    patterns.append({
                        "type": "Double Bottom",
                        "date": df.index[j],
                        "price": round(float(close[j]), 2),
                        "signal": "BUY",
                        "description": "Bullish reversal pattern"
                    })
                break
    
    return patterns


def detect_ascending_triangle(df: pd.DataFrame) -> list[dict]:
    if df is None or len(df) < 30:
        return []
    
    patterns = []
    high = df["High"].values
    low = df["Low"].values
    close = df["Close"].values
    
    resistance = max(high[-20:])
    
    flat_top = sum(1 for h in high[-20:] if abs(h - resistance) / resistance < 0.02) >= 3
    rising_bottom = low[-1] > low[-20]
    
    if flat_top and rising_bottom and close[-1] > resistance:
        patterns.append({
            "type": "Ascending Triangle",
            "date": df.index[-1],
            "price": round(float(close[-1]), 2),
            "signal": "BUY",
            "description": "Bullish continuation pattern"
        })
    
    return patterns


def detect_descending_triangle(df: pd.DataFrame) -> list[dict]:
    if df is None or len(df) < 30:
        return []
    
    patterns = []
    high = df["High"].values
    low = df["Low"].values
    close = df["Close"].values
    
    support = min(low[-20:])
    
    flat_bottom = sum(1 for l in low[-20:] if abs(l - support) / support < 0.02) >= 3
    falling_high = high[-1] < high[-20]
    
    if flat_bottom and falling_high and close[-1] < support:
        patterns.append({
            "type": "Descending Triangle",
            "date": df.index[-1],
            "price": round(float(close[-1]), 2),
            "signal": "SELL",
            "description": "Bearish continuation pattern"
        })
    
    return patterns


def detect_flags(df: pd.DataFrame) -> list[dict]:
    if df is None or len(df) < 30:
        return []
    
    patterns = []
    close = df["Close"].values
    
    recent_move = (close[-1] - close[-20]) / close[-20] * 100
    
    if abs(recent_move) > 15:
        consolidation = np.std(close[-10:]) / np.mean(close[-10:]) * 100
        
        if consolidation < 3:
            pattern_type = "Bull Flag" if recent_move > 0 else "Bear Flag"
            patterns.append({
                "type": pattern_type,
                "date": df.index[-1],
                "price": round(float(close[-1]), 2),
                "signal": "BUY" if recent_move > 0 else "SELL",
                "description": f"{'Bullish' if recent_move > 0 else 'Bearish'} continuation pattern"
            })
    
    return patterns


def detect_all_patterns(symbol: str) -> list[dict]:
    df = get_stock_data(symbol, period="6mo")
    if df is None or df.empty:
        return []
    
    all_patterns = []
    all_patterns.extend(detect_head_shoulders(df))
    all_patterns.extend(detect_double_top(df))
    all_patterns.extend(detect_double_bottom(df))
    all_patterns.extend(detect_ascending_triangle(df))
    all_patterns.extend(detect_descending_triangle(df))
    all_patterns.extend(detect_flags(df))
    
    return all_patterns
