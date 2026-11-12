import pandas as pd
from typing import Optional
from core import upstox_data
from core.data_fetcher import ALL_SYMBOLS, get_stock_data
from core.indicators import add_all_indicators


def get_market_breadth() -> dict:
    symbols = ALL_SYMBOLS

    advancing = 0
    declining = 0
    unchanged = 0
    above_sma20 = 0
    above_sma50 = 0
    total = 0

    quotes = upstox_data.get_quotes(symbols) or {}

    for symbol in symbols:
        try:
            q = quotes.get(symbol)
            if not q:
                continue

            total += 1
            change_pct = float(q.get("changePercent", 0) or 0)

            if change_pct > 0:
                advancing += 1
            elif change_pct < 0:
                declining += 1
            else:
                unchanged += 1

            df = get_stock_data(symbol, period="1y", interval="1d")
            if df is None or df.empty:
                continue
            df = add_all_indicators(df)
            latest = df.iloc[-1]
            current = float(latest["Close"])

            if pd.notna(latest.get("SMA_20")) and current > float(latest["SMA_20"]):
                above_sma20 += 1
            if pd.notna(latest.get("SMA_50")) and current > float(latest["SMA_50"]):
                above_sma50 += 1
        except Exception:
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
