from fastapi import APIRouter
from core.patterns import detect_all_patterns

router = APIRouter(prefix="/api/patterns", tags=["patterns"])


@router.get("/{symbol}")
def stock_patterns(symbol: str):
    patterns = detect_all_patterns(symbol)
    return {"symbol": symbol, "patterns": patterns, "count": len(patterns)}
