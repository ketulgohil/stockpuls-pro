from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import List, Optional
from core.sentinel.engine import sentinel_engine
from core.sentinel.dispatcher import dispatcher
from core.sentinel.types import SentinelConfig, SentinelAlert

router = APIRouter(prefix="/api/sentinel", tags=["sentinel"])

@router.get("/feed")
def get_sentinel_feed():
    return {"alerts": dispatcher.get_alerts()}

@router.get("/digests")
def get_sentinel_digests():
    return {"digests": dispatcher.get_digests()}

@router.post("/analyze/{symbol}")
def analyze_stock_sentinel(symbol: str):
    alert = sentinel_engine.scan_symbol(symbol)
    if alert:
        return alert.model_dump()
    # Force on-demand synthesis if no high trigger was found
    from core.data_fetcher import get_stock_data
    from core.indicators import add_all_indicators
    from core.sentinel.desks.technical_desk import TechnicalDesk
    from core.sentinel.desks.news_desk import NewsDesk
    from core.sentinel.synthesizer import GeminiSynthesizer
    from datetime import datetime

    df = get_stock_data(symbol, period="1mo", interval="1d")
    if df is not None and not df.empty:
        df = add_all_indicators(df)
    tech = TechnicalDesk.scan(symbol, df)
    news = NewsDesk.scan(symbol)
    all_findings = tech + news
    price = float(df.iloc[-1]['Close']) if (df is not None and not df.empty) else 0.0
    review = GeminiSynthesizer.synthesize_alert(symbol, price, all_findings)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return SentinelAlert(
        id=f"ondemand_{symbol}_{int(datetime.now().timestamp())}",
        symbol=symbol,
        title=f"{symbol.replace('.NS', '')}: Research Desk Dossier",
        summary="On-demand comprehensive multi-desk intelligence analysis",
        severity="INFO",
        findings=all_findings,
        analysis=review,
        created_at=now_str,
        data_as_of=now_str
    ).model_dump()

@router.post("/routine/{routine_type}")
async def trigger_routine(routine_type: str):
    if routine_type not in ("PRE_MARKET", "MIDDAY_PULSE", "POST_MARKET_WRAP"):
        raise HTTPException(status_code=400, detail="Invalid routine type")
    await sentinel_engine.run_routine(routine_type)
    return {"message": f"Routine {routine_type} triggered successfully"}

@router.get("/config")
def get_config():
    return {
        "is_running": sentinel_engine.is_running,
        "tracked_symbols": sentinel_engine.tracked_symbols
    }
