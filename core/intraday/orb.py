import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from core.upstox.stream import upstox_engine

logger = logging.getLogger("orb_scanner")

class ORBScanner:
    """
    Opening Range Breakout (ORB) Scanner for detecting bullish breakouts
    above the 09:15-09:30 IST opening range high with volume and VWAP confirmation.
    """
    def __init__(self):
        pass

    def evaluate_breakout(
        self,
        symbol: str,
        orb_range: dict,
        current_candle: dict,
        avg_volume: float,
        vwap: float
    ) -> Optional[dict]:
        """
        Evaluate whether the current candle forms a valid bullish ORB breakout.

        Checks:
        1. Opening range is locked (or locked key is True / missing).
        2. Candle close > Opening Range High.
        3. Candle close > VWAP.
        4. Candle volume > 1.3 * Average Volume.
        """
        if not orb_range or orb_range.get("locked") is False:
            return None

        orb_high = orb_range.get("high", 0.0)
        orb_low = orb_range.get("low", 0.0)

        if orb_high <= 0 or orb_low <= 0:
            return None

        close_price = current_candle.get("close", 0.0)
        volume = current_candle.get("volume", 0)

        # Conditions check
        is_above_high = close_price > orb_high
        is_above_vwap = vwap <= 0 or close_price > vwap  # if vwap not provided (<=0), bypass or require >0
        if vwap > 0:
            is_above_vwap = close_price > vwap
        else:
            is_above_vwap = True

        is_volume_surge = avg_volume <= 0 or volume > 1.3 * avg_volume

        if is_above_high and is_above_vwap and is_volume_surge:
            spread = orb_high - orb_low
            entry_price = close_price
            stop_loss = orb_low
            target_1 = entry_price + 1.5 * spread
            target_2 = entry_price + 2.5 * spread

            return {
                "symbol": symbol.upper().replace(".NS", "").replace(".BO", "").strip(),
                "status": "BULLISH_ORB_BREAKOUT",
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "target_1": target_1,
                "target_2": target_2,
                "spread": spread,
                "volume": volume,
                "avg_volume": avg_volume,
                "orb_high": orb_high,
                "orb_low": orb_low,
                "vwap": vwap,
                "timestamp": current_candle.get("timestamp", datetime.now().isoformat())
            }

        return None

    def scan(self, symbol: str, engine: Optional[Any] = None) -> Optional[dict]:
        """
        Scan a single symbol using the market engine.
        """
        eng = engine or upstox_engine
        clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "").strip()

        orb_range = eng.get_opening_range(clean_sym)
        candles = eng.get_5m_candles(clean_sym)

        if not candles or not orb_range or not orb_range.get("locked", False):
            return None

        current_candle = candles[-1]

        # Calculate average volume over available candles (up to last 20)
        recent_candles = candles[-20:]
        avg_volume = sum(c.get("volume", 0) for c in recent_candles) / len(recent_candles) if recent_candles else 0.0

        # Get VWAP from quotes or estimate from recent candles (typical price mean)
        quotes = eng.get_latest_quotes()
        quote = quotes.get(clean_sym, {})
        vwap = quote.get("vwap", 0.0)
        if vwap <= 0 and candles:
            # Estimate VWAP as average close or typical price of candles
            vwap = sum((c["high"] + c["low"] + c["close"]) / 3 for c in recent_candles) / len(recent_candles)

        return self.evaluate_breakout(clean_sym, orb_range, current_candle, avg_volume, vwap)

    def scan_all(self, engine: Optional[Any] = None) -> List[dict]:
        """
        Scan all tracked symbols in the engine for ORB breakouts.
        """
        eng = engine or upstox_engine
        symbols = getattr(eng, "symbols", [])
        breakouts = []
        for sym in symbols:
            result = self.scan(sym, engine=eng)
            if result:
                breakouts.append(result)
        return breakouts
