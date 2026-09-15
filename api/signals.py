from fastapi import APIRouter
from core.signals import generate_signals, get_all_signals

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("")
def all_signals():
    signals = get_all_signals()
    return {"signals": signals, "count": len(signals)}


@router.get("/{symbol}")
def stock_signals(symbol: str):
    signals = generate_signals(symbol)
    return {"symbol": symbol, "signals": signals, "count": len(signals)}
