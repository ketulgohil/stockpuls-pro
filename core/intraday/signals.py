import logging
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any
from core.indicators import ema, rsi
from core.upstox.stream import upstox_engine

logger = logging.getLogger("confluence_signals")

class ConfluenceSignalEngine:
    """
    Confluence Buy Signal Engine for evaluating multi-factor intraday buy signals
    combining VWAP, EMAs (9 & 20), RSI momentum, and volume surge.
    """
    def __init__(self):
        pass

    def evaluate_signal(
        self,
        symbol: str,
        ltp: float,
        vwap: float,
        ema9: float,
        ema20: float,
        rsi: float,
        current_volume: int,
        avg_volume: float
    ) -> dict:
        """
        Evaluate multi-factor confluence buy signal.

        Checks:
        1. LTP > VWAP (Weight: 20 pts)
        2. EMA9 > EMA20 (Weight: 20 pts)
        3. LTP > EMA9 (Weight: 20 pts)
        4. RSI between 55 and 70 (Weight: 20 pts)
        5. Current Volume > 1.5x Average Volume (Weight: 20 pts)

        Total Score: 0 to 100.
        Qualified if Confluence Score >= 80.
        Invalidation Stop Loss: VWAP (or EMA20 as secondary).
        """
        score = 0
        factors = {}

        # 1. LTP > VWAP
        cond_vwap = ltp > vwap if vwap > 0 else True
        if cond_vwap:
            score += 20
        factors["ltp_above_vwap"] = cond_vwap

        # 2. EMA9 > EMA20
        cond_ema_cross = ema9 > ema20
        if cond_ema_cross:
            score += 20
        factors["ema9_above_ema20"] = cond_ema_cross

        # 3. LTP > EMA9
        cond_price_ema9 = ltp > ema9
        if cond_price_ema9:
            score += 20
        factors["ltp_above_ema9"] = cond_price_ema9

        # 4. RSI between 55 and 70
        cond_rsi = 55.0 <= rsi <= 70.0
        if cond_rsi:
            score += 20
        elif 50.0 <= rsi <= 75.0:  # Partial credit if close
            score += 10
        factors["rsi_bullish_momentum"] = cond_rsi

        # 5. Volume > 1.5x Average Volume
        cond_volume = avg_volume <= 0 or current_volume > 1.5 * avg_volume
        if cond_volume:
            score += 20
        elif avg_volume > 0 and current_volume > 1.2 * avg_volume:
            score += 10
        factors["volume_surge"] = cond_volume

        qualified = score >= 80
        invalidation_sl = vwap if vwap > 0 else ema20

        return {
            "symbol": symbol.upper().replace(".NS", "").replace(".BO", "").strip(),
            "qualified": qualified,
            "confluence_score": score,
            "invalidation_sl": invalidation_sl,
            "ltp": ltp,
            "vwap": vwap,
            "ema9": ema9,
            "ema20": ema20,
            "rsi": rsi,
            "current_volume": current_volume,
            "avg_volume": avg_volume,
            "factors": factors,
            "timestamp": datetime.now().isoformat()
        }

    def evaluate(self, symbol: str, engine: Optional[Any] = None) -> Optional[dict]:
        """
        Evaluate confluence signal for a symbol using market engine data.
        """
        eng = engine or upstox_engine
        clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "").strip()

        candles = eng.get_5m_candles(clean_sym)
        if not candles or len(candles) < 20:
            return None

        df = pd.DataFrame(candles)
        if "close" not in df.columns or "volume" not in df.columns:
            return None

        # Compute indicators
        closes = df["close"]
        ema9_series = ema(closes, 9)
        ema20_series = ema(closes, 20)
        rsi_series = rsi(closes, 14)

        latest_idx = len(df) - 1
        ltp = float(closes.iloc[latest_idx])
        ema9_val = float(ema9_series.iloc[latest_idx]) if not pd.isna(ema9_series.iloc[latest_idx]) else ltp
        ema20_val = float(ema20_series.iloc[latest_idx]) if not pd.isna(ema20_series.iloc[latest_idx]) else ltp
        rsi_val = float(rsi_series.iloc[latest_idx]) if not pd.isna(rsi_series.iloc[latest_idx]) else 50.0

        current_volume = int(df["volume"].iloc[latest_idx])
        avg_volume = float(df["volume"].rolling(20).mean().iloc[latest_idx])
        if pd.isna(avg_volume):
            avg_volume = float(df["volume"].mean())

        quotes = eng.get_latest_quotes()
        quote = quotes.get(clean_sym, {})
        vwap = quote.get("vwap", 0.0)
        if vwap <= 0:
            vwap = float((df["high"] + df["low"] + df["close"]) / 3).mean()

        return self.evaluate_signal(
            symbol=clean_sym,
            ltp=ltp,
            vwap=vwap,
            ema9=ema9_val,
            ema20=ema20_val,
            rsi=rsi_val,
            current_volume=current_volume,
            avg_volume=avg_volume
        )

    def scan_all(self, engine: Optional[Any] = None) -> List[dict]:
        """
        Scan all tracked symbols in the engine for qualified confluence signals.
        """
        eng = engine or upstox_engine
        symbols = getattr(eng, "symbols", [])
        signals = []
        for sym in symbols:
            result = self.evaluate(sym, engine=eng)
            if result and result.get("qualified"):
                signals.append(result)
        return signals
