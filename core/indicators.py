import pandas as pd
import numpy as np
from typing import Optional


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(window=length).mean()


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=length - 1, min_periods=length).mean()
    avg_loss = loss.ewm(com=length - 1, min_periods=length).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(series: pd.Series, length: int = 20, std: float = 2.0):
    middle = sma(series, length)
    rolling_std = series.rolling(window=length).std()
    upper = middle + (rolling_std * std)
    lower = middle - (rolling_std * std)
    return upper, middle, lower


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=length).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14):
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    atr_val = atr(high, low, close, length)
    plus_di = 100 * ema(plus_dm, length) / atr_val
    minus_di = 100 * ema(minus_dm, length) / atr_val
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx_val = ema(dx, length)
    return adx_val, plus_di, minus_di


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    obv_val = [0]
    for i in range(1, len(close)):
        if close.iloc[i] > close.iloc[i - 1]:
            obv_val.append(obv_val[-1] + volume.iloc[i])
        elif close.iloc[i] < close.iloc[i - 1]:
            obv_val.append(obv_val[-1] - volume.iloc[i])
        else:
            obv_val.append(obv_val[-1])
    return pd.Series(obv_val, index=close.index)


def mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, length: int = 14) -> pd.Series:
    typical_price = (high + low + close) / 3
    money_flow = typical_price * volume
    delta = typical_price.diff()
    positive_flow = money_flow.where(delta > 0, 0.0)
    negative_flow = money_flow.where(delta < 0, 0.0)
    positive_mf = positive_flow.rolling(window=length).sum()
    negative_mf = negative_flow.rolling(window=length).sum()
    mfi_val = 100 - (100 / (1 + positive_mf / negative_mf))
    return mfi_val


def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    typical_price = (high + low + close) / 3
    cumulative_tp_vol = (typical_price * volume).cumsum()
    cumulative_vol = volume.cumsum()
    return cumulative_tp_vol / cumulative_vol


def stoch(high: pd.Series, low: pd.Series, close: pd.Series, k: int = 14, d: int = 3):
    lowest_low = low.rolling(window=k).min()
    highest_high = high.rolling(window=k).max()
    stoch_k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    stoch_d = stoch_k.rolling(window=d).mean()
    return stoch_k, stoch_d


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    df["SMA_20"] = sma(close, 20)
    df["SMA_50"] = sma(close, 50)
    df["SMA_200"] = sma(close, 200)
    df["EMA_12"] = ema(close, 12)
    df["EMA_26"] = ema(close, 26)

    macd_line, signal_line, histogram = macd(close)
    df["MACD"] = macd_line
    df["MACD_Signal"] = signal_line
    df["MACD_Hist"] = histogram

    df["RSI"] = rsi(close)

    bb_upper, bb_middle, bb_lower = bollinger_bands(close)
    df["BB_Upper"] = bb_upper
    df["BB_Middle"] = bb_middle
    df["BB_Lower"] = bb_lower

    df["ATR"] = atr(high, low, close)

    adx_val, di_plus, di_minus = adx(high, low, close)
    df["ADX"] = adx_val
    df["DI_Plus"] = di_plus
    df["DI_Minus"] = di_minus

    df["OBV"] = obv(close, volume)
    df["MFI"] = mfi(high, low, close, volume)
    df["VWAP"] = vwap(high, low, close, volume)

    stoch_k, stoch_d = stoch(high, low, close)
    df["Stoch_K"] = stoch_k
    df["Stoch_D"] = stoch_d

    return df


def get_latest_indicators(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {}

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    indicators = {
        "close": round(float(latest["Close"]), 2),
        "change": round(float(latest["Close"] - prev["Close"]), 2),
        "changePercent": round(float((latest["Close"] - prev["Close"]) / prev["Close"] * 100), 2),
    }

    indicator_fields = [
        "RSI", "MACD", "MACD_Signal", "MACD_Hist",
        "SMA_20", "SMA_50", "SMA_200", "EMA_12", "EMA_26",
        "BB_Upper", "BB_Middle", "BB_Lower",
        "ATR", "ADX", "DI_Plus", "DI_Minus",
        "OBV", "MFI", "VWAP", "Stoch_K", "Stoch_D",
        "Ichimoku_Base", "Ichimoku_SpanA", "Ichimoku_SpanB"
    ]

    for field in indicator_fields:
        if field in latest.index and pd.notna(latest[field]):
            indicators[field] = round(float(latest[field]), 2)
        else:
            indicators[field] = None

    return indicators


def fibonacci_levels(df: pd.DataFrame) -> dict:
    if df is None or len(df) < 20:
        return {"levels": []}

    high = df["High"].max()
    low = df["Low"].min()
    diff = high - low

    levels = {
        "0.0": round(float(high), 2),
        "23.6": round(float(high - diff * 0.236), 2),
        "38.2": round(float(high - diff * 0.382), 2),
        "50.0": round(float(high - diff * 0.5), 2),
        "61.8": round(float(high - diff * 0.618), 2),
        "78.6": round(float(high - diff * 0.786), 2),
        "100.0": round(float(low), 2),
    }

    return {"levels": levels, "high": round(float(high), 2), "low": round(float(low), 2)}


def ichimoku_cloud(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    nine_period_high = high.rolling(window=9).max()
    nine_period_low = low.rolling(window=9).min()
    df["Ichimoku_SpanA"] = ((nine_period_high + nine_period_low) / 2).shift(26)

    twenty_six_period_high = high.rolling(window=26).max()
    twenty_six_period_low = low.rolling(window=26).min()
    df["Ichimoku_Base"] = ((twenty_six_period_high + twenty_six_period_low) / 2)

    fifty_two_period_high = high.rolling(window=52).max()
    fifty_two_period_low = low.rolling(window=52).min()
    df["Ichimoku_SpanB"] = ((fifty_two_period_high + fifty_two_period_low) / 2).shift(26)

    df["Ichimoku_Lagging"] = close.shift(-26)

    return df


def calculate_support_resistance(df: pd.DataFrame, window: int = 20) -> dict:
    if df is None or len(df) < window:
        return {"support": [], "resistance": []}

    close = df["Close"].values
    highs = df["High"].values
    lows = df["Low"].values

    support_levels = []
    resistance_levels = []

    for i in range(window, len(close) - window):
        if all(lows[i] <= lows[j] for j in range(i - window, i + window + 1)):
            support_levels.append(round(float(lows[i]), 2))
        if all(highs[i] >= highs[j] for j in range(i - window, i + window + 1)):
            resistance_levels.append(round(float(highs[i]), 2))

    support_levels = sorted(set(support_levels), reverse=True)[:3]
    resistance_levels = sorted(set(resistance_levels))[:3]

    return {
        "support": support_levels,
        "resistance": resistance_levels
    }
