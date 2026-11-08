"""Data Aggregator and Module Bridge for Dalal Street Dashboard.

Bridges scanner setups, entry triggers, market data service, and analyst
quarterly financial statements into unified data objects for the REST API.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional

from ..calendar import IST
from .confluence import evaluate_confluence

logger = logging.getLogger(__name__)

# Default Nifty 50 core constituent watchlist
DEFAULT_SYMBOLS = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "TATAMOTORS",
    "BHARTIARTL",
    "SBIN",
    "ITC",
    "HINDUNILVR",
    "LT",
    "AXISBANK",
]

# Baseline fallback financials for offline/research mode (INR Crores)
FALLBACK_FINANCIALS = {
    "RELIANCE": {
        "ttm_pat_growth_yoy": 14.2,
        "operating_margin": 17.8,
        "margin_expanding": True,
        "positive_growth_quarters": 7,
        "ttm_revenue_growth_yoy": 11.8,
        "revenue_cr": 984200.0,
        "pat_cr": 74520.0,
        "eps": 109.80,
        "pe": 24.5,
        "sector": "Energy & Conglomerate",
    },
    "TCS": {
        "ttm_pat_growth_yoy": 18.5,
        "operating_margin": 24.5,
        "margin_expanding": True,
        "positive_growth_quarters": 8,
        "ttm_revenue_growth_yoy": 14.0,
        "revenue_cr": 240890.0,
        "pat_cr": 46500.0,
        "eps": 128.20,
        "pe": 32.1,
        "sector": "IT Services",
    },
    "INFY": {
        "ttm_pat_growth_yoy": -2.4,
        "operating_margin": 14.2,
        "margin_expanding": False,
        "positive_growth_quarters": 3,
        "ttm_revenue_growth_yoy": 2.1,
        "revenue_cr": 153670.0,
        "pat_cr": 26250.0,
        "eps": 63.40,
        "pe": 27.5,
        "sector": "IT Services",
    },
    "HDFCBANK": {
        "ttm_pat_growth_yoy": 16.8,
        "operating_margin": 22.4,
        "margin_expanding": True,
        "positive_growth_quarters": 7,
        "ttm_revenue_growth_yoy": 15.2,
        "revenue_cr": 215000.0,
        "pat_cr": 64000.0,
        "eps": 84.50,
        "pe": 19.8,
        "sector": "Banking & Financials",
    },
}

# Baseline fallback technicals for offline/research mode
FALLBACK_TECHNICALS = {
    "RELIANCE": {
        "symbol": "RELIANCE",
        "price": 1342.50,
        "change": 24.80,
        "change_pct": 1.88,
        "orb_high": 1338.00,
        "orb_low": 1328.00,
        "orb_breakout": True,
        "volume_ratio": 1.78,
        "above_vwap": True,
        "vwap": 1335.20,
        "reclaim_ma20": True,
    },
    "TCS": {
        "symbol": "TCS",
        "price": 4120.00,
        "change": 38.50,
        "change_pct": 0.94,
        "orb_high": 4150.00,
        "orb_low": 4090.00,
        "orb_breakout": False,
        "oversold": True,
        "reclaim_ma20": True,
        "volume_ratio": 1.15,
        "above_vwap": True,
        "vwap": 4110.00,
    },
    "INFY": {
        "symbol": "INFY",
        "price": 1745.20,
        "change": -28.40,
        "change_pct": -1.60,
        "orb_high": 1780.00,
        "orb_low": 1754.00,
        "orb_breakout": False,
        "below_orb_low": True,
        "volume_ratio": 1.45,
        "above_vwap": False,
        "vwap": 1762.00,
    },
    "HDFCBANK": {
        "symbol": "HDFCBANK",
        "price": 1720.00,
        "change": 12.00,
        "change_pct": 0.70,
        "orb_high": 1718.00,
        "orb_low": 1705.00,
        "orb_breakout": True,
        "volume_ratio": 1.35,
        "above_vwap": True,
        "vwap": 1714.00,
    },
}


class DashboardAggregator:
    """Aggregates market data, scanner setups, and analyst facts."""

    def __init__(
        self,
        offline: bool = False,
        demo: bool = False,
        watchlist_file: str = "trader/watchlist.txt",
        metrics_file: str = "trader/metrics.json",
        scan_file: str = "trader/scan.json",
    ):
        self.offline = offline
        self.demo = demo
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../..")
        )
        self._project_root = project_root
        self.watchlist_file = (
            os.path.join(project_root, watchlist_file)
            if watchlist_file == "trader/watchlist.txt"
            else watchlist_file
        )
        self.metrics_file = (
            os.path.join(project_root, metrics_file)
            if metrics_file == "trader/metrics.json"
            else metrics_file
        )
        self.scan_file = (
            os.path.join(project_root, scan_file)
            if scan_file == "trader/scan.json"
            else scan_file
        )
        self._market_quotes: Dict[str, Dict[str, Any]] = {}

    def update_market_tick(
        self,
        symbol: str,
        price: Any,
        previous_close: Any = None,
        timestamp: Any = None,
        volume: Any = None,
    ) -> None:
        """Record a validated live quote for macro cards and breadth."""
        try:
            last = float(price)
        except (TypeError, ValueError):
            return
        if last <= 0:
            return
        if isinstance(timestamp, datetime.datetime):
            timestamp = timestamp.isoformat()
        quote: Dict[str, Any] = {"price": last, "as_of": timestamp}
        if volume is not None:
            try:
                quote["volume"] = max(0, int(volume))
            except (TypeError, ValueError):
                pass
        try:
            if previous_close is not None and float(previous_close) > 0:
                close = float(previous_close)
                quote["previous_close"] = close
                quote["change"] = round(last - close, 2)
                quote["change_pct"] = round((last - close) / close * 100, 2)
        except (TypeError, ValueError):
            pass
        self._market_quotes[symbol.strip().upper()] = quote

    def get_watchlist_symbols(self) -> List[str]:
        """Loads symbols from watchlist.txt or returns defaults."""
        symbols = []
        if os.path.exists(self.watchlist_file):
            try:
                with open(self.watchlist_file, "r", encoding="utf-8") as f:
                    for line in f:
                        s = line.strip().upper()
                        if s and not s.startswith("#") and s not in symbols:
                            s = s.replace(".NS", "").replace(".BO", "")
                            symbols.append(s)
            except Exception:
                pass

        if not symbols:
            symbols = list(DEFAULT_SYMBOLS)
        else:
            for sym in DEFAULT_SYMBOLS[:4]:
                if sym not in symbols:
                    symbols.append(sym)

        return symbols

    def get_macro_overview(self) -> Dict[str, Any]:
        """Calculates Dalal Street macro indices and session status."""
        current_dt = datetime.datetime.now(IST)
        current_time_str = current_dt.strftime("%H:%M:%S")

        weekday = current_dt.weekday()
        hour = current_dt.hour
        minute = current_dt.minute
        time_minutes = hour * 60 + minute

        if weekday >= 5:
            session = "WEEKEND CLOSED"
        elif time_minutes < 9 * 60 + 15:
            session = "PRE-MARKET"
        elif time_minutes <= 15 * 60 + 30:
            if time_minutes <= 9 * 60 + 30:
                session = "ORB BUILDING (09:15-09:30)"
            elif time_minutes <= 9 * 60 + 35:
                session = "ORB EVALUATION (09:30-09:35)"
            else:
                session = "REGULAR SESSION"
        else:
            session = "POST-MARKET CLOSED"

        if self.demo:
            return {
                "nifty_50": {
                    "symbol": "NIFTY 50",
                    "price": 24380.20,
                    "change": 145.40,
                    "change_pct": 0.60,
                    "status": "DEMO",
                },
                "bank_nifty": {
                    "symbol": "BANK NIFTY",
                    "price": 51840.10,
                    "change": 280.50,
                    "change_pct": 0.54,
                    "status": "DEMO",
                },
                "advances": 36,
                "declines": 14,
                "unchanged": 0,
                "session_status": session,
                "ist_time": current_time_str,
                "ist_date": current_dt.strftime("%Y-%m-%d"),
                "is_demo": True,
                "mode": "DEMO",
            }

        nifty_quote = self._market_quotes.get("NIFTY 50")
        bank_quote = self._market_quotes.get("BANK NIFTY")
        constituent_quotes = [
            self._market_quotes.get(s) for s in self.get_watchlist_symbols()
        ]
        advances = sum(
            1 for q in constituent_quotes if q and q.get("change", 0) > 0
        ) or None
        declines = sum(
            1 for q in constituent_quotes if q and q.get("change", 0) < 0
        ) or None
        scans = self._load_cached_scans()
        if not (nifty_quote or bank_quote) and scans and isinstance(scans, dict):
            hits = scans.get("hits") or []
            if hits:
                advances = advances or len(hits)
                declines = declines or max(
                    0, (scans.get("scanned", 0) or len(hits)) - advances
                )

        return {
            "nifty_50": {
                "symbol": "NIFTY 50",
                "price": nifty_quote.get("price") if nifty_quote else None,
                "change": nifty_quote.get("change") if nifty_quote else None,
                "change_pct": nifty_quote.get("change_pct") if nifty_quote else None,
                "status": "LIVE" if nifty_quote else "DATA_UNAVAILABLE",
            },
            "bank_nifty": {
                "symbol": "BANK NIFTY",
                "price": bank_quote.get("price") if bank_quote else None,
                "change": bank_quote.get("change") if bank_quote else None,
                "change_pct": bank_quote.get("change_pct") if bank_quote else None,
                "status": "LIVE" if bank_quote else "DATA_UNAVAILABLE",
            },
            "advances": advances,
            "declines": declines,
            "unchanged": 0 if advances is not None else None,
            "session_status": session,
            "ist_time": current_time_str,
            "ist_date": current_dt.strftime("%Y-%m-%d"),
            "is_demo": False,
            "mode": "LIVE" if not self.offline else "OFFLINE",
        }

    def _load_cached_metrics(self) -> Dict[str, Any]:
        """Loads metrics.json if present."""
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _load_cached_scans(self) -> Dict[str, Any]:
        """Loads scan_file if present, indexing any hits by symbol."""
        combined: Dict[str, Any] = {}
        target_files = [self.scan_file]
        default_scan = os.path.join(self._project_root, "trader", "scan.json")
        if os.path.abspath(self.scan_file) == default_scan:
            watchlist_json = os.path.join(self._project_root, "trader", "watchlist.json")
            if os.path.exists(watchlist_json):
                target_files.append(watchlist_json)

        for fpath in target_files:
            if fpath and os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            hits = data.get("hits", [])
                            for h in hits:
                                if isinstance(h, dict) and "symbol" in h:
                                    raw_s = str(h["symbol"]).upper()
                                    clean_s = raw_s.replace(".NS", "").replace(".BO", "")
                                    setups = h.get("setups", [])
                                    tech_data = {
                                        "symbol": clean_s,
                                        "price": h.get("price", 0.0),
                                        "orb_breakout": "orb" in setups
                                        or "breakout_20d" in setups,
                                        "orb_high": h.get("or_high"),
                                        "orb_low": h.get("or_low"),
                                        "volume_ratio": 1.25 if "orb" in setups else 1.0,
                                        "above_vwap": True,
                                        "reclaim_ma20": "reclaim_ma20" in setups
                                        or "bull_flag" in setups,
                                        "oversold": "oversold" in setups,
                                        "oversold_bounce": "oversold_bounce" in setups,
                                        "change": 0.0,
                                        "change_pct": h.get("pct_over", 0.0),
                                    }
                                    combined[clean_s] = tech_data
                                    combined[raw_s] = tech_data
                            for k, v in data.items():
                                if isinstance(v, dict) and k not in (
                                    "hits",
                                    "filters",
                                    "meta",
                                ):
                                    combined[k] = v
                except Exception as e:
                    logger.warning("Error reading %s: %s", fpath, e)
        return combined

    def get_signals(
        self, stitcher: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """Computes confluence signals for all watchlist symbols."""
        symbols = self.get_watchlist_symbols()
        metrics = self._load_cached_metrics()
        scans = self._load_cached_scans()
        scan_has_results = bool(scans)

        if scans and isinstance(scans, dict):
            for scanned_sym, scan_val in scans.items():
                if isinstance(scan_val, dict) and "price" in scan_val:
                    clean = (
                        scanned_sym.replace(".NS", "").replace(".BO", "").strip().upper()
                    )
                    if clean and clean not in symbols:
                        symbols.append(clean)

        results = []
        for sym in symbols:
            tech = None

            # 1. First priority: Live bars from CandleStitcher
            if stitcher is not None and hasattr(stitcher, "get_bars"):
                try:
                    bars = stitcher.get_bars(sym, include_active=True)
                    if bars:
                        last_bar = bars[-1]
                        price = last_bar.get("close")
                        if price is not None and price > 0:
                            total_vol = sum(b.get("volume", 0) for b in bars)
                            vol_weighted_price = sum(
                                b.get("close", 0) * b.get("volume", 0) for b in bars
                            )
                            vwap = (
                                vol_weighted_price / total_vol
                                if total_vol > 0
                                else price
                            )
                            avg_vol = total_vol / len(bars) if bars else 1
                            vol_ratio = (
                                last_bar.get("volume", 0) / avg_vol
                                if avg_vol > 0
                                else 1.0
                            )

                            or_high = max(
                                (b.get("high") or b.get("close")) for b in bars[:3]
                            ) if len(bars) >= 3 else price * 1.01
                            or_low = min(
                                (b.get("low") or b.get("close")) for b in bars[:3]
                            ) if len(bars) >= 3 else price * 0.99
                            orb_breakout = price > or_high and len(bars) > 3

                            open_price = bars[0].get("open", price)
                            change = round(float(price) - float(open_price), 2)
                            change_pct = (
                                round((change / float(open_price)) * 100, 2)
                                if open_price
                                else 0.0
                            )

                            tech = {
                                "symbol": sym,
                                "price": float(price),
                                "change": change,
                                "change_pct": change_pct,
                                "orb_breakout": orb_breakout,
                                "orb_high": float(or_high),
                                "orb_low": float(or_low),
                                "volume_ratio": round(float(vol_ratio), 2),
                                "above_vwap": price >= vwap,
                                "vwap": round(float(vwap), 2),
                            }
                except Exception as e:
                    logger.debug(
                        "Could not derive live technicals for %s: %s", sym, e
                    )

            # 2. Second priority: Cached scanner hits
            if not tech:
                tech = scans.get(sym) or scans.get(f"{sym}.NS")

            # 3. Third priority: Demo sandbox mode
            if not tech and self.demo:
                tech = FALLBACK_TECHNICALS.get(sym)
                if not tech:
                    tech = {
                        "symbol": sym,
                        "price": 1000.0,
                        "change": 0.0,
                        "change_pct": 0.0,
                        "orb_breakout": False,
                        "volume_ratio": 1.0,
                        "above_vwap": True,
                        "vwap": 1000.0,
                    }

            # Build fund data
            fund = metrics.get(sym) or metrics.get(f"{sym}.NS")
            if not fund and self.demo:
                fund = FALLBACK_FINANCIALS.get(sym)
                if not fund:
                    fund = {
                        "ttm_pat_growth_yoy": 10.0,
                        "operating_margin": 15.0,
                        "margin_expanding": True,
                        "positive_growth_quarters": 6,
                        "ttm_revenue_growth_yoy": 8.0,
                    }

            if not tech:
                unavailable_status = (
                    "NO_SETUP" if scan_has_results else "DATA_UNAVAILABLE"
                )
                results.append({
                    "symbol": sym,
                    "price": None,
                    "technical_score": None,
                    "fundamental_score": None,
                    "confluence_score": None,
                    "signal": (
                        "NO ACTIVE SETUP" if scan_has_results else "NO DATA / UN-SCANNED"
                    ),
                    "status": unavailable_status,
                    "sector": fund.get("sector", "Equities") if fund else "Equities",
                    "sizing": {},
                    "tech_details": {},
                    "fund_details": fund or {},
                    "is_demo": False,
                })
                continue

            tech_dict = dict(tech)
            tech_dict["symbol"] = sym
            evaluated = evaluate_confluence(tech_dict, fund or {})
            evaluated["sector"] = (fund or {}).get("sector", "Equities")
            evaluated["status"] = "OK"
            evaluated["is_demo"] = self.demo
            results.append(evaluated)

        results.sort(
            key=lambda x: (
                x.get("confluence_score") is not None,
                x.get("confluence_score") or 0,
            ),
            reverse=True,
        )
        return results

    def get_stock_detail(
        self, symbol: str, stitcher: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Returns deep-dive technical and 8-quarter financial disclosure statements."""
        clean_sym = symbol.strip().upper().replace(".NS", "").replace(".BO", "")
        signals = self.get_signals(stitcher=stitcher)

        matched = next(
            (
                s
                for s in signals
                if s["symbol"] == clean_sym
                and s.get("status") not in ("DATA_UNAVAILABLE", "NO_SETUP")
            ),
            None,
        )
        if not matched:
            if not self.demo:
                has_scan = bool(self._load_cached_scans())
                return {
                    "symbol": clean_sym,
                    "price": None,
                    "technical_score": None,
                    "fundamental_score": None,
                    "confluence_score": None,
                    "signal": (
                        "NO ACTIVE SETUP" if has_scan else "NO DATA / UN-SCANNED"
                    ),
                    "status": "NO_SETUP" if has_scan else "DATA_UNAVAILABLE",
                    "sector": "NSE Equities",
                    "sizing": {},
                    "tech_details": {},
                    "fund_details": {},
                    "financial_statements": [],
                    "intraday_candles": [],
                    "is_demo": False,
                }
            tech = {
                "symbol": clean_sym,
                "price": 500.0,
                "change": 0.0,
                "change_pct": 0.0,
                "orb_breakout": False,
                "volume_ratio": 1.0,
                "above_vwap": True,
            }
            fund = {}
            matched = evaluate_confluence(tech, fund)
            matched["sector"] = "NSE Equities"
            matched["is_demo"] = True

        detail = dict(matched)

        if not self.demo:
            detail["financial_statements"] = []
            try:
                detail["intraday_candles"] = (
                    stitcher.get_bars(clean_sym, include_active=True)
                    if stitcher is not None and hasattr(stitcher, "get_bars")
                    else []
                )
            except Exception:
                detail["intraday_candles"] = []
            return detail

        # Demo mode: 8-Quarter Financial Statement normalization
        ttm_pat = detail.get("fund_details", {}).get("pat_cr", 12500.0)
        ttm_rev = detail.get("fund_details", {}).get("revenue_cr", 85000.0)
        q_rev = round(ttm_rev / 4.0, 1)
        q_pat = round(ttm_pat / 4.0, 1)
        op_margin = detail.get("fund_details", {}).get("operating_margin", 16.5)

        quarters = [
            {
                "quarter": "Q1 FY26",
                "rev_cr": round(q_rev * 1.06, 1),
                "pat_cr": round(q_pat * 1.08, 1),
                "margin_pct": op_margin,
                "yoy_pct": "+12.4%",
            },
            {
                "quarter": "Q4 FY25",
                "rev_cr": round(q_rev * 1.04, 1),
                "pat_cr": round(q_pat * 1.05, 1),
                "margin_pct": op_margin,
                "yoy_pct": "+11.8%",
            },
            {
                "quarter": "Q3 FY25",
                "rev_cr": round(q_rev * 1.02, 1),
                "pat_cr": round(q_pat * 1.03, 1),
                "margin_pct": round(op_margin - 0.4, 1),
                "yoy_pct": "+10.2%",
            },
            {
                "quarter": "Q2 FY25",
                "rev_cr": q_rev,
                "pat_cr": q_pat,
                "margin_pct": round(op_margin - 0.2, 1),
                "yoy_pct": "+9.8%",
            },
            {
                "quarter": "Q1 FY25",
                "rev_cr": round(q_rev * 0.94, 1),
                "pat_cr": round(q_pat * 0.92, 1),
                "margin_pct": round(op_margin - 0.8, 1),
                "yoy_pct": "+8.5%",
            },
            {
                "quarter": "Q4 FY24",
                "rev_cr": round(q_rev * 0.92, 1),
                "pat_cr": round(q_pat * 0.90, 1),
                "margin_pct": round(op_margin - 1.0, 1),
                "yoy_pct": "+7.9%",
            },
            {
                "quarter": "Q3 FY24",
                "rev_cr": round(q_rev * 0.90, 1),
                "pat_cr": round(q_pat * 0.88, 1),
                "margin_pct": round(op_margin - 1.2, 1),
                "yoy_pct": "+8.1%",
            },
            {
                "quarter": "Q2 FY24",
                "rev_cr": round(q_rev * 0.88, 1),
                "pat_cr": round(q_pat * 0.86, 1),
                "margin_pct": round(op_margin - 1.4, 1),
                "yoy_pct": "+7.4%",
            },
        ]
        detail["financial_statements"] = quarters

        # Demo Intraday 5-min candles
        p = detail.get("price", 500.0) or 500.0
        candles = [
            {
                "time": "09:15",
                "open": round(p * 0.993, 2),
                "high": round(p * 0.998, 2),
                "low": round(p * 0.991, 2),
                "close": round(p * 0.996, 2),
                "vol": 125000,
            },
            {
                "time": "09:20",
                "open": round(p * 0.996, 2),
                "high": round(p * 0.999, 2),
                "low": round(p * 0.994, 2),
                "close": round(p * 0.997, 2),
                "vol": 118000,
            },
            {
                "time": "09:25",
                "open": round(p * 0.997, 2),
                "high": round(p * 1.000, 2),
                "low": round(p * 0.995, 2),
                "close": round(p * 0.998, 2),
                "vol": 142000,
            },
            {
                "time": "09:30",
                "open": round(p * 0.998, 2),
                "high": round(p * 1.004, 2),
                "low": round(p * 0.998, 2),
                "close": round(p * 1.003, 2),
                "vol": 265000,
            },
            {
                "time": "09:35",
                "open": round(p * 1.003, 2),
                "high": round(p * 1.007, 2),
                "low": round(p * 1.002, 2),
                "close": p,
                "vol": 210000,
            },
        ]
        detail["intraday_candles"] = candles

        return detail
