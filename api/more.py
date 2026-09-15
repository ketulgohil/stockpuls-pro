from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/more", tags=["more"])


@router.get("/ipo")
def ipo_data():
    from core.more_features import get_ipo_data
    result = get_ipo_data()
    return {"ipos": result, "count": len(result)}


@router.get("/financials/{symbol}")
def stock_financials(symbol: str):
    from core.more_features import get_stock_financials
    result = get_stock_financials(symbol)
    return result


@router.get("/dividends/{symbol}")
def dividend_history(symbol: str):
    from core.more_features import get_dividend_history
    result = get_dividend_history(symbol)
    return result


@router.get("/market-status")
def market_status():
    from core.more_features import get_market_status
    result = get_market_status()
    return result


@router.get("/calendar")
def economic_calendar():
    from core.more_features import get_economic_calendar
    result = get_economic_calendar()
    return {"events": result, "count": len(result)}


class SIPRequest(BaseModel):
    monthly_amount: float
    expected_return: float
    years: int


@router.post("/sip-calculator")
def sip_calculator(request: SIPRequest):
    monthly_rate = request.expected_return / 100 / 12
    months = request.years * 12
    
    future_value = 0
    for i in range(months):
        future_value = (future_value + request.monthly_amount) * (1 + monthly_rate)
    
    total_invested = request.monthly_amount * months
    wealth_gained = future_value - total_invested
    
    return {
        "monthly_investment": request.monthly_amount,
        "years": request.years,
        "expected_return": request.expected_return,
        "total_invested": round(total_invested, 2),
        "future_value": round(future_value, 2),
        "wealth_gained": round(wealth_gained, 2),
        "return_percentage": round((wealth_gained / total_invested) * 100, 2)
    }


class TaxRequest(BaseModel):
    selling_price: float
    buying_price: float
    quantity: int
    holding_period: str  # "short" or "long"


@router.post("/tax-calculator")
def tax_calculator(request: TaxRequest):
    total_sale = request.selling_price * request.quantity
    total_cost = request.buying_price * request.quantity
    profit = total_sale - total_cost
    
    if profit <= 0:
        return {
            "profit": round(profit, 2),
            "tax": 0,
            "tax_rate": 0,
            "net_profit": round(profit, 2),
            "note": "No tax on losses"
        }
    
    if request.holding_period == "short":
        # STCG - 15% for equity
        tax_rate = 15
        tax = profit * tax_rate / 100
    else:
        # LTCG - 10% above ₹1 lakh
        if profit > 100000:
            tax = (profit - 100000) * 10 / 100
        else:
            tax = 0
        tax_rate = 10 if profit > 100000 else 0
    
    return {
        "total_sale": round(total_sale, 2),
        "total_cost": round(total_cost, 2),
        "profit": round(profit, 2),
        "holding_period": request.holding_period,
        "tax_rate": f"{tax_rate}%",
        "tax": round(tax, 2),
        "net_profit": round(profit - tax, 2),
        "note": "STCG: 15% | LTCG: 10% above ₹1 lakh"
    }
