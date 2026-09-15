from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/api/features", tags=["features"])


# Stock Notes
class NoteRequest(BaseModel):
    symbol: str
    note: str
    category: Optional[str] = "general"


@router.get("/notes/{symbol}")
def get_notes(symbol: str):
    from core.notes import get_notes
    notes = get_notes(symbol)
    return {"symbol": symbol, "notes": notes, "count": len(notes)}


@router.post("/notes")
def add_note(request: NoteRequest):
    from core.notes import add_note
    note = add_note(request.symbol, request.note, request.category)
    return note


@router.delete("/notes/{symbol}/{note_id}")
def delete_note(symbol: str, note_id: int):
    from core.notes import delete_note
    deleted = delete_note(symbol, note_id)
    if not deleted:
        return {"error": "Note not found"}
    return {"message": "Note deleted"}


@router.get("/notes")
def all_notes():
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
    import yfinance as yf
    
    activity = []
    
    try:
        for symbol in ["^NSEI", "^BSESN"]:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1mo")
            if len(hist) >= 2:
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
    import yfinance as yf
    
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    chart_data = {}
    
    for symbol in symbol_list[:5]:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="6mo")
            if not hist.empty:
                normalized = []
                base_price = hist["Close"].iloc[0]
                for date, row in hist.iterrows():
                    normalized.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "value": round(float((row["Close"] / base_price) * 100), 2)
                    })
                chart_data[symbol.replace(".NS", "")] = normalized
        except:
            continue
    
    return {"symbols": list(chart_data.keys()), "data": chart_data}
