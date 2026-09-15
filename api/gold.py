from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/gold", tags=["gold"])


@router.get("/prices")
def gold_silver_prices():
    from core.gold_silver import get_gold_prices, get_silver_prices
    gold = get_gold_prices()
    silver = get_silver_prices()
    return {"gold": gold, "silver": silver}


@router.get("/etfs")
def gold_etfs():
    from core.gold_silver import get_gold_etfs
    result = get_gold_etfs()
    return {"etfs": result, "count": len(result)}


@router.get("/nifty-ratio")
def gold_nifty_ratio():
    from core.gold_silver import get_gold_nifty_ratio
    result = get_gold_nifty_ratio()
    return result


class GoldValueRequest(BaseModel):
    weight_grams: float
    purity: Optional[str] = "24K"


@router.post("/calculate")
def calculate_gold(request: GoldValueRequest):
    from core.gold_silver import calculate_gold_value
    result = calculate_gold_value(request.weight_grams, request.purity)
    return result
