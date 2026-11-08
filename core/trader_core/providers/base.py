"""trader_core.providers.base - Market Data Provider Abstraction & Base Interfaces.

Provides:
- MarketDataProvider: Abstract base class for market data providers.
- ProviderCapability: Feature/mode capability flags (LIVE vs HISTORICAL_RESEARCH_ONLY).
- Quote: Standardized market quote representation with provider provenance.
- InstrumentInfo & InstrumentMaster: Versioned exchange/segment/key mapping.
- Provider exception hierarchy for fail-closed error handling.
"""

from __future__ import annotations

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import datetime
from decimal import Decimal
from enum import Enum
import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ..calendar import IST, parse_ist_timestamp
from ..candle import Candle


class ProviderCapability(Enum):
    """Capabilities supported by a market data provider."""

    LIVE = "LIVE"
    HISTORICAL_RESEARCH_ONLY = "HISTORICAL_RESEARCH_ONLY"


class ProviderError(Exception):
    """Base exception for all market data provider failures."""

    pass


class ProviderAuthenticationError(ProviderError):
    """Raised when authentication credentials (API key, OAuth token) fail or expire."""

    pass


class ProviderRateLimitError(ProviderError):
    """Raised when upstream HTTP 429 or rate limits are exceeded."""

    pass


class ProviderDataError(ProviderError):
    """Raised when received payload is malformed, corrupt, or contradicts safety invariants."""

    pass


class ProviderConnectionError(ProviderError):
    """Raised on network timeout, socket drop, or upstream 5xx HTTP error."""

    pass


class ProviderPolicyError(ProviderError):
    """Raised on invariant violations, such as attempting live trading with historical data."""

    pass


class InstrumentNotFoundError(ProviderError):
    """Raised when a symbol or instrument key cannot be resolved."""

    pass


@dataclass
class Quote:
    """Standardized representation of a single market quote snapshot."""

    symbol: str
    last_price: Decimal
    timestamp: datetime.datetime
    volume: int = 0
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Optional[Decimal] = None
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    provider: str = ""

    @property
    def price(self) -> Decimal:
        """Alias for last_price."""
        return self.last_price

    @property
    def prev_close(self) -> Optional[Decimal]:
        """Alias for close."""
        return self.close

    def to_dict(self) -> Dict[str, Any]:
        """Serialize quote to dictionary."""
        return {
            "symbol": self.symbol,
            "last_price": str(self.last_price),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "volume": self.volume,
            "open": str(self.open) if self.open is not None else None,
            "high": str(self.high) if self.high is not None else None,
            "low": str(self.low) if self.low is not None else None,
            "close": str(self.close) if self.close is not None else None,
            "bid": str(self.bid) if self.bid is not None else None,
            "ask": str(self.ask) if self.ask is not None else None,
            "provider": self.provider,
        }


@dataclass
class InstrumentInfo:
    """Versioned canonical mapping for an exchange-traded equity."""

    symbol: str
    exchange: str = "NSE"
    segment: str = "EQ"
    instrument_key: str = ""
    isin: str = ""
    yahoo_ticker: str = ""
    lot_size: int = 1
    tick_size: Decimal = Decimal("0.05")

    def __post_init__(self):
        if not self.instrument_key and self.isin:
            self.instrument_key = f"{self.exchange}_{self.segment}|{self.isin}"
        elif not self.instrument_key:
            self.instrument_key = f"{self.exchange}_{self.segment}|{self.symbol}"

        if not self.yahoo_ticker:
            suffix = ".NS" if self.exchange.upper() == "NSE" else ".BO"
            self.yahoo_ticker = f"{self.symbol}{suffix}"


