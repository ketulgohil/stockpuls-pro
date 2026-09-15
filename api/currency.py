from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/currency", tags=["currency"])


@router.get("/rate/{from_currency}")
def get_rate(from_currency: str, to_currency: str = "INR"):
    from core.currency import get_exchange_rate
    result = get_exchange_rate(from_currency.upper(), to_currency.upper())
    if not result:
        return {"error": "Could not fetch rate"}
    return result


class ConvertRequest(BaseModel):
    amount: float
    fromCurrency: str
    toCurrency: str = "INR"


@router.post("/convert")
def convert_currency(request: ConvertRequest):
    from core.currency import convert
    return convert(request.amount, request.fromCurrency.upper(), request.toCurrency.upper())


@router.get("/currencies")
def get_currencies():
    from core.currency import CURRENCIES
    return CURRENCIES
