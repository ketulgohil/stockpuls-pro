"""Dashboard API (port of trader_core.dashboard from Indian Day Trader).

Provides macro overview, signals, and stock detail endpoints backed by the
DashboardAggregator.

Endpoints:
  GET /api/dashboard/macro        Market overview (indices, breadth, session)
  GET /api/dashboard/signals      Confluence signals for watchlist stocks
  GET /api/dashboard/stock/{symbol} Deep-dive stock detail
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from core.trader_core.dashboard.aggregator import DashboardAggregator

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

_aggregator = DashboardAggregator(offline=False, demo=False)


@router.get("/macro")
def dashboard_macro():
    """Market overview with indices, breadth, and session status."""
    try:
        return _aggregator.get_macro_overview()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals")
def dashboard_signals():
    """Confluence signals for all watchlist symbols."""
    try:
        return {"signals": _aggregator.get_signals()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/{symbol}")
def dashboard_stock(symbol: str):
    """Deep-dive stock detail with technicals, fundamentals, and candles."""
    try:
        return _aggregator.get_stock_detail(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
