from fastapi import APIRouter, HTTPException
from core.news import get_stock_news, get_market_news

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("")
def market_news(limit: int = 20):
    news = get_market_news(limit)
    return {"news": news, "count": len(news)}


@router.get("/{symbol}")
def stock_news(symbol: str, limit: int = 10):
    news = get_stock_news(symbol, limit)
    return {"symbol": symbol, "news": news, "count": len(news)}
