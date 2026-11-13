from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from core.upstox.client import UpstoxClient
from core.upstox.stream import upstox_engine
from core.intraday.orb import ORBScanner
from core.intraday.signals import ConfluenceSignalEngine
from core.intraday.paper_trading import PaperTradingDesk
from core.intraday.backtest import IntradayBacktester
from core.auth import verify_api_key

router = APIRouter(prefix="/api/upstox", tags=["upstox"])

upstox_client = UpstoxClient()
paper_desk = PaperTradingDesk()
orb_scanner = ORBScanner()
signal_engine = ConfluenceSignalEngine()
backtester = IntradayBacktester()

class PaperOrderRequest(BaseModel):
    symbol: str
    quantity: int = Field(..., gt=0)
    stop_loss: float
    target: float
    notes: Optional[str] = ""
    entry_price: Optional[float] = None

class PaperCloseRequest(BaseModel):
    exit_price: Optional[float] = None
    reason: Optional[str] = "MANUAL"

class BacktestApiRequest(BaseModel):
    symbol: str = "RELIANCE"
    period: str = "1d"
    interval: str = "5minute"

@router.get("/status")
def get_upstox_status():
    return {
        "status": "active" if upstox_engine.is_running else "stopped",
        "engine_running": upstox_engine.is_running,
        "token_configured": upstox_client.is_authenticated,
        "tracked_symbols_count": len(upstox_engine.symbols),
        "latest_quotes_count": len(upstox_engine.get_latest_quotes()),
        "timestamp": datetime.now().isoformat()
    }

@router.get("/quotes")
async def get_upstox_quotes():
    quotes = upstox_engine.get_latest_quotes()
    if not quotes and upstox_client.is_authenticated:
        quotes = await upstox_client.get_quotes(upstox_engine.symbols)
    return {"quotes": quotes, "count": len(quotes)}

@router.get("/quote/{symbol}")
async def get_upstox_quote_detail(symbol: str):
    clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "").strip()
    depth = await upstox_client.get_market_depth(clean_sym)
    quotes = upstox_engine.get_latest_quotes()
    q = quotes.get(clean_sym) or quotes.get(symbol)
    if q:
        depth.update({
            "last_price": q.get("last_price") or q.get("currentPrice", 0.0),
            "vwap": q.get("vwap", 0.0),
            "volume": q.get("volume", 0),
            "net_change": q.get("net_change", 0.0),
            "change_percent": q.get("change_percent", 0.0)
        })
    return depth

@router.get("/scanner/orb")
def get_orb_scanner_results():
    breakouts = orb_scanner.scan_all(engine=upstox_engine)
    return {"breakouts": breakouts, "count": len(breakouts)}

@router.get("/scanner/signals")
def get_signals_scanner_results():
    signals = signal_engine.scan_all(engine=upstox_engine)
    return {"signals": signals, "count": len(signals)}

@router.get("/paper/portfolio")
def get_paper_portfolio(auth: bool = Depends(verify_api_key)):
    quotes = upstox_engine.get_latest_quotes()
    paper_desk.update_mtm(quotes, engine=upstox_engine)
    summary = paper_desk.get_summary()
    summary["virtual_cash"] = summary.get("cash", 0.0)
    return summary

@router.post("/paper/order")
def execute_paper_order(req: PaperOrderRequest, auth: bool = Depends(verify_api_key)):
    try:
        position = paper_desk.execute_buy(
            symbol=req.symbol,
            quantity=req.quantity,
            stop_loss=req.stop_loss,
            target=req.target,
            notes=req.notes or "",
            entry_price=req.entry_price,
            engine=upstox_engine
        )
        return {"status": "success", "position": position}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/paper/close/{position_id}")
def close_paper_position(position_id: str, req: PaperCloseRequest, auth: bool = Depends(verify_api_key)):
    try:
        closed = paper_desk.close_position(
            position_id=position_id,
            exit_price=req.exit_price,
            reason=req.reason or "MANUAL",
            engine=upstox_engine
        )
        return {"status": "success", "position": closed}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/paper/reset")
def reset_paper_portfolio(initial_capital: float = 10000000.0, auth: bool = Depends(verify_api_key)):
    paper_desk.cash = initial_capital
    paper_desk.initial_capital = initial_capital
    paper_desk.positions = []
    paper_desk._save_state()
    summary = paper_desk.get_summary()
    summary["virtual_cash"] = summary.get("cash", 0.0)
    return {"status": "success", "summary": summary}

@router.post("/backtest")
async def run_intraday_backtest(req: BacktestApiRequest):
    clean_sym = req.symbol.upper().replace(".NS", "").replace(".BO", "").strip()
    candles = await upstox_client.get_candles(clean_sym, interval=req.interval)
    if not candles or len(candles) < 5:
        candles = upstox_engine.get_5m_candles(clean_sym)

    result = backtester.run_orb_backtest(clean_sym, candles)
    return result

# WebSocket Route for real-time Upstox feed.
# Registered on a prefix-less router so the browser connects to /ws/upstox/live
# (the /api/upstox prefix above would otherwise prepend to the WS path).
ws_router = APIRouter()

@ws_router.websocket("/ws/upstox/live")
async def websocket_upstox_live(websocket: WebSocket):
    await websocket.accept()

    # Greet with engine state + a full snapshot so the desk renders instantly.
    try:
        await websocket.send_json(upstox_engine.hello_payload())
    except Exception:
        pass

    async def on_market_update(data):
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    upstox_engine.subscribe(on_market_update)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        upstox_engine.unsubscribe(on_market_update)
