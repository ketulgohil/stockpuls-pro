"""trader_core.dashboard.stitcher - CandleStitcher for dashboard chart data.

Stitches raw market ticks into completed 5-minute candles for dashboard
chart rendering. Maintains a bounded buffer of recent candles per symbol.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from ..calendar import IST


class CandleStitcher:
    """Stitches market data ticks into candles for dashboard charts."""

    def __init__(self, max_candles_per_symbol: int = 500):
        self.max_candles_per_symbol = max_candles_per_symbol
        self._candles: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = __import__("threading").Lock()

    def get_bars(
        self,
        symbol: str,
        interval: str = "5m",
        include_active: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get stitched candles for a symbol."""
        with self._lock:
            bars = list(self._candles.get(symbol.upper(), []))
        if not include_active and bars:
            bars = bars[:-1] if bars else bars
        return bars

    def seed_history(self, symbol: str, days: int = 60) -> List[Dict[str, Any]]:
        """Seed historical candles for a symbol (placeholder - uses empty data)."""
        return []

    def on_tick(
        self,
        symbol: str,
        price: float,
        timestamp: datetime.datetime,
        volume: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """Process a tick and return completed candle if a bar closed."""
        sym = symbol.upper().replace(".NS", "").replace(".BO", "")
        with self._lock:
            if sym not in self._candles:
                self._candles[sym] = []

            now_ist = timestamp.astimezone(IST) if timestamp.tzinfo else timestamp.replace(tzinfo=IST)
            bar_start = now_ist.replace(
                minute=(now_ist.minute // 5) * 5,
                second=0,
                microsecond=0,
            )

            candles = self._candles[sym]
            if candles and candles[-1]["start"] == bar_start.isoformat():
                # Update active bar
                last = candles[-1]
                last["high"] = max(last["high"], price)
                last["low"] = min(last["low"], price)
                last["close"] = price
                last["volume"] += volume
                return None
            else:
                # Close previous bar and start new one
                new_bar = {
                    "start": bar_start.isoformat(),
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": volume,
                }
                candles.append(new_bar)
                if len(candles) > self.max_candles_per_symbol:
                    candles.pop(0)
                return candles[-2] if len(candles) >= 2 else None

    def get_latest(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get the latest candle for a symbol."""
        with self._lock:
            bars = self._candles.get(symbol.upper(), [])
            return bars[-1] if bars else None
