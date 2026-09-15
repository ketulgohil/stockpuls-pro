from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/downstox", tags=["downstox"])


@router.get("/fii-dii")
def fii_dii():
    from core.downstox import get_fii_dii
    return get_fii_dii()


@router.get("/market-overview")
def market_overview():
    from core.downstox import get_market_overview
    return get_market_overview()


@router.get("/sentiments")
def sentiments():
    from core.downstox import get_market_sentiments
    return get_market_sentiments()


@router.get("/superinvestors")
def superinvestors():
    from core.downstox import get_superinvestors
    return {"investors": get_superinvestors()}


@router.get("/superinvestors/{slug}")
def superinvestor_detail(slug: str):
    from core.downstox import get_superinvestor_detail
    return get_superinvestor_detail(slug)


@router.get("/breakouts")
def breakouts():
    from core.downstox import get_breakouts
    return get_breakouts()


@router.get("/holidays")
def holidays():
    from core.downstox import get_holidays
    return get_holidays()


@router.get("/dividend-aristocrats")
def dividend_aristocrats():
    from core.downstox import get_dividend_aristocrats
    return {"stocks": get_dividend_aristocrats()}


@router.get("/weekly-outlook")
def weekly_outlook():
    from core.downstox import get_weekly_outlook
    return get_weekly_outlook()


@router.get("/announcements")
def announcements():
    from core.downstox import get_announcements
    return {"announcements": get_announcements()}


@router.get("/other-side")
def other_side():
    from core.downstox import get_other_side
    return get_other_side()


@router.get("/pre-open")
def pre_open():
    from core.downstox import get_pre_open
    return get_pre_open()


@router.get("/promises")
def promises():
    from core.downstox import get_promises
    return {"promises": get_promises()}


@router.get("/stocks/{symbol}")
def stock_detail(symbol: str):
    from core.downstox import get_stock_detail
    return get_stock_detail(symbol)


@router.get("/us-multibaggers")
def us_multibaggers():
    from core.downstox import get_us_multibaggers
    return get_us_multibaggers()


@router.get("/mf/schemes")
def mf_schemes(page: int = 1, limit: int = 20):
    from core.downstox import get_mf_schemes
    return get_mf_schemes(page, limit)


@router.get("/mf/scheme/{code}")
def mf_scheme_detail(code: str):
    from core.downstox import get_mf_scheme_detail
    return get_mf_scheme_detail(code)
