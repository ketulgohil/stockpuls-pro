from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from core.portfolio import (
    get_portfolio, add_holding, remove_holding, sell_holding, get_realized_trades,
    add_dividend, apply_corp_action, get_dividend_records,
    get_watchlist, add_to_watchlist, remove_from_watchlist
)
from core.data_fetcher import get_live_price
from core.auth import verify_api_key

router = APIRouter(prefix="/api", tags=["portfolio"])


class HoldingRequest(BaseModel):
    symbol: str
    quantity: float
    buy_price: float


class SellRequest(BaseModel):
    quantity: float
    price: Optional[float] = None


class DividendRequest(BaseModel):
    amount: float
    date: Optional[str] = None
    note: Optional[str] = ""


class CorpActionRequest(BaseModel):
    ratio: float
    type: str = "split"
    date: Optional[str] = None


class WatchlistRequest(BaseModel):
    symbol: str
    name: Optional[str] = ""


def _enrich_holdings() -> dict:
    """Attach live prices, P&L and today's (day-change) P&L to holdings."""
    holdings = get_portfolio()
    summary = {
        "totalValue": 0.0, "totalInvested": 0.0,
        "totalPnl": 0.0, "totalDayPnl": 0.0, "totalReturn": 0.0,
    }
    for holding in holdings:
        qty = holding.get("quantity", 0) or 0
        buy = holding.get("buyPrice", 0) or 0
        price_data = get_live_price(holding["symbol"])
        if price_data:
            price = price_data["price"]
            prev_close = price_data.get("previousClose") or price
            holding["currentPrice"] = price
            holding["pnl"] = round((price - buy) * qty, 2)
            holding["pnlPercent"] = round((price - buy) / buy * 100, 2) if buy else 0
            holding["dayChange"] = round(price - prev_close, 2)
            holding["dayChangePnl"] = round((price - prev_close) * qty, 2)
        else:
            holding["currentPrice"] = buy
            holding["pnl"] = 0
            holding["pnlPercent"] = 0
            holding["dayChange"] = 0
            holding["dayChangePnl"] = 0
        summary["totalValue"] += holding["currentPrice"] * qty
        summary["totalInvested"] += buy * qty
        summary["totalPnl"] += holding["pnl"]
        summary["totalDayPnl"] += holding["dayChangePnl"]
    summary = {k: round(v, 2) for k, v in summary.items()}
    summary["totalReturn"] = round(summary["totalPnl"] / summary["totalInvested"] * 100, 2) if summary["totalInvested"] else 0
    return {"holdings": holdings, "summary": summary}


@router.get("/portfolio")
def portfolio(auth: bool = Depends(verify_api_key)):
    return _enrich_holdings()


@router.post("/portfolio")
def add_portfolio_holding(request: HoldingRequest, auth: bool = Depends(verify_api_key)):
    holding = add_holding(request.symbol, request.quantity, request.buy_price)
    return holding


@router.delete("/portfolio/{symbol}")
def remove_portfolio_holding(symbol: str, auth: bool = Depends(verify_api_key)):
    removed = remove_holding(symbol)
    if not removed:
        raise HTTPException(status_code=404, detail="Holding not found")
    return {"message": f"Removed {symbol} from portfolio"}


@router.post("/portfolio/{symbol}/sell")
def sell_portfolio_holding(symbol: str, request: SellRequest, auth: bool = Depends(verify_api_key)):
    result = sell_holding(symbol, request.quantity, request.price)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/portfolio/realized")
def portfolio_realized(auth: bool = Depends(verify_api_key)):
    trades = get_realized_trades()
    total = round(sum(t.get("realizedPnl") or 0 for t in trades), 2)
    trades_sorted = sorted(trades, key=lambda t: t.get("soldAt") or "", reverse=True)
    return {"trades": trades_sorted, "totalRealizedPnl": total, "tradeCount": len(trades)}


@router.get("/portfolio/dividends")
def portfolio_dividends(auth: bool = Depends(verify_api_key)):
    return get_dividend_records()


@router.get("/portfolio/benchmark")
def portfolio_benchmark(period: str = "1Y", auth: bool = Depends(verify_api_key)):
    from core.portfolio_analytics import get_portfolio_benchmark
    result = get_portfolio_benchmark(period)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/portfolio/events")
def portfolio_events(auth: bool = Depends(verify_api_key)):
    """Auto-detected dividend / split / bonus suggestions for held stocks."""
    from core.portfolio_events import get_portfolio_event_suggestions
    return get_portfolio_event_suggestions()


@router.post("/portfolio/events/{event_id}/dismiss")
def dismiss_portfolio_event(event_id: str, auth: bool = Depends(verify_api_key)):
    from core.portfolio_events import dismiss_event
    result = dismiss_event(event_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/portfolio/{symbol}/dividend")
def add_dividend_endpoint(symbol: str, request: DividendRequest, auth: bool = Depends(verify_api_key)):
    result = add_dividend(symbol, request.amount, request.date, request.note or "")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/portfolio/{symbol}/corp-action")
def corp_action_endpoint(symbol: str, request: CorpActionRequest, auth: bool = Depends(verify_api_key)):
    result = apply_corp_action(symbol, request.ratio, request.type, request.date)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/watchlist")
def watchlist(auth: bool = Depends(verify_api_key)):
    symbols = get_watchlist()
    for item in symbols:
        price_data = get_live_price(item["symbol"])
        if price_data:
            item["price"] = price_data["price"]
            item["change"] = round(price_data["price"] - price_data["previousClose"], 2)
            item["changePercent"] = round((price_data["price"] - price_data["previousClose"]) / price_data["previousClose"] * 100, 2)
    return {"watchlist": symbols}


@router.post("/watchlist")
def add_to_watchlist_endpoint(request: WatchlistRequest, auth: bool = Depends(verify_api_key)):
    item = add_to_watchlist(request.symbol, request.name)
    return item


@router.delete("/watchlist/{symbol}")
def remove_from_watchlist_endpoint(symbol: str, auth: bool = Depends(verify_api_key)):
    removed = remove_from_watchlist(symbol)
    if not removed:
        raise HTTPException(status_code=404, detail="Symbol not found in watchlist")
    return {"message": f"Removed {symbol} from watchlist"}


@router.get("/portfolio/live-pnl")
def portfolio_live_pnl(auth: bool = Depends(verify_api_key)):
    return _enrich_holdings()
