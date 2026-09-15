from fastapi import APIRouter

router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/upcoming")
def upcoming_results():
    from core.quarterly_results import get_upcoming_results
    return {"results": get_upcoming_results()}


@router.get("/financials/{symbol}")
def stock_financials(symbol: str):
    from core.quarterly_results import get_stock_financials
    return get_stock_financials(symbol.upper())
