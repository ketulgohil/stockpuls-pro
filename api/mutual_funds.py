from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/mutual-funds", tags=["mutual-funds"])


@router.get("")
def get_all_funds():
    from core.mutual_funds import get_all_mf_data
    return get_all_mf_data()


@router.get("/categories")
def get_categories():
    from core.mutual_funds import MF_CATEGORIES
    return MF_CATEGORIES


class SIPRequest(BaseModel):
    amount: float
    annualReturn: float
    years: int


@router.post("/sip-calculator")
def sip_calculator(request: SIPRequest):
    from core.mutual_funds import calculate_sip
    return calculate_sip(request.amount, request.annualReturn, request.years)
