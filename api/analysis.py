from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any
from core.multi_timeframe import multi_timeframe_analysis, custom_strategy_backtest

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/multi-timeframe/{symbol}")
def multi_timeframe(symbol: str):
    result = multi_timeframe_analysis(symbol)
    return result


class CustomStrategyRequest(BaseModel):
    symbol: str
    strategy_name: str = "Custom Strategy"
    buy_conditions: Dict[str, Any]
    sell_conditions: Dict[str, Any]
    period: str = "1y"
    initial_capital: float = 100000


@router.post("/custom-strategy")
def custom_strategy(request: CustomStrategyRequest):
    result = custom_strategy_backtest(
        request.symbol,
        request.strategy_name,
        request.buy_conditions,
        request.sell_conditions,
        request.period,
        request.initial_capital
    )
    return result