# Pre-loaded default Nifty 50 canonical instrument master records
_DEFAULT_NIFTY50_INSTRUMENTS: List[Dict[str, str]] = [
    {"symbol": "NIFTY 50", "isin": "", "instrument_key": "NSE_INDEX|Nifty 50", "exchange": "NSE", "segment": "INDEX", "yahoo_ticker": "^NSEI"},
    {"symbol": "BANK NIFTY", "isin": "", "instrument_key": "NSE_INDEX|Nifty Bank", "exchange": "NSE", "segment": "INDEX", "yahoo_ticker": "^NSEBANK"},
    {"symbol": "RELIANCE", "isin": "INE002A01018", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "TCS", "isin": "INE467B01029", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "HDFCBANK", "isin": "INE040A01034", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "ICICIBANK", "isin": "INE090A01021", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "INFY", "isin": "INE009A01021", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "BHARTIARTL", "isin": "INE397D01024", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "ITC", "isin": "INE154A01025", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "SBIN", "isin": "INE062A01020", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "LICI", "isin": "INE0J1Y01017", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "HINDUNILVR", "isin": "INE030A01027", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "LT", "isin": "INE018A01030", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "BAJFINANCE", "isin": "INE296A01024", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "HCLTECH", "isin": "INE860A01027", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "MARUTI", "isin": "INE585B01010", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "SUNPHARMA", "isin": "INE044A01036", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "ADANIENT", "isin": "INE423A01024", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "KOTAKBANK", "isin": "INE237A01028", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "TATAMOTORS", "isin": "INE155A01022", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "AXISBANK", "isin": "INE238A01034", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "NTPC", "isin": "INE733E01010", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "TITAN", "isin": "INE280A01028", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "ONGC", "isin": "INE213A01029", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "POWERGRID", "isin": "INE752E01010", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "TATASTEEL", "isin": "INE081A01020", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "COALINDIA", "isin": "INE522F01014", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "ASIANPAINT", "isin": "INE021A01026", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "BAJAJFINSV", "isin": "INE918I01026", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "M&M", "isin": "INE101A01026", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "ULTRACEMCO", "isin": "INE481G01011", "exchange": "NSE", "segment": "EQ"},
    {"symbol": "WIPRO", "isin": "INE075A01022", "exchange": "NSE", "segment": "EQ"},
]


class MarketDataProvider(ABC):
    """Abstract Base Class for market data providers."""

    name: str = "base"
    capabilities: Set[ProviderCapability] = set()

    @abstractmethod
    def get_intraday_bars(
        self,
        symbol: str,
        interval: str = "5minute",
        start: Optional[datetime.datetime] = None,
        end: Optional[datetime.datetime] = None,
    ) -> List[Candle]:
        pass

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote:
        pass

    def get_quotes(self, symbols: List[str]) -> Dict[str, Quote]:
        results: Dict[str, Quote] = {}
        for s in symbols:
            try:
                results[s] = self.get_quote(s)
            except Exception:
                pass
        return results

    def get_bars(
        self,
        symbol: str,
        interval: str = "5minute",
        start: Optional[datetime.datetime] = None,
        end: Optional[datetime.datetime] = None,
    ) -> List[Candle]:
        """Alias for get_intraday_bars."""
        return self.get_intraday_bars(symbol=symbol, interval=interval, start=start, end=end)


