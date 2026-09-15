from fastapi import APIRouter
from core.fundamentals import get_earnings_calendar, get_dividend_stocks, get_fii_dii_data

router = APIRouter(prefix="/api/fundamentals", tags=["fundamentals"])


@router.get("/earnings")
def earnings_calendar():
    result = get_earnings_calendar()
    return {"earnings": result, "count": len(result)}


@router.get("/dividends")
def dividend_stocks():
    result = get_dividend_stocks()
    return {"stocks": result, "count": len(result)}


@router.get("/fii-dii")
def fii_dii_data():
    result = get_fii_dii_data()
    return result
