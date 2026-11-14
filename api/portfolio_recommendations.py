"""Portfolio recommendation API — latest labels, immutable history, outcome
performance stats, and a rate-limited manual rescan.

All endpoints are informational: they never place orders or mutate holdings.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth import verify_api_key
from core.portfolio import get_portfolio
from core.recommendation_store import get_store
from core.recommendation_evaluator import SUCCESS_DEFINITIONS
from core.trader_core import IST, is_trading_day

router = APIRouter(prefix="/api/portfolio/recommendations", tags=["portfolio-recommendations"])


def _next_scan_iso(now: datetime) -> Optional[str]:
    from core.portfolio_recommendations import SCAN_TIME
    from core.recommendation_evaluator import next_trading_dates
    try:
        days = next_trading_dates(now.date(), 1)
    except Exception:
        return None
    if not days:
        return None
    target_date = days[0]
    candidate = datetime.combine(target_date, SCAN_TIME, tzinfo=IST)
    if candidate <= now:
        # today's slot already passed → next scan is the day after
        later = next_trading_dates(target_date, 1)
        if not later:
            return None
        candidate = datetime.combine(later[0], SCAN_TIME, tzinfo=IST)
    return candidate.isoformat(timespec="seconds")


def _market_note(now: datetime) -> Optional[str]:
    try:
        trading = is_trading_day(now.date())
    except Exception:
        return "Holiday calendar unavailable — weekend check only"
    if trading:
        return None
    if now.weekday() >= 5:
        return "Weekend — markets closed; no scan runs today"
    return "NSE market holiday — no scan runs today"


@router.get("/latest")
def latest_recommendations(auth: bool = Depends(verify_api_key)):
    """Latest daily and intraday recommendation per current holding, plus scan
    status. Read-only; served from the durable store, not request-time scans."""
    store = get_store()
    now = datetime.now(IST)
    symbols = [h.get("symbol") for h in get_portfolio()]
    latest = store.latest_recommendations()
    scan = store.latest_completed_scan() or store.latest_scan_any_status()
    return {
        "asOf": now.isoformat(timespec="seconds"),
        "scan": scan,
        "nextScanAt": _next_scan_iso(now),
        "marketNote": _market_note(now),
        "calendarLimitation": (
            None if now.year <= 2026 else
            "The bundled NSE holiday calendar covers 2026 only — scans after that "
            "skip weekends but cannot know holidays until the calendar is updated"
        ),
        "recommendations": {s: latest[s] for s in symbols if s in latest},
    }


@router.get("/history")
def recommendation_history(
    symbol: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=500),
    auth: bool = Depends(verify_api_key),
):
    """Immutable recommendation records for one symbol (newest first)."""
    clean = symbol.upper().strip()
    if not clean.endswith(".NS"):
        clean += ".NS"
    rows = get_store().history_for_symbol(clean, limit)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No recommendation history for {clean}")
    return {"symbol": clean, "count": len(rows), "records": rows}


@router.get("/performance")
def recommendation_performance(
    horizon: Optional[str] = Query(None, description="daily_swing | intraday"),
    type: Optional[str] = Query(None, description="BUY | SELL | HOLD | NO_DATA | NOT_ENOUGH_DATA"),
    days: int = Query(90, ge=1, le=365, description="Look back this many calendar days"),
    strategy: Optional[str] = Query(None),
    auth: bool = Depends(verify_api_key),
):
    """Aggregated outcome statistics with their exact definitions, denominators
    and pending/failed counts. Traceable to stored records via /history."""
    from core.recommendation_evaluator import summarize_performance
    store = get_store()
    since = (datetime.now(IST).date() - timedelta(days=days)).isoformat()
    rows = store.evaluation_rows(
        horizon=horizon, rec_type=type, since_date=since, strategy=strategy)
    summary = summarize_performance(rows)
    summary["filters"] = {
        "horizon": horizon, "type": type, "days": days, "strategy": strategy,
        "sinceDate": since,
    }
    summary["definitions"] = SUCCESS_DEFINITIONS
    return summary


@router.post("/rescan")
def manual_rescan(auth: bool = Depends(verify_api_key)):
    """Explicit manual rescan — rate-limited to once per 10 minutes and
    serialized with the scheduled scan; appends new immutable records."""
    from core.portfolio_recommendations import run_manual_rescan
    result = run_manual_rescan()
    if result.get("status") == "cooldown":
        raise HTTPException(status_code=429, detail=result.get("error"))
    if result.get("status") == "failed":
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result
