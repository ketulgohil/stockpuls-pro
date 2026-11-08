"""trader_core.service - Unified Market Data Service with Strict Safety Policies.

Enforces:
- Upstox API V3 is the sole authorized market data provider across live,
  research, and historical modes.
- Yahoo Finance is decommissioned from the system.
- Fail-closed error propagation.
"""

from __future__ import annotations

import datetime
import logging
from typing import Dict, List, Optional

from .calendar import IST
from .candle import Candle
from .providers.base import (
    InstrumentInfo,
    InstrumentMaster,
    MarketDataProvider,
    ProviderCapability,
    ProviderError,
    ProviderPolicyError,
    Quote,
)
from .providers.upstox import UpstoxV3Provider

logger = logging.getLogger(__name__)


class MarketDataService:
    """Unified market data service using Upstox API V3.

    Enforces strict execution mode constraints and safety invariants:
    - Upstox API V3 is the sole authorized market data provider.
    - Any attempt to use decommissioned Yahoo Finance will raise
      ProviderPolicyError.
    """

    def __init__(
        self,
        primary_provider: Optional[MarketDataProvider] = None,
        secondary_provider: Optional[MarketDataProvider] = None,
        mode: str = "live",
        instrument_master: Optional[InstrumentMaster] = None,
    ):
        self.mode = mode.lower()
        self.instrument_master = instrument_master or InstrumentMaster()
        self.primary_provider = primary_provider or UpstoxV3Provider(
            instrument_master=self.instrument_master
        )
        self.secondary_provider = secondary_provider

    def get_provider(self, name: Optional[str] = None) -> MarketDataProvider:
        """Retrieve provider by name while enforcing mode safety policies."""
        if not name or name.lower() == "upstox":
            return self.primary_provider
        elif name.lower() == "yahoo":
            raise ProviderPolicyError(
                "INV-07 / THR-02: Yahoo Finance has been decommissioned. "
                "Upstox API V3 is the sole authorized market data provider."
            )
        else:
            raise ValueError(
                f"Unknown market data provider '{name}'. Supported provider: 'upstox'"
            )

    def resolve_symbol(self, symbol: str, strict: bool = False) -> InstrumentInfo:
        """Resolve symbol or key to canonical InstrumentInfo."""
        return self.instrument_master.resolve(symbol, strict=strict)

    def get_intraday_bars(
        self,
        symbol: str,
        interval: str = "5minute",
        start: Optional[datetime.datetime] = None,
        end: Optional[datetime.datetime] = None,
        allow_fallback: bool = False,
        provider: Optional[str] = None,
    ) -> List[Candle]:
        """Fetch completed intraday bars."""
        if self.mode == "live" and allow_fallback:
            raise ProviderPolicyError(
                "INV-07 / THR-02: Fallback to secondary provider (Yahoo) is "
                "strictly prohibited in live trading mode."
            )

        if provider is not None and provider.lower() == "yahoo":
            raise ProviderPolicyError(
                "INV-07 / THR-02: Yahoo Finance has been decommissioned. "
                "Upstox API V3 is the sole authorized market data provider."
            )

        if provider is not None:
            active_provider = self.get_provider(provider)
            return active_provider.get_intraday_bars(
                symbol=symbol, interval=interval, start=start, end=end
            )

        try:
            return self.primary_provider.get_intraday_bars(
                symbol=symbol, interval=interval, start=start, end=end
            )
        except ProviderError as e:
            if allow_fallback and self.secondary_provider is not None:
                logger.warning(
                    "Primary provider '%s' failed for %s (%s); trying "
                    "secondary provider '%s'",
                    self.primary_provider.name,
                    symbol,
                    e,
                    self.secondary_provider.name,
                )
                return self.secondary_provider.get_intraday_bars(
                    symbol=symbol, interval=interval, start=start, end=end
                )
            raise

    def get_bars(
        self,
        symbol: str,
        interval: str = "5minute",
        start: Optional[datetime.datetime] = None,
        end: Optional[datetime.datetime] = None,
        allow_fallback: bool = False,
        provider: Optional[str] = None,
    ) -> List[Candle]:
        """Alias for get_intraday_bars."""
        return self.get_intraday_bars(
            symbol=symbol,
            interval=interval,
            start=start,
            end=end,
            allow_fallback=allow_fallback,
            provider=provider,
        )

    def get_quote(
        self,
        symbol: str,
        allow_fallback: bool = False,
        provider: Optional[str] = None,
    ) -> Quote:
        """Fetch market quote."""
        if self.mode == "live" and allow_fallback:
            raise ProviderPolicyError(
                "INV-07 / THR-02: Fallback to secondary provider (Yahoo) is "
                "strictly prohibited in live trading mode."
            )

        if provider is not None and provider.lower() == "yahoo":
            raise ProviderPolicyError(
                "INV-07 / THR-02: Yahoo Finance has been decommissioned. "
                "Upstox API V3 is the sole authorized market data provider."
            )

        if provider is not None:
            active_provider = self.get_provider(provider)
            return active_provider.get_quote(symbol)

        try:
            return self.primary_provider.get_quote(symbol)
        except ProviderError as e:
            if allow_fallback and self.secondary_provider is not None:
                logger.warning(
                    "Primary provider '%s' quote failed for %s (%s); trying "
                    "secondary provider '%s'",
                    self.primary_provider.name,
                    symbol,
                    e,
                    self.secondary_provider.name,
                )
                return self.secondary_provider.get_quote(symbol)
            raise

    def get_quotes(
        self,
        symbols: List[str],
        allow_fallback: bool = False,
        provider: Optional[str] = None,
    ) -> Dict[str, Quote]:
        """Fetch market quotes for multiple symbols."""
        if self.mode == "live" and allow_fallback:
            raise ProviderPolicyError(
                "INV-07 / THR-02: Fallback to secondary provider (Yahoo) is "
                "strictly prohibited in live trading mode."
            )

        if provider is not None and provider.lower() == "yahoo":
            raise ProviderPolicyError(
                "INV-07 / THR-02: Yahoo Finance has been decommissioned. "
                "Upstox API V3 is the sole authorized market data provider."
            )

        if provider is not None:
            active_provider = self.get_provider(provider)
            return active_provider.get_quotes(symbols)

        try:
            return self.primary_provider.get_quotes(symbols)
        except ProviderError as e:
            if allow_fallback and self.secondary_provider is not None:
                return self.secondary_provider.get_quotes(symbols)
            raise
