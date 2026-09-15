from fastapi import APIRouter
from typing import List, Optional
from core.correlation import calculate_correlation, get_most_correlated

router = APIRouter(prefix="/api/correlation", tags=["correlation"])


@router.get("")
def correlation_matrix(symbols: str = "RELIANCE.NS,TCS.NS,HDFCBANK.NS,INFY.NS"):
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    result = calculate_correlation(symbol_list)
    return result


@router.get("/{symbol}")
def stock_correlation(symbol: str, limit: int = 10):
    result = get_most_correlated(symbol, limit)
    return {"symbol": symbol, "correlated": result, "count": len(result)}
