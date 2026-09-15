from fastapi import APIRouter, Query
from typing import Optional
from core.screener import screen_stocks

router = APIRouter(prefix="/api/screen", tags=["screener"])


@router.get("")
def screener(
    rsi_below: Optional[float] = Query(default=None, ge=0, le=100),
    rsi_above: Optional[float] = Query(default=None, ge=0, le=100),
    macd_cross_up: Optional[bool] = Query(default=None),
    price_above_sma: Optional[int] = Query(default=None),
    price_below_sma: Optional[int] = Query(default=None),
    volume_above_avg: Optional[float] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50)
):
    results = screen_stocks(
        rsi_below=rsi_below,
        rsi_above=rsi_above,
        macd_cross_up=macd_cross_up,
        price_above_sma=price_above_sma,
        price_below_sma=price_below_sma,
        volume_above_avg=volume_above_avg,
        limit=limit
    )
    return {"results": results, "count": len(results)}
