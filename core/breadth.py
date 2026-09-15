import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from core.data_fetcher import NIFTY50_SYMBOLS


def get_market_breadth() -> dict:
    symbols = NIFTY50_SYMBOLS
    
    advancing = 0
    declining = 0
    unchanged = 0
    above_sma20 = 0
    above_sma50 = 0
    total = 0
    
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            
            if len(hist) >= 2:
                total += 1
                current = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[-2]
                
                if current > prev:
                    advancing += 1
                elif current < prev:
                    declining += 1
                else:
                    unchanged += 1
                
                if len(hist) >= 20:
                    sma20 = hist["Close"].rolling(20).mean().iloc[-1]
                    if current > sma20:
                        above_sma20 += 1
                
                if len(hist) >= 50:
                    sma50 = hist["Close"].rolling(50).mean().iloc[-1]
                    if current > sma50:
                        above_sma50 += 1
        except:
            continue
    
    ad_ratio = advancing / max(declining, 1)
    
    return {
        "total": total,
        "advancing": advancing,
        "declining": declining,
        "unchanged": unchanged,
        "adRatio": round(ad_ratio, 2),
        "percentAdvancing": round(advancing / max(total, 1) * 100, 1),
        "percentDeclining": round(declining / max(total, 1) * 100, 1),
        "aboveSma20": above_sma20,
        "aboveSma20Percent": round(above_sma20 / max(total, 1) * 100, 1),
        "aboveSma50": above_sma50,
        "aboveSma50Percent": round(above_sma50 / max(total, 1) * 100, 1),
        "breadthSignal": "BULLISH" if ad_ratio > 1.5 else "BEARISH" if ad_ratio < 0.7 else "NEUTRAL"
    }


def get_advance_decline_history() -> list[dict]:
    return [{"date": "Data limited", "note": "Use market hours for live data"}]