class InstrumentMaster:
    """Authoritative registry and resolver for exchange-traded instruments."""

    def __init__(self, snapshot_path: Optional[str] = None):
        self._by_symbol: Dict[str, InstrumentInfo] = {}
        self._by_key: Dict[str, InstrumentInfo] = {}
        self._by_isin: Dict[str, InstrumentInfo] = {}
        self._by_yahoo: Dict[str, InstrumentInfo] = {}

        for item in _DEFAULT_NIFTY50_INSTRUMENTS:
            info = InstrumentInfo(
                symbol=item["symbol"],
                exchange=item.get("exchange", "NSE"),
                segment=item.get("segment", "EQ"),
                isin=item["isin"],
                instrument_key=item.get(
                    "instrument_key",
                    f"{item.get('exchange', 'NSE')}_{item.get('segment', 'EQ')}|{item['isin']}",
                ),
                yahoo_ticker=f"{item['symbol']}.NS",
            )
            self.register(info)

        if snapshot_path and os.path.isfile(snapshot_path):
            self.load_snapshot(snapshot_path)

    def register(self, info: InstrumentInfo) -> None:
        self._by_symbol[info.symbol.upper()] = info
        if info.instrument_key:
            self._by_key[info.instrument_key] = info
        if info.isin:
            self._by_isin[info.isin.upper()] = info
        if info.yahoo_ticker:
            self._by_yahoo[info.yahoo_ticker.upper()] = info

    def resolve_live(self, identifier: str) -> InstrumentInfo:
        return self.resolve(identifier, strict=True)

    def resolve_research(self, identifier: str) -> InstrumentInfo:
        return self.resolve(identifier, strict=False)

    def resolve(self, identifier: str, strict: bool = False) -> InstrumentInfo:
        raw = identifier.strip()
        upper = raw.upper()

        if upper in self._by_symbol:
            return self._by_symbol[upper]
        COMMON_ALIASES = {
            "IDEAFO": "IDEAFORGE", "DREAMF": "DREAMFOLKS", "UTKARS": "UTKARSHBNK",
            "ANANTRJ": "ANANTRAJ", "EIHAHOTEL": "EIHAHOTELS", "HDFC": "HDFCBANK",
            "NSE": "NIFTY 50", "NIFTY": "NIFTY 50", "NIFTY50": "NIFTY 50",
            "NIFTY_50": "NIFTY 50", "^NSEI": "NIFTY 50",
            "BANKNIFTY": "BANK NIFTY", "BANK_NIFTY": "BANK NIFTY", "^NSEBANK": "BANK NIFTY",
        }
        if upper in COMMON_ALIASES and COMMON_ALIASES[upper] in self._by_symbol:
            return self._by_symbol[COMMON_ALIASES[upper]]
        if upper in self._by_key:
            return self._by_key[upper]
        if upper in self._by_isin:
            return self._by_isin[upper]
        if upper in self._by_yahoo:
            return self._by_yahoo[upper]

        clean_symbol = upper
        if clean_symbol.endswith(".NS") or clean_symbol.endswith(".BO"):
            clean_symbol = clean_symbol[:-3]

        if clean_symbol in self._by_symbol:
            return self._by_symbol[clean_symbol]

        if "|" in clean_symbol:
            tail = clean_symbol.split("|")[-1]
            if tail in self._by_symbol:
                return self._by_symbol[tail]
            if tail in self._by_isin:
                return self._by_isin[tail]

        if strict:
            raise InstrumentNotFoundError(
                f"Instrument identifier '{identifier}' could not be resolved in Authoritative InstrumentMaster."
            )

        is_bse = upper.endswith(".BO")
        exchange = "BSE" if is_bse else "NSE"
        segment = "EQ"
        key = f"{exchange}_{segment}|{clean_symbol}"
        yahoo_ticker = f"{clean_symbol}.BO" if is_bse else f"{clean_symbol}.NS"

        info = InstrumentInfo(
            symbol=clean_symbol,
            exchange=exchange,
            segment=segment,
            instrument_key=key,
            isin="",
            yahoo_ticker=yahoo_ticker,
        )
        return info

    def validate_watchlist(self, symbols: List[str]) -> Tuple[List[InstrumentInfo], List[str]]:
        valid: List[InstrumentInfo] = []
        unmapped: List[str] = []
        for s in symbols:
            clean = s.strip().upper()
            if not clean:
                continue
            try:
                info = self.resolve_live(clean)
                valid.append(info)
            except InstrumentNotFoundError:
                unmapped.append(clean)
        return valid, unmapped

    def load_snapshot(self, path: str) -> int:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        count = 0
        for item in data:
            sym = item.get("symbol")
            if not sym:
                continue
            isin_val = item.get("isin") or sym
            default_key = f"{item.get('exchange', 'NSE')}_{item.get('segment', 'EQ')}|{isin_val}"
            info = InstrumentInfo(
                symbol=sym.upper(),
                exchange=item.get("exchange", "NSE"),
                segment=item.get("segment", "EQ"),
                isin=item.get("isin", ""),
                instrument_key=item.get("instrument_key") or default_key,
                yahoo_ticker=item.get("yahoo_ticker", f"{sym}.NS"),
            )
            self.register(info)
            count += 1
        return count

    def save_snapshot(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        items = [
            {
                "symbol": info.symbol,
                "exchange": info.exchange,
                "segment": info.segment,
                "isin": info.isin,
                "instrument_key": info.instrument_key,
                "yahoo_ticker": info.yahoo_ticker,
            }
            for info in self._by_key.values()
        ]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(items, fh, indent=2)


_global_instrument_master: Optional[InstrumentMaster] = None


def get_instrument_master() -> InstrumentMaster:
    global _global_instrument_master
    if _global_instrument_master is None:
        _global_instrument_master = InstrumentMaster()
    return _global_instrument_master


