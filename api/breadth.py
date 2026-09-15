from fastapi import APIRouter
from core.breadth import get_market_breadth

router = APIRouter(prefix="/api/breadth", tags=["breadth"])


@router.get("")
def market_breadth():
    result = get_market_breadth()
    return result
