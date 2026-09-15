from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/tools", tags=["tools"])


class RiskCalcRequest(BaseModel):
    account_size: float
    risk_percent: float
    entry_price: float
    stop_loss: float


class PositionSizeRequest(BaseModel):
    account_size: float
    risk_percent: float
    entry_price: float
    stop_loss: float
    current_price: Optional[float] = None


@router.post("/risk-calculator")
def calculate_risk(request: RiskCalcRequest):
    risk_amount = request.account_size * (request.risk_percent / 100)
    risk_per_share = abs(request.entry_price - request.stop_loss)

    if risk_per_share == 0:
        return {"error": "Entry and stop loss cannot be same"}

    position_size = int(risk_amount / risk_per_share)
    total_investment = position_size * request.entry_price
    potential_loss = position_size * risk_per_share

    return {
        "account_size": request.account_size,
        "risk_percent": request.risk_percent,
        "risk_amount": round(risk_amount, 2),
        "entry_price": request.entry_price,
        "stop_loss": request.stop_loss,
        "risk_per_share": round(risk_per_share, 2),
        "position_size": position_size,
        "total_investment": round(total_investment, 2),
        "potential_loss": round(potential_loss, 2),
        "risk_reward": "Calculate manually"
    }


@router.post("/position-size")
def calculate_position_size(request: PositionSizeRequest):
    risk_amount = request.account_size * (request.risk_percent / 100)
    risk_per_share = abs(request.entry_price - request.stop_loss)

    if risk_per_share == 0:
        return {"error": "Entry and stop loss cannot be same"}

    position_size = int(risk_amount / risk_per_share)
    total_investment = position_size * request.entry_price

    current_price = request.current_price or request.entry_price
    unrealized_pnl = (current_price - request.entry_price) * position_size

    return {
        "account_size": request.account_size,
        "risk_percent": request.risk_percent,
        "risk_amount": round(risk_amount, 2),
        "entry_price": request.entry_price,
        "stop_loss": request.stop_loss,
        "current_price": current_price,
        "risk_per_share": round(risk_per_share, 2),
        "position_size": position_size,
        "total_investment": round(total_investment, 2),
        "unrealized_pnl": round(unrealized_pnl, 2)
    }


@router.get("/fibonacci/{symbol}")
def get_fibonacci_levels(symbol: str):
    from core.data_fetcher import get_stock_data
    from core.indicators import fibonacci_levels

    df = get_stock_data(symbol, period="6mo")
    if df is None:
        return {"error": "No data found"}

    fib = fibonacci_levels(df)
    return {"symbol": symbol, **fib}
