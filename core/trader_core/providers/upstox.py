"""trader_core.providers.upstox - Upstox V3 REST Market Data Provider.

Implements Upstox V3 REST candle and market quote API integration:
- Resolves symbols into canonical instrument keys.
- Fetches and parses completed intraday candles.
- Validates candle integrity invariants.
- Fetches real-time market quotes and market depth.
- Maps error statuses to fail-closed ProviderError subclasses.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
import json
import logging
import os
from typing import Any, Dict, List, Optional, Set, Union
import urllib.error
import urllib.parse
import urllib.request

from ..calendar import IST, parse_ist_timestamp
from ..candle import Candle, validate_candle
from .base import (
    InstrumentInfo,
    InstrumentMaster,
    MarketDataProvider,
    ProviderAuthenticationError,
    ProviderCapability,
    ProviderConnectionError,
    ProviderDataError,
    ProviderRateLimitError,
    Quote,
)

_INTERVAL_MAP = {
    "1m": "1minute",
    "1min": "1minute",
    "1minute": "1minute",
    "5m": "5minute",
    "5min": "5minute",
    "5minute": "5minute",
    "15m": "15minute",
    "15min": "15minute",
    "15minute": "15minute",
    "30m": "30minute",
    "30min": "30minute",
    "30minute": "30minute",
    "45m": "45minute",
    "45min": "45minute",
    "45minute": "45minute",
    "60m": "60minute",
    "1h": "60minute",
    "60minute": "60minute",
    "1d": "day",
    "d": "day",
    "day": "day",
    "1day": "day",
    "30d": "month",
    "1mo": "month",
    "month": "month",
    "1month": "month",
}

_INTERVAL_SECONDS = {
    "1minute": 60,
    "5minute": 300,
    "15minute": 900,
    "30minute": 1800,
    "45minute": 2700,
    "60minute": 3600,
    "day": 86400,
    "month": 2592000,
}

logger = logging.getLogger(__name__)


def _find_credentials() -> Dict[str, str]:
    """Load credentials from environment or trader/credentials.json."""
    creds = {
        "api_key": os.getenv("UPSTOX_API_KEY", ""),
        "access_token": os.getenv("UPSTOX_ACCESS_TOKEN", ""),
    }
    if creds["access_token"]:
        return creds

    candidates = []
    custom_path = os.getenv("UPSTOX_CREDENTIALS_PATH")
    if custom_path:
        candidates.append(custom_path)
    candidates.extend([
        "trader/credentials.json",
        "credentials.json",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "trader",
            "credentials.json",
        ),
    ])
    for p in candidates:
        if p and os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    if not creds["access_token"]:
                        creds["access_token"] = (
                            data.get("upstox_access_token")
                            or data.get("access_token")
                            or ""
                        )
                    if not creds["api_key"]:
                        creds["api_key"] = (
                            data.get("upstox_api_key")
                            or data.get("api_key")
                            or ""
                        )
                    if creds["access_token"]:
                        break
            except Exception:
                pass
    return creds


class UpstoxV3Provider(MarketDataProvider):
    """Primary live market data provider via Upstox API V3 / V2 REST endpoints."""

    name: str = "upstox"
    capabilities: Set[ProviderCapability] = {ProviderCapability.LIVE}

    def __init__(
        self,
        api_key: Optional[str] = None,
        access_token: Optional[str] = None,
        base_url: str = "https://api.upstox.com/v2",
        instrument_master: Optional[InstrumentMaster] = None,
        timeout: float = 10.0,
    ):
        creds = _find_credentials()
        self.api_key = api_key or creds.get("api_key", "")
        self.access_token = access_token or creds.get("access_token", "")
        self.base_url = base_url.rstrip("/")
        self.instrument_master = instrument_master or InstrumentMaster()
        self.timeout = timeout

    def _resolve_instrument(self, symbol: str) -> InstrumentInfo:
        return self.instrument_master.resolve(symbol)

    def _fetch_json(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        req_headers = {
            "Accept": "application/json",
            "User-Agent": "DalalStreetTrader/1.0",
        }
        if self.access_token:
            req_headers["Authorization"] = f"Bearer {self.access_token}"
        if headers:
            req_headers.update(headers)

        req = urllib.request.Request(url, headers=req_headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status_code = resp.getcode()
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            status_code = e.code
            try:
                body = e.read().decode("utf-8")
                err_data = json.loads(body)
            except Exception:
                err_data = {}

            err_msg = str(err_data.get("errors") or e.reason)
            if status_code in (401, 403):
                raise ProviderAuthenticationError(
                    f"Upstox authentication failed (HTTP {status_code}): {err_msg}"
                ) from e
            elif status_code == 429:
                raise ProviderRateLimitError(
                    f"Upstox rate limit exceeded (HTTP 429): {err_msg}"
                ) from e
            elif status_code >= 500:
                raise ProviderConnectionError(
                    f"Upstox server error (HTTP {status_code}): {err_msg}"
                ) from e
            else:
                raise ProviderDataError(
                    f"Upstox API error (HTTP {status_code}): {err_msg}"
                ) from e
        except urllib.error.URLError as e:
            raise ProviderConnectionError(
                f"Failed to connect to Upstox API: {e.reason}"
            ) from e
        except Exception as e:
            raise ProviderConnectionError(
                f"Network error querying Upstox API: {e}"
            ) from e

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ProviderDataError(
                f"Malformed JSON response from Upstox API: {e}"
            ) from e

        if not isinstance(data, dict):
            raise ProviderDataError(
                f"Expected dict response from Upstox API, got {type(data).__name__}"
            )

        status = data.get("status")
        if status == "error":
            errors = data.get("errors", [])
            msg = "; ".join(
                e.get("message", str(e)) for e in errors
            ) if errors else "Unknown Upstox API error"
            err_code = (
                errors[0].get("errorCode")
                if errors and isinstance(errors[0], dict)
                else ""
            )
            if "UDAPI100057" in str(err_code) or "AUTH" in str(err_code).upper():
                raise ProviderAuthenticationError(
                    f"Upstox authentication error: {msg}"
                )
            raise ProviderDataError(f"Upstox API returned error: {msg}")

        return data

    def get_intraday_bars(
        self,
        symbol: str,
        interval: str = "5minute",
        start: Optional[datetime.datetime] = None,
        end: Optional[datetime.datetime] = None,
    ) -> List[Candle]:
        info = self._resolve_instrument(symbol)
        mapped_interval = _INTERVAL_MAP.get(interval.lower(), interval)

        encoded_key = urllib.parse.quote(info.instrument_key, safe="")

        now_ist = datetime.datetime.now(IST)
        today_date = now_ist.date()

        start_dt = (
            start.astimezone(IST)
            if (start and start.tzinfo)
            else (start.replace(tzinfo=IST) if start else None)
        )
        end_dt = (
            end.astimezone(IST)
            if (end and end.tzinfo)
            else (end.replace(tzinfo=IST) if end else None)
        )

        if (
            mapped_interval not in ("day", "week", "month")
            and start_dt is not None
            and start_dt.date() < today_date
            and (end_dt is None or end_dt.date() >= today_date)
        ):
            yesterday_date = today_date - datetime.timedelta(days=1)
            yesterday_end = datetime.datetime.combine(
                yesterday_date, datetime.time(23, 59, 59, tzinfo=IST)
            )
            past_candles = self.get_intraday_bars(
                symbol=symbol,
                interval=interval,
                start=start_dt,
                end=yesterday_end,
            )
            today_start = datetime.datetime.combine(
                today_date, datetime.time(9, 15, 0, tzinfo=IST)
            )
            try:
                today_candles = self.get_intraday_bars(
                    symbol=symbol,
                    interval=interval,
                    start=today_start,
                    end=end_dt,
                )
            except Exception as e:
                logger.warning(
                    "Could not fetch today's intraday bars for %s: %s", symbol, e
                )
                today_candles = []

            all_candles = list(past_candles) + [
                c for c in today_candles if c.timestamp.date() == today_date
            ]
            seen_ts: Dict[datetime.datetime, Candle] = {}
            for c in all_candles:
                seen_ts[c.timestamp] = c
            return sorted(seen_ts.values(), key=lambda x: x.timestamp)

        if mapped_interval in ("day", "week", "month"):
            end_d = end_dt or now_ist
            min_allowed_start = end_d - datetime.timedelta(days=3650)
            if start_dt is not None:
                start_d = max(start_dt, min_allowed_start)
            else:
                start_d = end_d - datetime.timedelta(days=365)
            to_date = end_d.strftime("%Y-%m-%d")
            from_date = start_d.strftime("%Y-%m-%d")
            url = (
                f"{self.base_url}/historical-candle/{encoded_key}/{mapped_interval}"
                f"/{to_date}/{from_date}"
            )
        elif (
            start_dt is not None
            and end_dt is not None
            and end_dt.date() < today_date
        ):
            to_date = end_dt.strftime("%Y-%m-%d")
            from_date = start_dt.strftime("%Y-%m-%d")
            url = (
                f"{self.base_url}/historical-candle/{encoded_key}/{mapped_interval}"
                f"/{to_date}/{from_date}"
            )
        else:
            url = f"{self.base_url}/historical-candle/intraday/{encoded_key}/{mapped_interval}"

        try:
            payload = self._fetch_json(url)
        except ProviderDataError as e:
            if (
                "Interval accepts one of" in str(e)
                or "Bad Request" in str(e)
            ) and mapped_interval.endswith("minute"):
                return self._fetch_and_aggregate_bars(
                    info=info,
                    target_interval=mapped_interval,
                    start=start_dt,
                    end=end_dt,
                )
            raise

        data = payload.get("data")
        if not isinstance(data, dict):
            raise ProviderDataError(
                f"Malformed Upstox candle payload: missing or invalid 'data' container: {payload}"
            )

        raw_candles = data.get("candles")
        if not isinstance(raw_candles, list):
            raise ProviderDataError(
                f"Malformed Upstox candle payload: missing 'candles' list in data: {data}"
            )

        candles: List[Candle] = []
        for item in raw_candles:
            if not isinstance(item, (list, tuple)) or len(item) < 6:
                raise ProviderDataError(
                    f"Invalid candle record format in Upstox response: {item}"
                )

            ts_raw, o, h, l, c, v = item[0], item[1], item[2], item[3], item[4], item[5]
            try:
                ts = parse_ist_timestamp(ts_raw)
            except Exception as e:
                try:
                    ts = datetime.datetime.fromisoformat(str(ts_raw))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=IST)
                    else:
                        ts = ts.astimezone(IST)
                except Exception as ex:
                    raise ProviderDataError(
                        f"Could not parse candle timestamp '{ts_raw}': {e} / {ex}"
                    ) from ex

            try:
                candle = Candle(
                    timestamp=ts,
                    open=Decimal(str(o)),
                    high=Decimal(str(h)),
                    low=Decimal(str(l)),
                    close=Decimal(str(c)),
                    volume=int(v)
                    if isinstance(v, (int, float, Decimal))
                    else int(float(str(v))),
                    is_complete=True,
                )
            except Exception as e:
                raise ProviderDataError(
                    f"Failed to construct Candle from values {item}: {e}"
                ) from e

            step_sec = _INTERVAL_SECONDS.get(mapped_interval, 300)
            valid, err_msg = validate_candle(
                candle,
                interval_seconds=step_sec,
                validate_alignment=(mapped_interval != "day"),
            )
            if not valid:
                raise ProviderDataError(
                    f"Candle invariant violation from Upstox: {err_msg} ({item})"
                )

            if start is not None and candle.timestamp < start:
                continue
            effective_end = (
                end.replace(hour=23, minute=59, second=59)
                if (end and end.time() == datetime.time(0, 0))
                else end
            )
            if effective_end is not None and candle.timestamp > effective_end:
                continue

            candles.append(candle)

        candles.sort(key=lambda x: x.timestamp)
        return candles

    def _fetch_and_aggregate_bars(
        self,
        info: InstrumentInfo,
        target_interval: str,
        start: Optional[datetime.datetime] = None,
        end: Optional[datetime.datetime] = None,
    ) -> List[Candle]:
        if target_interval.endswith("minute"):
            try:
                target_minutes = int(target_interval[:-6])
            except ValueError:
                target_minutes = 5
        else:
            target_minutes = 5
        base_bars: List[Candle] = []

        if start is not None and end is not None and (end - start).days > 25:
            cur_start = start
            while cur_start < end:
                cur_end = min(cur_start + datetime.timedelta(days=25), end)
                chunk_bars = self.get_intraday_bars(
                    symbol=info.symbol,
                    interval="1minute",
                    start=cur_start,
                    end=cur_end,
                )
                base_bars.extend(chunk_bars)
                cur_start = cur_end + datetime.timedelta(days=1)
        else:
            base_bars = self.get_intraday_bars(
                symbol=info.symbol,
                interval="1minute",
                start=start,
                end=end,
            )
        if not base_bars:
            return []

        buckets: Dict[datetime.datetime, List[Candle]] = {}
        for c in base_bars:
            sess_start = c.timestamp.replace(
                hour=9, minute=15, second=0, microsecond=0
            )
            elapsed_minutes = (
                c.timestamp - sess_start
            ).total_seconds() // 60
            if elapsed_minutes < 0:
                minute_offset = c.timestamp.minute % target_minutes
                bucket_ts = c.timestamp.replace(
                    minute=c.timestamp.minute - minute_offset,
                    second=0,
                    microsecond=0,
                )
            else:
                bucket_offset = (
                    int(elapsed_minutes // target_minutes) * target_minutes
                )
                bucket_ts = sess_start + datetime.timedelta(minutes=bucket_offset)

            if bucket_ts not in buckets:
                buckets[bucket_ts] = []
            buckets[bucket_ts].append(c)

        agg_candles: List[Candle] = []
        for b_ts in sorted(buckets.keys()):
            chunk = buckets[b_ts]
            agg = Candle(
                timestamp=b_ts,
                open=chunk[0].open,
                high=max(c.high for c in chunk),
                low=min(c.low for c in chunk),
                close=chunk[-1].close,
                volume=sum(c.volume for c in chunk),
                is_complete=True,
            )
            valid, err_msg = validate_candle(
                agg,
                interval_seconds=target_minutes * 60,
                validate_alignment=True,
            )
            if not valid:
                raise ProviderDataError(
                    f"Aggregated candle invariant violation: {err_msg}"
                )
            agg_candles.append(agg)

        return agg_candles

    def get_quote(self, symbol: str) -> Quote:
        info = self._resolve_instrument(symbol)
        encoded_key = urllib.parse.quote(info.instrument_key, safe="")

        url = f"{self.base_url}/market-quote/quotes?instrument_key={encoded_key}"
        payload = self._fetch_json(url)

        data = payload.get("data")
        if not isinstance(data, dict):
            raise ProviderDataError(
                f"Malformed Upstox quote payload: 'data' is not dict: {payload}"
            )

        quote_data = None
        for k, v in data.items():
            if k == info.instrument_key or k.replace(":", "|") == info.instrument_key:
                quote_data = v
                break
            if info.symbol in k:
                quote_data = v
                break

        if quote_data is None and data:
            quote_data = next(iter(data.values()))

        if not isinstance(quote_data, dict):
            raise ProviderDataError(
                f"No quote data found for symbol '{symbol}' in Upstox response"
            )

        try:
            last_price = Decimal(
                str(
                    quote_data.get("last_price", quote_data.get("ltp", "0"))
                )
            )
        except Exception as e:
            raise ProviderDataError(
                f"Invalid last_price in Upstox quote: {e}"
            ) from e

        ohlc = quote_data.get("ohlc", {})
        open_val = (
            Decimal(str(ohlc["open"]))
            if ohlc and "open" in ohlc and ohlc["open"] is not None
            else None
        )
        high_val = (
            Decimal(str(ohlc["high"]))
            if ohlc and "high" in ohlc and ohlc["high"] is not None
            else None
        )
        low_val = (
            Decimal(str(ohlc["low"]))
            if ohlc and "low" in ohlc and ohlc["low"] is not None
            else None
        )
        close_val = (
            Decimal(str(ohlc["close"]))
            if ohlc and "close" in ohlc and ohlc["close"] is not None
            else None
        )

        depth = quote_data.get("depth", {})
        bid_val = None
        ask_val = None
        if isinstance(depth, dict):
            buy_depth = depth.get("buy", [])
            if (
                buy_depth
                and isinstance(buy_depth, list)
                and isinstance(buy_depth[0], dict)
                and "price" in buy_depth[0]
            ):
                bid_val = Decimal(str(buy_depth[0]["price"]))
            sell_depth = depth.get("sell", [])
            if (
                sell_depth
                and isinstance(sell_depth, list)
                and isinstance(sell_depth[0], dict)
                and "price" in sell_depth[0]
            ):
                ask_val = Decimal(str(sell_depth[0]["price"]))

        raw_ts = quote_data.get("timestamp")
        if raw_ts:
            try:
                quote_ts = parse_ist_timestamp(raw_ts)
            except Exception:
                try:
                    quote_ts = datetime.datetime.fromisoformat(str(raw_ts))
                    if quote_ts.tzinfo is None:
                        quote_ts = quote_ts.replace(tzinfo=IST)
                    else:
                        quote_ts = quote_ts.astimezone(IST)
                except Exception:
                    quote_ts = datetime.datetime.now(IST)
        else:
            quote_ts = datetime.datetime.now(IST)

        vol = quote_data.get("volume", 0)
        try:
            vol_int = int(vol)
        except Exception:
            vol_int = int(float(str(vol)))

        return Quote(
            symbol=info.symbol,
            last_price=last_price,
            timestamp=quote_ts,
            volume=vol_int,
            open=open_val,
            high=high_val,
            low=low_val,
            close=close_val,
            bid=bid_val,
            ask=ask_val,
            provider="upstox",
        )

    def get_quotes(self, symbols: List[str]) -> Dict[str, Quote]:
        if not symbols:
            return {}

        results: Dict[str, Quote] = {}
        symbol_info_map: Dict[str, InstrumentInfo] = {}
        key_to_symbol: Dict[str, str] = {}
        for sym in symbols:
            try:
                info = self._resolve_instrument(sym)
                symbol_info_map[sym] = info
                key_to_symbol[info.instrument_key] = sym
                key_to_symbol[info.instrument_key.replace("|", ":")] = sym
                if info.isin:
                    key_to_symbol[info.isin] = sym
                key_to_symbol[info.symbol] = sym
            except Exception:
                continue

        infos = list(symbol_info_map.values())
        chunk_size = 50
        for i in range(0, len(infos), chunk_size):
            chunk = infos[i : i + chunk_size]
            encoded_keys = [
                urllib.parse.quote(inf.instrument_key, safe="") for inf in chunk
            ]
            url = (
                f"{self.base_url}/market-quote/quotes?"
                f"instrument_key={','.join(encoded_keys)}"
            )
            try:
                payload = self._fetch_json(url)
            except Exception as e:
                logger.warning("Batch quotes fetch failed for chunk: %s", e)
                continue

            data = payload.get("data")
            if not isinstance(data, dict):
                continue

            for raw_k, quote_data in data.items():
                if not isinstance(quote_data, dict):
                    continue
                matched_sym = None
                normalized_k = raw_k.replace(":", "|")
                if raw_k in key_to_symbol:
                    matched_sym = key_to_symbol[raw_k]
                elif normalized_k in key_to_symbol:
                    matched_sym = key_to_symbol[normalized_k]
                else:
                    for k_pat, sym in key_to_symbol.items():
                        if k_pat in raw_k or k_pat in normalized_k:
                            matched_sym = sym
                            break

                if not matched_sym:
                    continue

                try:
                    last_price = Decimal(
                        str(
                            quote_data.get(
                                "last_price", quote_data.get("ltp", "0")
                            )
                        )
                    )
                    ohlc = quote_data.get("ohlc", {})
                    open_val = (
                        Decimal(str(ohlc["open"]))
                        if ohlc
                        and "open" in ohlc
                        and ohlc["open"] is not None
                        else None
                    )
                    high_val = (
                        Decimal(str(ohlc["high"]))
                        if ohlc
                        and "high" in ohlc
                        and ohlc["high"] is not None
                        else None
                    )
                    low_val = (
                        Decimal(str(ohlc["low"]))
                        if ohlc
                        and "low" in ohlc
                        and ohlc["low"] is not None
                        else None
                    )
                    close_val = (
                        Decimal(str(ohlc["close"]))
                        if ohlc
                        and "close" in ohlc
                        and ohlc["close"] is not None
                        else None
                    )

                    depth = quote_data.get("depth", {})
                    bid_val = None
                    ask_val = None
                    if isinstance(depth, dict):
                        buy_depth = depth.get("buy", [])
                        if (
                            buy_depth
                            and isinstance(buy_depth, list)
                            and isinstance(buy_depth[0], dict)
                            and "price" in buy_depth[0]
                        ):
                            bid_val = Decimal(str(buy_depth[0]["price"]))
                        sell_depth = depth.get("sell", [])
                        if (
                            sell_depth
                            and isinstance(sell_depth, list)
                            and isinstance(sell_depth[0], dict)
                            and "price" in sell_depth[0]
                        ):
                            ask_val = Decimal(str(sell_depth[0]["price"]))

                    raw_ts = quote_data.get("timestamp")
                    quote_ts = datetime.datetime.now(IST)
                    if raw_ts:
                        try:
                            quote_ts = parse_ist_timestamp(raw_ts)
                        except Exception:
                            try:
                                quote_ts = datetime.datetime.fromisoformat(
                                    str(raw_ts)
                                )
                                if quote_ts.tzinfo is None:
                                    quote_ts = quote_ts.replace(tzinfo=IST)
                                else:
                                    quote_ts = quote_ts.astimezone(IST)
                            except Exception:
                                pass

                    vol = quote_data.get("volume", 0)
                    try:
                        vol_int = int(vol)
                    except Exception:
                        vol_int = int(float(str(vol)))

                    results[matched_sym] = Quote(
                        symbol=matched_sym,
                        last_price=last_price,
                        timestamp=quote_ts,
                        volume=vol_int,
                        open=open_val,
                        high=high_val,
                        low=low_val,
                        close=close_val,
                        bid=bid_val,
                        ask=ask_val,
                        provider="upstox",
                    )
                except Exception as parse_err:
                    logger.debug(
                        "Failed to parse quote for %s in batch: %s",
                        matched_sym,
                        parse_err,
                    )

        return results
