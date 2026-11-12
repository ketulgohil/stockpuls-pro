import asyncio
import logging
from datetime import datetime, time
from typing import Dict, List, Optional, Any, Callable
from core.upstox.client import UpstoxClient

logger = logging.getLogger("upstox_stream")

from core.data_fetcher import ALL_SYMBOLS

NIFTY50_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK",
    "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "TATAMOTORS",
    "SUNPHARMA", "TITAN", "ULTRACEMCO", "NESTLEIND", "WIPRO",
    "ONGC", "TATASTEEL", "NTPC", "POWERGRID", "M&M",
    "JSWSTEEL", "ADANIENT", "ADANIPORTS", "TECHM", "HCLTECH",
    "BAJFINANCE", "BAJAJFINSV", "INDUSINDBK", "DRREDDY", "CIPLA",
    "DIVISLAB", "EICHERMOT", "GRASIM", "HEROMOTOCO", "HINDALCO",
    "TATACONSUM", "APOLLOHOSP", "COALINDIA", "BRITANNIA", "BPCL",
    "COLPAL", "SBILIFE", "HDFCLIFE", "BAJAJ-AUTO"
]

class UpstoxMarketEngine:
    """
    Background market engine that polls Upstox quotes, aggregates 5-minute candles,
    tracks the 09:15-09:30 IST opening range, and manages real-time broadcast queues/listeners.
    """
    def __init__(self, client: Optional[UpstoxClient] = None, symbols: Optional[List[str]] = None):
        self.client = client or UpstoxClient()
        self.symbols = symbols or ALL_SYMBOLS
        self._quotes: Dict[str, dict] = {}
        self._ticks: Dict[str, List[dict]] = {}  # raw ticks per symbol
        self._candles_5m: Dict[str, List[dict]] = {}  # aggregated 5m candles per symbol
        self._opening_ranges: Dict[str, dict] = {}  # high, low, locked status
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._subscribers: List[Callable] = []

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        if self._running:
            return
        self._running = True
        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._poll_loop())
        except RuntimeError:
            pass
        logger.info("🚀 UpstoxMarketEngine started.")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("🛑 UpstoxMarketEngine stopped.")

    async def poll_once(self):
        try:
            if self.client and hasattr(self.client, "get_quotes"):
                quotes = await self.client.get_quotes(self.symbols)
                if quotes:
                    now = datetime.now()
                    self._quotes = quotes
                    for sym, q in quotes.items():
                        ltp = q.get("last_price", 0.0)
                        vol = q.get("volume", 0)
                        if ltp > 0:
                            self.record_tick(sym, ltp, vol, now)
        except Exception as e:
            logger.error(f"Error in Upstox poll_once: {e}")

    async def _poll_loop(self):
        while self._running:
            await self.poll_once()
            await asyncio.sleep(1.5)

    def subscribe(self, callback: Callable):
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable):
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def broadcast(self, data: Any):
        for sub in list(self._subscribers):
            try:
                if asyncio.iscoroutinefunction(sub):
                    await sub(data)
                else:
                    sub(data)
            except Exception as e:
                logger.error(f"Error broadcasting to subscriber: {e}")

    def record_tick(self, symbol: str, price: float, volume: int, timestamp: datetime):
        clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "").strip()

        # Update quote cache
        self._quotes[clean_sym] = {
            "symbol": clean_sym,
            "last_price": price,
            "volume": volume,
            "timestamp": timestamp.isoformat()
        }

        # 1. Store tick
        if clean_sym not in self._ticks:
            self._ticks[clean_sym] = []
        self._ticks[clean_sym].append({"price": price, "volume": volume, "time": timestamp})

        # 2. Check Opening Range (09:15 to 09:30 IST)
        t_time = timestamp.time()
        orb_start = time(9, 15, 0)
        orb_end = time(9, 30, 0)

        if timestamp.hour == 9 and 15 <= timestamp.minute < 30:
            if clean_sym not in self._opening_ranges:
                self._opening_ranges[clean_sym] = {"high": price, "low": price, "locked": False}
            else:
                orb = self._opening_ranges[clean_sym]
                if not orb["locked"]:
                    if price > orb["high"]:
                        orb["high"] = price
                    if price < orb["low"]:
                        orb["low"] = price
        elif (timestamp.hour > 9 or (timestamp.hour == 9 and timestamp.minute >= 30)):
            if clean_sym in self._opening_ranges and not self._opening_ranges[clean_sym]["locked"]:
                orb = self._opening_ranges[clean_sym]
                orb["locked"] = True
                high = orb["high"]
                low = orb["low"]
                spread = high - low
                orb["spread_pct"] = round((spread / low) * 100, 3) if low > 0 else 0.0

        # Also ensure spread_pct is computed if locked
        if clean_sym in self._opening_ranges:
            orb = self._opening_ranges[clean_sym]
            if orb["low"] > 0:
                orb["spread_pct"] = round(((orb["high"] - orb["low"]) / orb["low"]) * 100, 3)

        # 3. Aggregate 5-minute candles
        minute_bucket = (timestamp.minute // 5) * 5
        bucket_time = timestamp.replace(minute=minute_bucket, second=0, microsecond=0).isoformat()

        if clean_sym not in self._candles_5m:
            self._candles_5m[clean_sym] = []

        candles = self._candles_5m[clean_sym]
        if candles and candles[-1]["timestamp"] == bucket_time:
            c = candles[-1]
            c["high"] = max(c["high"], price)
            c["low"] = min(c["low"], price)
            c["close"] = price
            c["volume"] += volume  # Accumulate incremental tick volume
        else:
            # New 5m candle - first tick of this bucket defines open
            candles.append({
                "timestamp": bucket_time,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume
            })
            if len(candles) > 100:
                self._candles_5m[clean_sym] = candles[-100:]

    def get_latest_quotes(self) -> Dict[str, dict]:
        return self._quotes

    def get_5m_candles(self, symbol: str) -> List[dict]:
        clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "").strip()
        return self._candles_5m.get(clean_sym, [])

    def get_opening_range(self, symbol: str) -> dict:
        clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "").strip()
        orb = self._opening_ranges.get(clean_sym, {"high": 0.0, "low": 0.0, "locked": False, "spread_pct": 0.0})
        if "spread_pct" not in orb and orb["low"] > 0:
            orb["spread_pct"] = round(((orb["high"] - orb["low"]) / orb["low"]) * 100, 3)
        return orb

# Global singleton instance
upstox_engine = UpstoxMarketEngine()
