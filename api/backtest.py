from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from core.backtest import backtest_rsi, backtest_macd, backtest_sma_crossover

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    symbol: str
    strategy: str = "rsi"
    period: str = "1y"
    rsi_buy: float = 30
    rsi_sell: float = 70
    fast_period: int = 20
    slow_period: int = 50
    initial_capital: float = 100000


@router.post("")
def run_backtest(request: BacktestRequest):
    if request.strategy == "rsi":
        result = backtest_rsi(
            request.symbol,
            request.period,
            request.rsi_buy,
            request.rsi_sell,
            request.initial_capital
        )
    elif request.strategy == "macd":
        result = backtest_macd(
            request.symbol,
            request.period,
            request.initial_capital
        )
    elif request.strategy == "sma":
        result = backtest_sma_crossover(
            request.symbol,
            request.period,
            request.fast_period,
            request.slow_period,
            request.initial_capital
        )
    else:
        return {"error": "Unknown strategy. Use: rsi, macd, or sma"}
    
    return result
