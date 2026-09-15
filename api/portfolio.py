from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.portfolio import (
    get_portfolio, add_holding, remove_holding,
    get_watchlist, add_to_watchlist, remove_from_watchlist
)
from core.data_fetcher import get_live_price

router = APIRouter(prefix="/api", tags=["portfolio"])


class HoldingRequest(BaseModel):
    symbol: str
    quantity: float
    buy_price: float


class WatchlistRequest(BaseModel):
    symbol: str
    name: Optional[str] = ""


@router.get("/portfolio")
def portfolio():
    holdings = get_portfolio()
    for holding in holdings:
        price_data = get_live_price(holding["symbol"])
        if price_data:
            holding["currentPrice"] = price_data["price"]
            holding["pnl"] = round((price_data["price"] - holding["buyPrice"]) * holding["quantity"], 2)
            holding["pnlPercent"] = round((price_data["price"] - holding["buyPrice"]) / holding["buyPrice"] * 100, 2)
        else:
            holding["currentPrice"] = holding["buyPrice"]
            holding["pnl"] = 0
            holding["pnlPercent"] = 0
    return {"holdings": holdings}


@router.post("/portfolio")
def add_portfolio_holding(request: HoldingRequest):
    holding = add_holding(request.symbol, request.quantity, request.buy_price)
    return holding


@router.delete("/portfolio/{symbol}")
def remove_portfolio_holding(symbol: str):
    removed = remove_holding(symbol)
    if not removed:
        raise HTTPException(status_code=404, detail="Holding not found")
    return {"message": f"Removed {symbol} from portfolio"}


@router.get("/watchlist")
def watchlist():
    symbols = get_watchlist()
    for item in symbols:
        price_data = get_live_price(item["symbol"])
        if price_data:
            item["price"] = price_data["price"]
            item["change"] = round(price_data["price"] - price_data["previousClose"], 2)
            item["changePercent"] = round((price_data["price"] - price_data["previousClose"]) / price_data["previousClose"] * 100, 2)
    return {"watchlist": symbols}


@router.post("/watchlist")
def add_to_watchlist_endpoint(request: WatchlistRequest):
    item = add_to_watchlist(request.symbol, request.name)
    return item


@router.delete("/watchlist/{symbol}")
def remove_from_watchlist_endpoint(symbol: str):
    removed = remove_from_watchlist(symbol)
    if not removed:
        raise HTTPException(status_code=404, detail="Symbol not found in watchlist")
    return {"message": f"Removed {symbol} from watchlist"}
