import os
import json
import httpx
from typing import List, Dict, Optional, Any
from pathlib import Path

INSTRUMENTS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "upstox_instruments.json"
FULL_INSTRUMENTS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "upstox_instruments_full.json"


class UpstoxClient:
    """
    High-performance asynchronous client for Upstox API v2 / v3.
    Supports batch quote queries, real 5-level market depth,
    historical/intraday candles, and instrument key resolution.
    """
    BASE_URL = "https://api.upstox.com/v2"

    def __init__(self, token: Optional[str] = None):
        self.token = token if token is not None else os.getenv("UPSTOX_ACCESS_TOKEN", "")
        self._instruments_cache: Dict[str, Any] = {}
        self._load_instruments()

    @property
    def is_authenticated(self) -> bool:
        """Returns True if an access token is configured."""
        return bool(self.token and len(self.token.strip()) > 0)

    def _load_instruments(self):
        """Loads bundled mappings plus the full NSE equity master when present."""
        if INSTRUMENTS_FILE.exists():
            try:
                with open(INSTRUMENTS_FILE, "r") as f:
                    self._instruments_cache = json.load(f)
            except Exception:
                self._instruments_cache = {}

        if FULL_INSTRUMENTS_FILE.exists():
            try:
                with open(FULL_INSTRUMENTS_FILE, "r") as f:
                    full = json.load(f)
                for sym, entry in full.items():
                    self._instruments_cache.setdefault(sym, entry)
                    self._instruments_cache.setdefault(sym.upper(), entry)
            except Exception:
                pass

    def resolve_instrument_key(self, symbol: str) -> str:
        """
        Resolves an equity trading symbol or index to its Upstox instrument_key.
        Examples:
          'RELIANCE' -> 'NSE_EQ|INE002A01018'
          'TCS' -> 'NSE_EQ|INE467B01029'
          'NIFTY 50' -> 'NSE_INDEX|Nifty 50'
          'BANK NIFTY' -> 'NSE_INDEX|Nifty Bank'
        """
        if not symbol:
            return ""

        clean_sym = symbol.strip()
        # If already formatted with exchange/segment pipe (e.g. NSE_EQ|INE002A01018)
        if "|" in clean_sym:
            return clean_sym

        clean_sym_upper = clean_sym.upper().replace(".NS", "").replace(".BO", "").strip()

        # Check instruments cache
        if clean_sym in self._instruments_cache:
            entry = self._instruments_cache[clean_sym]
            if isinstance(entry, dict):
                return entry.get("instrument_key", f"NSE_EQ|{clean_sym_upper}")
            return str(entry)

        if clean_sym_upper in self._instruments_cache:
            entry = self._instruments_cache[clean_sym_upper]
            if isinstance(entry, dict):
                return entry.get("instrument_key", f"NSE_EQ|{clean_sym_upper}")
            return str(entry)

        # Standard indices fallbacks
        if clean_sym_upper in ("^NSEI", "NIFTY", "NIFTY 50", "NIFTY50"):
            return "NSE_INDEX|Nifty 50"
        if clean_sym_upper in ("^BSESN", "SENSEX"):
            return "BSE_INDEX|SENSEX"
        if clean_sym_upper in ("^INDIAVIX", "INDIA VIX", "INDIAVIX"):
            return "NSE_INDEX|India VIX"
        if clean_sym_upper in ("^NSEMDCP50", "^NSEMDCP100", "NIFTY MIDCAP 50", "NIFTY MIDCAP 100"):
            return "NSE_INDEX|Nifty Midcap 50"
        if clean_sym_upper in ("^NSEBANK", "BANKNIFTY", "BANK NIFTY", "NIFTY BANK"):
            return "NSE_INDEX|Nifty Bank"
        if clean_sym_upper in ("NIFTY 500", "NIFTY500"):
            return "NSE_INDEX|Nifty 500"
        if clean_sym_upper in ("^CNXIT", "NIFTY IT", "NIFTYIT"):
            return "NSE_INDEX|Nifty IT"
        if clean_sym_upper in ("NIFTY AUTO", "NIFTYAUTO"):
            return "NSE_INDEX|Nifty Auto"

        return f"NSE_EQ|{clean_sym_upper}"

    def get_instrument_info(self, symbol: str) -> Optional[dict]:
        """Returns metadata info for symbol if available in instruments cache."""
        clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "").strip()
        entry = self._instruments_cache.get(clean_sym)
        if isinstance(entry, dict):
            return entry
        elif isinstance(entry, str):
            return {"instrument_key": entry, "symbol": clean_sym}
        return None

    def _get_headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}" if self.token else ""
        }

    async def get_quotes(self, symbols: List[str]) -> Dict[str, dict]:
        """
        Fetches real-time market quotes in batch for up to 500 symbols.
        Returns parsed quotes mapped by symbol.
        """
        if not symbols:
            return {}

        key_to_orig: Dict[str, List[str]] = {}
        clean_to_orig: Dict[str, List[str]] = {}
        instrument_keys: List[str] = []

        for s in symbols:
            key = self.resolve_instrument_key(s)
            clean_s = s.upper().replace(".NS", "").replace(".BO", "").strip()

            if key not in instrument_keys:
                instrument_keys.append(key)

            key_to_orig.setdefault(key, []).append(s)
            key_to_orig.setdefault(key.replace("|", ":"), []).append(s)
            clean_to_orig.setdefault(clean_s, []).append(s)

        params = {"instrument_key": ",".join(instrument_keys)}
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"{self.BASE_URL}/market-quote/quotes", params=params, headers=headers)
                if resp.status_code != 200:
                    return {}
                payload = resp.json()
            except Exception:
                return {}

        raw_data = payload.get("data", {})
        quotes: Dict[str, dict] = {}

        for raw_key, item in raw_data.items():
            sym_part = raw_key.split(":")[-1] if ":" in raw_key else raw_key
            sym_part_upper = sym_part.upper()

            # Find matching original symbol(s)
            matched_syms = set()
            if raw_key in key_to_orig:
                matched_syms.update(key_to_orig[raw_key])
            alt_key = raw_key.replace(":", "|")
            if alt_key in key_to_orig:
                matched_syms.update(key_to_orig[alt_key])
            if sym_part_upper in clean_to_orig:
                matched_syms.update(clean_to_orig[sym_part_upper])
            if sym_part in clean_to_orig:
                matched_syms.update(clean_to_orig[sym_part])

            # If no direct match found, fallback to sym_part
            if not matched_syms:
                matched_syms = {sym_part}

            ohlc = item.get("ohlc", {}) or {}
            depth = item.get("depth", {}) or {}
            last_price = float(item.get("last_price", 0.0) or 0.0)
            vwap = float(item.get("average_price", 0.0) or item.get("vwap", 0.0) or last_price)
            net_change = float(item.get("net_change", 0.0) or 0.0)
            # Upstox `ohlc.close` is the latest traded close; derive the
            # previous close from net_change so change % is correct.
            close = float(ohlc.get("close", 0.0) or last_price)
            if net_change:
                close = last_price - net_change
            change_pct = round((net_change / close * 100), 2) if close > 0 else 0.0

            buy_depth = depth.get("buy", [])
            sell_depth = depth.get("sell", [])
            tot_buy = float(item.get("total_buy_quantity", sum(b.get("quantity", 0) for b in buy_depth)) or 0.0)
            tot_sell = float(item.get("total_sell_quantity", sum(s.get("quantity", 0) for s in sell_depth)) or 0.0)

            quote_data = {
                "symbol": sym_part,
                "instrument_key": item.get("instrument_token", raw_key),
                "last_price": last_price,
                "vwap": vwap,
                "open": float(ohlc.get("open", 0.0) or 0.0),
                "high": float(ohlc.get("high", 0.0) or 0.0),
                "low": float(ohlc.get("low", 0.0) or 0.0),
                "close": close,
                "volume": int(item.get("volume", 0) or 0),
                "net_change": net_change,
                "change_percent": change_pct,
                "lower_circuit": float(item.get("lower_circuit_limit", 0.0) or 0.0),
                "upper_circuit": float(item.get("upper_circuit_limit", 0.0) or 0.0),
                "timestamp": item.get("timestamp", ""),
                "depth": {
                    "buy": buy_depth,
                    "sell": sell_depth,
                    "total_buy_qty": tot_buy,
                    "total_sell_qty": tot_sell
                }
            }

            for sym in matched_syms:
                quotes[sym] = dict(quote_data, symbol=sym)

        return quotes

    async def get_candles(
        self,
        symbol: str,
        interval: str = "5minute",
        to_date: Optional[str] = None,
        from_date: Optional[str] = None,
    ) -> List[dict]:
        """
        Retrieves historical or intraday candlesticks.
        Interval options: '1minute', '5minute', '15minute', '30minute', 'day' (or '1m', '5m', '15m', '30m', '1d').
        Returns list of dicts in chronological order:
        [{'timestamp': ..., 'open': ..., 'high': ..., 'low': ..., 'close': ..., 'volume': ..., 'oi': ...}]
        """
        instrument_key = self.resolve_instrument_key(symbol)
        headers = self._get_headers()

        interval_map = {
            "1m": "1minute",
            "5m": "5minute",
            "15m": "15minute",
            "30m": "30minute",
            "1d": "day",
            "D": "day"
        }
        normalized_interval = interval_map.get(interval, interval)

        if to_date and from_date:
            url = f"{self.BASE_URL}/historical-candle/{instrument_key}/{normalized_interval}/{to_date}/{from_date}"
        elif to_date:
            url = f"{self.BASE_URL}/historical-candle/{instrument_key}/{normalized_interval}/{to_date}"
        else:
            url = f"{self.BASE_URL}/historical-candle/intraday/{instrument_key}/{normalized_interval}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    return []
                payload = resp.json()
            except Exception:
                return []

        candles_raw = payload.get("data", {}).get("candles", [])
        parsed_candles = []
        for c in candles_raw:
            if len(c) >= 6:
                parsed_candles.append({
                    "timestamp": c[0],
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4]),
                    "volume": int(c[5]),
                    "oi": int(c[6]) if len(c) > 6 else 0
                })

        # Ensure candles are strictly sorted chronologically by timestamp
        parsed_candles.sort(key=lambda c: str(c["timestamp"]))
        return parsed_candles

    async def get_market_depth(self, symbol: str) -> dict:
        """
        Retrieves real-time 5-level DOM market depth for an equity.
        Provides both Upstox buy/sell nomenclature and DOM bids/asks.
        """
        quotes = await self.get_quotes([symbol])
        clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "").strip()
        q = quotes.get(symbol) or quotes.get(clean_sym)
        if not q:
            return {
                "symbol": clean_sym,
                "currentPrice": 0.0,
                "vwap": 0.0,
                "buy": [],
                "sell": [],
                "bids": [],
                "asks": [],
                "totalBidQty": 0.0,
                "totalAskQty": 0.0,
                "bidAskRatio": 0.0,
                "spread": 0.0,
                "spreadPercent": 0.0,
                "timestamp": "",
                "error": "No market depth available"
            }

        depth = q.get("depth", {})
        buy_orders = depth.get("buy", [])
        sell_orders = depth.get("sell", [])
        total_buy = depth.get("total_buy_qty", sum(b.get("quantity", 0) for b in buy_orders))
        total_sell = depth.get("total_sell_qty", sum(s.get("quantity", 0) for s in sell_orders))
        ratio = round(total_buy / total_sell, 2) if total_sell > 0 else 0.0

        best_bid = buy_orders[0]["price"] if buy_orders and len(buy_orders) > 0 else 0.0
        best_ask = sell_orders[0]["price"] if sell_orders and len(sell_orders) > 0 else 0.0
        spread = round(best_ask - best_bid, 2) if (best_ask > 0 and best_bid > 0) else 0.0

        return {
            "symbol": clean_sym,
            "currentPrice": q.get("last_price", 0.0),
            "vwap": q.get("vwap", 0.0),
            "buy": buy_orders,
            "sell": sell_orders,
            "bids": buy_orders,
            "asks": sell_orders,
            "totalBidQty": total_buy,
            "totalAskQty": total_sell,
            "bidAskRatio": ratio,
            "spread": spread,
            "spreadPercent": round((spread / q.get("last_price", 1.0)) * 100, 3) if q.get("last_price", 0) > 0 else 0.0,
            "timestamp": q.get("timestamp", "")
        }
