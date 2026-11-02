import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from core.upstox.client import UpstoxClient

logger = logging.getLogger("upstox_stream")

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
    tracks the 09:15-09:30 IST opening range, and manages real-time broadcast queues.
    """
    def __init__(self, client: Optional[UpstoxClient] = None):
        self.client = client or UpstoxClient()
        self._quotes: Dict[str, dict] = {}
        self._ticks: Dict[str, List[dict]] = {}  # raw ticks per symbol
        self._candles_5m: Dict[str, List[dict]] = {}  # aggregated 5m candles per symbol
        self._opening_ranges: Dict[str, dict] = {}  # high, low, locked status
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._subscribers: List[asyncio.Queue] = []

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

    async def _poll_loop(self):
        while self._running:
            try:
                quotes = await self.client.get_quotes(NIFTY50_SYMBOLS)
                if quotes:
                    now = datetime.now()
                    self._quotes = quotes
                    for sym, q in quotes.items():
                        ltp = q.get("last_price", 0.0)
                        vol = q.get("volume", 0)
                        if ltp > 0:
                            self.record_tick(sym, ltp, vol, now)

                    # Broadcast to subscribers
                    for q_queue in self._subscribers:
                        try:
                            q_queue.put_nowait({"type": "quotes", "quotes": quotes, "timestamp": datetime.now().isoformat()})
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"Error in Upstox poll loop: {e}")

            await asyncio.sleep(1.5)

    def record_tick(self, symbol: str, price: float, volume: int, timestamp: datetime):
        clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "").strip()

        # 1. Store tick
        if clean_sym not in self._ticks:
            self._ticks[clean_sym] = []
        self._ticks[clean_sym].append({"price": price, "volume": volume, "time": timestamp})

        # 2. Check Opening Range (09:15 to 09:30 IST)
        if timestamp.hour == 9 and 15 <= timestamp.minute < 30:
            if clean_sym not in self._opening_ranges:
                self._opening_ranges[clean_sym] = {"high": price, "low": price, "locked": False}
            else:
                orb = self._opening_ranges[clean_sym]
                if price > orb["high"]:
                    orb["high"] = price
                if price < orb["low"]:
                    orb["low"] = price
        elif timestamp.hour >= 9 and timestamp.minute >= 30:
            if clean_sym in self._opening_ranges and not self._opening_ranges[clean_sym]["locked"]:
                orb = self._opening_ranges[clean_sym]
                orb["locked"] = True
                high = orb["high"]
                low = orb["low"]
                spread = high - low
                orb["spread_pct"] = round((spread / low) * 100, 3) if low > 0 else 0.0

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
            c["volume"] = max(c["volume"], volume)  # cumulative volume or snapshot
        else:
            # New 5m candle
            prev_close = candles[-1]["close"] if candles else price
            candles.append({
                "timestamp": bucket_time,
                "open": prev_close,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume
            })
            # Keep last 100 candles max
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
