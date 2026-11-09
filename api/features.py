from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from core import upstox_data
from core.data_fetcher import get_stock_data
from core.auth import verify_api_key

router = APIRouter(prefix="/api/features", tags=["features"])


# Stock Notes
class NoteRequest(BaseModel):
    symbol: str
    note: str
    category: Optional[str] = "general"


@router.get("/notes/{symbol}")
def get_notes(symbol: str, auth: bool = Depends(verify_api_key)):
    from core.notes import get_notes
    notes = get_notes(symbol)
    return {"symbol": symbol, "notes": notes, "count": len(notes)}


@router.post("/notes")
def add_note(request: NoteRequest, auth: bool = Depends(verify_api_key)):
    from core.notes import add_note
    note = add_note(request.symbol, request.note, request.category)
    return note


@router.delete("/notes/{symbol}/{note_id}")
def delete_note(symbol: str, note_id: int, auth: bool = Depends(verify_api_key)):
    from core.notes import delete_note
    deleted = delete_note(symbol, note_id)
    if not deleted:
        return {"error": "Note not found"}
    return {"message": "Note deleted"}


@router.get("/notes")
def all_notes(auth: bool = Depends(verify_api_key)):
    from core.notes import get_all_notes
    return get_all_notes()


# Earnings Calendar - Live from Yahoo Finance
@router.get("/earnings")
def earnings_calendar():
    from core.fundamentals import get_earnings_calendar
    earnings = get_earnings_calendar()
    return {"earnings": earnings, "count": len(earnings)}


# FII/DII Activity
@router.get("/fii-dii")
def fii_dii_activity():
    activity = []
    
    try:
        for symbol in ["^NSEI", "^BSESN"]:
            hist = get_stock_data(symbol, period="1mo")
            if hist is not None and len(hist) >= 2:
                change = ((hist["Close"].iloc[-1] - hist["Close"].iloc[-2]) / hist["Close"].iloc[-2]) * 100
                activity.append({
                    "index": symbol,
                    "name": "NIFTY 50" if "NSEI" in symbol else "SENSEX",
                    "current": round(float(hist["Close"].iloc[-1]), 2),
                    "monthly_change": round(float(change), 2)
                })
    except:
        pass
    
    fii_data = {
        "note": "FII/DII actual flows require NSE/BSE paid data",
        "recent_activity": activity,
        "suggestion": "Check moneycontrol.com or NSE for real-time FII/DII data"
    }
    
    return fii_data


# Multi-Chart Data
@router.get("/multi-chart")
def multi_chart_data(symbols: str = "RELIANCE.NS,TCS.NS,HDFCBANK.NS"):
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    chart_data = {}
    
    for symbol in symbol_list[:5]:
        try:
            hist = get_stock_data(symbol, period="6mo")
            if hist is not None and not hist.empty:
                normalized = []
                base_price = hist["Close"].iloc[0]
                if not base_price:
                    continue
                for date, row in hist.iterrows():
                    date_str = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)[:10]
                    normalized.append({
                        "date": date_str,
                        "value": round(float((row["Close"] / base_price) * 100), 2)
                    })
                chart_data[symbol.replace(".NS", "")] = normalized
        except:
            continue
    
    return {"symbols": list(chart_data.keys()), "data": chart_data}
