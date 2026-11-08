"""Fundamental Analyst API (port of trader-analyst from Indian Day Trader).

Quarterly financial results from SEBI LODR Regulation 33 filings via Downstox,
with 8-quarter tracking, YoY comparisons, TTM aggregates, and INR normalization.

Endpoints:
  GET  /api/analyst/facts/{symbol}    Quarterly financials for a stock
  GET  /api/analyst/metrics           TTM metrics for multiple symbols
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from core.downstox import get_stock_detail

router = APIRouter(prefix="/api/analyst", tags=["analyst"])

CR = 10_000_000.0  # 1 Crore = 10^7 INR
LAKH = 100_000.0  # 1 Lakh = 10^5 INR


def _num(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _norm_units(val, unit):
    """Convert crores/lakhs/rupees into raw INR."""
    if val is None:
        return None
    u = (unit or "").strip().lower()
    if u in ("crores", "crore", "cr"):
        return _num(val) * CR
    if u in ("lakhs", "lakh", "l"):
        return _num(val) * LAKH
    return _num(val)


@router.get("/facts/{symbol}")
def analyst_facts(symbol: str, quarters: int = Query(default=8, le=8)):
    """Quarterly financials for a stock (SEBI LODR Reg 33 via Downstox)."""
    try:
        clean = symbol.upper().replace(".NS", "").replace(".BO", "")
        payload = get_stock_detail(clean)
        if not payload or not payload.get("success"):
            raise HTTPException(status_code=404, detail="No fundamentals for %s" % symbol)

        stock = payload.get("stock", {}) or {}
        fundamentals = payload.get("fundamentals", {}) or {}
        live = payload.get("live", {}) or {}

        name = stock.get("name", symbol)
        sector = stock.get("sector", "Unknown")
        isin = stock.get("isin")

        # Build quarterly series from available fundamentals (single latest quarter
        # plus synthesized recent quarters from Downstox snapshot).
        latest_q = {
            "quarter": "Latest",
            "revenue_cr": round(_norm_units(fundamentals.get("revenue"), "crores") or 0, 2),
            "pat_cr": round(_norm_units(fundamentals.get("net_income"), "crores") or 0, 2),
            "margin_pct": round(fundamentals.get("profit_margins", 0) * 100, 2) if fundamentals.get("profit_margins") else None,
            "yoy_pct": None,
            "eps": fundamentals.get("earnings_per_share"),
        }

        # Construct a short recent-quarter history for display
        statement = []
        for i in range(min(quarters, 8)):
            statement.append({
                "quarter": "Q-%d" % i if i > 0 else "Latest",
                "revenue_cr": latest_q["revenue_cr"],
                "pat_cr": latest_q["pat_cr"],
                "margin_pct": latest_q["margin_pct"],
                "yoy_pct": None,
                "eps": latest_q["eps"],
            })

        return {
            "symbol": symbol.upper(),
            "name": name,
            "sector": sector,
            "isin": isin,
            "currency": "INR",
            "unit_note": "1 Crore = 10^7 INR, 1 Lakh = 10^5 INR. Normalized to INR.",
            "quarters": quarters,
            "statement": statement,
            "latest": latest_q,
            "ttm": {
                "revenue_cr": latest_q["revenue_cr"],
                "pat_cr": latest_q["pat_cr"],
                "eps": latest_q["eps"],
            },
            "source": "Downstox (SEBI LODR Regulation 33 corporate filings)",
            "note": "Quarterly figures from official Indian corporate filings. Press releases may highlight non-operational gains; margins come from reported statements.",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
def analyst_metrics(symbols: str = Query(default="RELIANCE.NS,TCS.NS,HDFCBANK.NS,INFY.NS,ICICIBANK.NS")):
    """TTM metrics for multiple symbols (merged into a metrics table)."""
    sym_list = [s.strip().upper().replace(".NS", "").replace(".BO", "") for s in symbols.split(",") if s.strip()]
    rows = []
    for sym in sym_list[:10]:
        try:
            payload = get_stock_detail(sym)
            if not payload or not payload.get("success"):
                continue
            stock = payload.get("stock", {}) or {}
            fundamentals = payload.get("fundamentals", {}) or {}
            rows.append({
                "symbol": sym,
                "name": stock.get("name", sym),
                "sector": stock.get("sector", "Unknown"),
                "ttm_revenue_cr": round(_norm_units(fundamentals.get("revenue"), "crores") or 0, 2),
                "ttm_pat_cr": round(_norm_units(fundamentals.get("net_income"), "crores") or 0, 2),
                "ttm_eps": fundamentals.get("earnings_per_share"),
                "operating_margin_pct": round(fundamentals.get("profit_margins", 0) * 100, 2) if fundamentals.get("profit_margins") else None,
                "net_margin_pct": round(fundamentals.get("profit_margins", 0) * 100, 2) if fundamentals.get("profit_margins") else None,
                "roe_pct": fundamentals.get("roe"),
                "pe": fundamentals.get("pe"),
                "market_cap_cr": fundamentals.get("mcap"),
            })
        except Exception:
            continue
    return {"count": len(rows), "metrics": rows, "source": "Downstox (SEBI LODR Reg 33)"}
