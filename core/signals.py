import pandas as pd
from typing import Optional
from core.data_fetcher import get_stock_data, NIFTY50_SYMBOLS
from core.indicators import add_all_indicators


def generate_signals(symbol: str) -> list[dict]:
    signals = []

    df = get_stock_data(symbol, period="6mo")
    if df is None or df.empty:
        return signals

    df = add_all_indicators(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    close = float(latest["Close"])

    if pd.notna(latest.get("RSI")):
        rsi = float(latest["RSI"])
        if rsi < 30:
            signals.append({
                "type": "BUY",
                "indicator": "RSI",
                "strength": "Strong",
                "message": f"RSI oversold at {rsi:.1f} - Potential buying opportunity",
                "price": close
            })
        elif rsi < 40:
            signals.append({
                "type": "BUY",
                "indicator": "RSI",
                "strength": "Moderate",
                "message": f"RSI approaching oversold at {rsi:.1f}",
                "price": close
            })
        elif rsi > 70:
            signals.append({
                "type": "SELL",
                "indicator": "RSI",
                "strength": "Strong",
                "message": f"RSI overbought at {rsi:.1f} - Consider booking profits",
                "price": close
            })
        elif rsi > 60:
            signals.append({
                "type": "SELL",
                "indicator": "RSI",
                "strength": "Moderate",
                "message": f"RSI approaching overbought at {rsi:.1f}",
                "price": close
            })

    if pd.notna(latest.get("MACD")) and pd.notna(prev.get("MACD")):
        macd_now = float(latest["MACD"])
        signal_now = float(latest["MACD_Signal"])
        macd_prev = float(prev["MACD"])
        signal_prev = float(prev["MACD_Signal"])

        if macd_prev < signal_prev and macd_now > signal_now:
            signals.append({
                "type": "BUY",
                "indicator": "MACD",
                "strength": "Strong",
                "message": "MACD bullish crossover - Momentum turning positive",
                "price": close
            })
        elif macd_prev > signal_prev and macd_now < signal_now:
            signals.append({
                "type": "SELL",
                "indicator": "MACD",
                "strength": "Strong",
                "message": "MACD bearish crossover - Momentum turning negative",
                "price": close
            })

    if pd.notna(latest.get("BB_Upper")) and pd.notna(latest.get("BB_Lower")):
        bb_upper = float(latest["BB_Upper"])
        bb_lower = float(latest["BB_Lower"])
        bb_mid = float(latest["BB_Middle"])

        if close <= bb_lower:
            signals.append({
                "type": "BUY",
                "indicator": "Bollinger Bands",
                "strength": "Moderate",
                "message": f"Price at lower Bollinger Band ({bb_lower:.2f}) - Potential bounce",
                "price": close
            })
        elif close >= bb_upper:
            signals.append({
                "type": "SELL",
                "indicator": "Bollinger Bands",
                "strength": "Moderate",
                "message": f"Price at upper Bollinger Band ({bb_upper:.2f}) - May face resistance",
                "price": close
            })

    if pd.notna(latest.get("SMA_20")) and pd.notna(latest.get("SMA_50")):
        sma20 = float(latest["SMA_20"])
        sma50 = float(latest["SMA_50"])
        prev_sma20 = float(prev["SMA_20"]) if pd.notna(prev.get("SMA_20")) else sma20
        prev_sma50 = float(prev["SMA_50"]) if pd.notna(prev.get("SMA_50")) else sma50

        if prev_sma20 < prev_sma50 and sma20 > sma50:
            signals.append({
                "type": "BUY",
                "indicator": "SMA Crossover",
                "strength": "Strong",
                "message": "Golden Cross - SMA 20 crossed above SMA 50",
                "price": close
            })
        elif prev_sma20 > prev_sma50 and sma20 < sma50:
            signals.append({
                "type": "SELL",
                "indicator": "SMA Crossover",
                "strength": "Strong",
                "message": "Death Cross - SMA 20 crossed below SMA 50",
                "price": close
            })

    if pd.notna(latest.get("MFI")):
        mfi = float(latest["MFI"])
        if mfi < 20:
            signals.append({
                "type": "BUY",
                "indicator": "MFI",
                "strength": "Moderate",
                "message": f"MFI oversold at {mfi:.1f} - Money flow turning positive",
                "price": close
            })
        elif mfi > 80:
            signals.append({
                "type": "SELL",
                "indicator": "MFI",
                "strength": "Moderate",
                "message": f"MFI overbought at {mfi:.1f} - Money flow weakening",
                "price": close
            })

    return signals


def get_all_signals() -> list[dict]:
    all_signals = []

    for symbol in NIFTY50_SYMBOLS[:20]:
        signals = generate_signals(symbol)
        for signal in signals:
            signal["symbol"] = symbol
            signal["name"] = symbol.replace(".NS", "")
            all_signals.append(signal)

    all_signals.sort(key=lambda x: (
        0 if x["strength"] == "Strong" else 1,
        0 if x["type"] == "BUY" else 1
    ))

    return all_signals[:30]
