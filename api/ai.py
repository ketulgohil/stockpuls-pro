from fastapi import APIRouter
from core.ai_analysis import (
    get_news_sentiment_analysis,
    find_trending_stocks_news,
    get_market_mood,
    ai_stock_analysis
)

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/sentiment/{symbol}")
def sentiment_analysis(symbol: str):
    result = get_news_sentiment_analysis(symbol)
    return result


@router.get("/trending")
def trending_stocks():
    result = find_trending_stocks_news()
    return {"trending": result, "count": len(result)}


@router.get("/mood")
def market_mood():
    result = get_market_mood()
    return result


@router.get("/analyze/{symbol}")
def full_analysis(symbol: str):
    result = ai_stock_analysis(symbol)
    return result
