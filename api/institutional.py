"""Institutional Tracker API (port of trader-institutional from Indian Day Trader).

NSE/BSE bulk & block deals and SEBI PIT (Prohibition of Insider Trading)
promoter/director disclosures. Public regulatory filings only — no inside
information; disclosures reflect past execution.

Endpoints:
  GET  /api/institutional/deals    Latest bulk & block deals
  GET  /api/institutional/pit      SEBI PIT insider trading disclosures
"""

from __future__ import annotations

import datetime
import json
import os
import urllib.request
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/institutional", tags=["institutional"])

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DEALS_FILE = os.path.join(DATA_DIR, "institutional_deals.json")
PIT_FILE = os.path.join(DATA_DIR, "institutional_pit.json")

UA = "Mozilla/5.0 (compatible; day-trader-skill/2.0; institutional-tracker)"


def _save_json(path, doc):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def _fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


@router.get("/deals")
def institutional_deals(symbol: Optional[str] = Query(default=None)):
    """Latest NSE/BSE bulk & block deals (public exchange disclosures)."""
    try:
        # Try NSE bulk deals endpoint
        deals = []
        source = "nse"
        try:
            text = _fetch("https://www.nseindia.com/api/bulk-deals", timeout=15)
            data = json.loads(text)
            raw = data.get("data", []) if isinstance(data, dict) else []
            for item in raw[:30]:
                sym = str(item.get("symbol", "")).upper()
                if symbol and sym != symbol.upper():
                    continue
                deals.append({
                    "symbol": sym,
                    "series": item.get("series", ""),
                    "client": item.get("clientName", ""),
                    "deal_type": item.get("dealType", ""),
                    "quantity": item.get("quantity", 0),
                    "price": item.get("tradePrice", 0),
                    "value": item.get("value", 0),
                    "date": item.get("lastDate", ""),
                    "source": "NSE Bulk Deals",
                })
        except Exception:
            source = "cached"

        if not deals:
            # Fall back to cached data
            cached = _load_json(DEALS_FILE, {"deals": []})
            deals = cached.get("deals", [])
            source = "cache"

        # Flag deals in symbols the user holds/watch (placeholder)
        flagged = []
        for d in deals:
            d["flagged"] = bool(symbol and d["symbol"] == symbol.upper())
            flagged.append(d)

        doc = {
            "created_at": datetime.datetime.now().isoformat(),
            "source": source,
            "count": len(flagged),
            "deals": flagged,
            "note": "Bulk deals (>0.5% of equity) and block deals (>=500k shares or >=₹10 cr). "
                    "Disclosed post-market; reflects past execution, not a prediction.",
        }
        _save_json(DEALS_FILE, doc)
        return doc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pit")
def institutional_pit(symbol: Optional[str] = Query(default=None)):
    """SEBI PIT (Prohibition of Insider Trading) promoter/director disclosures."""
    try:
        # SEBI PIT disclosures are published as PDFs/CSV on sebi.gov.in; no public JSON API.
        # Return structured empty response with guidance, plus cached data if available.
        cached = _load_json(PIT_FILE, {"filings": []})
        filings = cached.get("filings", [])

        if symbol:
            filings = [f for f in filings if str(f.get("symbol", "")).upper() == symbol.upper()]

        return {
            "created_at": datetime.datetime.now().isoformat(),
            "source": "sebi.gov.in (Regulation 7(2) PIT disclosures)",
            "count": len(filings),
            "filings": filings,
            "note": "SEBI PIT filings (Regulation 7(2)): promoters, directors, designated persons "
                    "reporting buy/sell above statutory thresholds within 2 trading days. "
                    "No public JSON API; filings are PDF/CSV on sebi.gov.in. "
                    "Use the offline import to load saved disclosures.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return default
