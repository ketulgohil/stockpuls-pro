import pandas as pd
from typing import Optional
from core.data_fetcher import get_stock_data, NIFTY50_SYMBOLS
from core.indicators import add_all_indicators


def screen_stocks(
    rsi_below: Optional[float] = None,
    rsi_above: Optional[float] = None,
    macd_cross_up: Optional[bool] = None,
    price_above_sma: Optional[int] = None,
    price_below_sma: Optional[int] = None,
    volume_above_avg: Optional[float] = None,
    sector: Optional[str] = None,
    limit: int = 20
) -> list[dict]:
    results = []

    for symbol in NIFTY50_SYMBOLS[:30]:
        try:
            df = get_stock_data(symbol, period="3mo")
            if df is None or df.empty:
                continue

            df = add_all_indicators(df)
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest

            match = True

            if rsi_below is not None and (pd.isna(latest.get("RSI")) or latest["RSI"] > rsi_below):
                match = False
            if rsi_above is not None and (pd.isna(latest.get("RSI")) or latest["RSI"] < rsi_above):
                match = False

            if macd_cross_up:
                if pd.isna(latest.get("MACD")) or pd.isna(prev.get("MACD")):
                    match = False
                elif not (prev["MACD"] < prev["MACD_Signal"] and latest["MACD"] > latest["MACD_Signal"]):
                    match = False

            if price_above_sma:
                sma_col = f"SMA_{price_above_sma}"
                if sma_col not in latest.index or pd.isna(latest[sma_col]):
                    match = False
                elif latest["Close"] < latest[sma_col]:
                    match = False

            if price_below_sma:
                sma_col = f"SMA_{price_below_sma}"
                if sma_col not in latest.index or pd.isna(latest[sma_col]):
                    match = False
                elif latest["Close"] > latest[sma_col]:
                    match = False

            if volume_above_avg:
                if "Volume" in df.columns:
                    avg_vol = df["Volume"].mean()
                    if latest["Volume"] < avg_vol * volume_above_avg:
                        match = False

            if match:
                results.append({
                    "symbol": symbol,
                    "name": symbol.replace(".NS", ""),
                    "price": round(float(latest["Close"]), 2),
                    "change": round(float(latest["Close"] - prev["Close"]), 2),
                    "changePercent": round(float((latest["Close"] - prev["Close"]) / prev["Close"] * 100), 2),
                    "rsi": round(float(latest["RSI"]), 2) if pd.notna(latest.get("RSI")) else None,
                    "macd": round(float(latest["MACD"]), 2) if pd.notna(latest.get("MACD")) else None,
                    "volume": int(latest["Volume"]),
                })

                if len(results) >= limit:
                    break
        except Exception as e:
            continue

    return results
