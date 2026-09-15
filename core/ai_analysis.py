import yfinance as yf
from typing import Optional
from core.data_fetcher import get_stock_data, ALL_SYMBOLS
from core.indicators import add_all_indicators
import re


POSITIVE_WORDS = [
    "surge", "rally", "gain", "rise", "profit", "growth", "bullish", "upgrade",
    "outperform", "beat", "strong", "boost", "jump", "soar", "record high",
    "buy", "accumulate", "expansion", "revenue up", "positive", "recovery",
    "breakout", "momentum", "upgrade", "target raise", "dividend", "bonus"
]

NEGATIVE_WORDS = [
    "crash", "fall", "drop", "decline", "loss", "bearish", "downgrade",
    "underperform", "miss", "weak", "slump", "plunge", "sell", "panic",
    "recession", "debt", "default", "fraud", "investigation", "warning",
    "breakdown", "resistance", "downgrade", "target cut", "layoff", "recall"
]


def analyze_sentiment(text: str) -> dict:
    text_lower = text.lower()
    
    pos_count = sum(1 for w in POSITIVE_WORDS if w in text_lower)
    neg_count = sum(1 for w in NEGATIVE_WORDS if w in text_lower)
    
    total = pos_count + neg_count
    if total == 0:
        score = 0.5
    else:
        score = pos_count / total
    
    if score > 0.6:
        label = "BULLISH"
    elif score < 0.4:
        label = "BEARISH"
    else:
        label = "NEUTRAL"
    
    return {
        "score": round(score, 2),
        "label": label,
        "positive_hits": pos_count,
        "negative_hits": neg_count
    }


def get_news_sentiment_analysis(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news
        
        if not news:
            return {"symbol": symbol, "news": [], "sentiment": None, "recommendation": "NO_DATA"}
        
        analyzed_news = []
        all_sentiments = []
        
        for item in news[:15]:
            title = item.get("title", "")
            publisher = item.get("publisher", "")
            summary = item.get("summary", "")
            
            combined_text = f"{title} {summary}"
            sentiment = analyze_sentiment(combined_text)
            
            analyzed_news.append({
                "title": title,
                "publisher": publisher,
                "link": item.get("link", ""),
                "published": item.get("providerPublishTime", ""),
                "sentiment": sentiment["label"],
                "sentiment_score": sentiment["score"]
            })
            all_sentiments.append(sentiment["score"])
        
        avg_score = sum(all_sentiments) / len(all_sentiments) if all_sentiments else 0.5
        
        if avg_score > 0.65:
            recommendation = "BUY"
            reasoning = "Strong positive news sentiment"
        elif avg_score > 0.55:
            recommendation = "MODERATE_BUY"
            reasoning = "Moderately positive news sentiment"
        elif avg_score < 0.35:
            recommendation = "SELL"
            reasoning = "Strong negative news sentiment"
        elif avg_score < 0.45:
            recommendation = "MODERATE_SELL"
            reasoning = "Moderately negative news sentiment"
        else:
            recommendation = "HOLD"
            reasoning = "Neutral news sentiment"
        
        return {
            "symbol": symbol,
            "name": symbol.replace(".NS", ""),
            "news_count": len(analyzed_news),
            "news": analyzed_news,
            "sentiment": {
                "average_score": round(avg_score, 2),
                "label": "BULLISH" if avg_score > 0.6 else "BEARISH" if avg_score < 0.4 else "NEUTRAL",
                "positive_count": sum(1 for s in all_sentiments if s > 0.6),
                "negative_count": sum(1 for s in all_sentiments if s < 0.4),
                "neutral_count": sum(1 for s in all_sentiments if 0.4 <= s <= 0.6)
            },
            "recommendation": recommendation,
            "reasoning": reasoning
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


def find_trending_stocks_news() -> list[dict]:
    from core.data_fetcher import ALL_SYMBOLS
    hot_stocks = ALL_SYMBOLS[:30]
    
    results = []
    
    for symbol in hot_stocks:
        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news
            
            if news and len(news) > 0:
                sentiment_scores = []
                headlines = []
                
                for item in news[:5]:
                    title = item.get("title", "")
                    headlines.append(title)
                    sentiment = analyze_sentiment(title)
                    sentiment_scores.append(sentiment["score"])
                
                avg = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.5
                
                results.append({
                    "symbol": symbol,
                    "name": symbol.replace(".NS", ""),
                    "news_count": len(news),
                    "headlines": headlines[:3],
                    "sentiment_score": round(avg, 2),
                    "sentiment": "BULLISH" if avg > 0.6 else "BEARISH" if avg < 0.4 else "NEUTRAL"
                })
        except:
            continue
    
    results.sort(key=lambda x: x["news_count"], reverse=True)
    return results[:15]


def get_market_mood() -> dict:
    indices_data = []
    try:
        for symbol in ["^NSEI", "^BSESN"]:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            if len(hist) >= 2:
                change = ((hist["Close"].iloc[-1] - hist["Close"].iloc[-2]) / hist["Close"].iloc[-2]) * 100
                indices_data.append({"symbol": symbol, "change": round(float(change), 2)})
    except:
        pass
    
    trending = find_trending_stocks_news()[:10]
    bullish = sum(1 for s in trending if s["sentiment"] == "BULLISH")
    bearish = sum(1 for s in trending if s["sentiment"] == "BEARISH")
    
    if bullish > bearish * 1.5:
        mood = "BULLISH"
    elif bearish > bullish * 1.5:
        mood = "BEARISH"
    else:
        mood = "NEUTRAL"
    
    return {
        "mood": mood,
        "indices": indices_data,
        "trending_bullish": bullish,
        "trending_bearish": bearish,
        "trending_stocks": trending[:5]
    }


def ai_stock_analysis(symbol: str) -> dict:
    try:
        sentiment_data = get_news_sentiment_analysis(symbol)
        
        df = get_stock_data(symbol, period="3mo")
        technical = {}
        if df is not None and not df.empty:
            df = add_all_indicators(df)
            latest = df.iloc[-1]
            technical = {
                "price": round(float(latest["Close"]), 2),
                "rsi": round(float(latest["RSI"]), 2) if not latest.get("RSI") != latest.get("RSI") else None,
                "macd": round(float(latest["MACD"]), 2) if not latest.get("MACD") != latest.get("MACD") else None,
                "sma20": round(float(latest["SMA_20"]), 2) if not latest.get("SMA_20") != latest.get("SMA_20") else None,
                "sma50": round(float(latest["SMA_50"]), 2) if not latest.get("SMA_50") != latest.get("SMA_50") else None,
                "trend": "BULLISH" if latest.get("SMA_20", 0) > latest.get("SMA_50", 0) else "BEARISH"
            }
        
        news_score = sentiment_data.get("sentiment", {}).get("average_score", 0.5) if sentiment_data.get("sentiment") else 0.5
        tech_score = 0.5
        if technical:
            rsi = technical.get("rsi", 50)
            if rsi and rsi < 30:
                tech_score = 0.7
            elif rsi and rsi > 70:
                tech_score = 0.3
            elif technical.get("trend") == "BULLISH":
                tech_score = 0.6
            else:
                tech_score = 0.4
        
        combined_score = (news_score * 0.4 + tech_score * 0.6)
        
        if combined_score > 0.65:
            recommendation = "STRONG BUY"
        elif combined_score > 0.55:
            recommendation = "BUY"
        elif combined_score < 0.35:
            recommendation = "STRONG SELL"
        elif combined_score < 0.45:
            recommendation = "SELL"
        else:
            recommendation = "HOLD"
        
        return {
            "symbol": symbol,
            "name": symbol.replace(".NS", ""),
            "technical": technical,
            "news_sentiment": sentiment_data.get("sentiment"),
            "news_count": sentiment_data.get("news_count", 0),
            "top_headlines": [n["title"] for n in sentiment_data.get("news", [])[:3]],
            "combined_score": round(combined_score, 2),
            "recommendation": recommendation,
            "reasoning": {
                "news": sentiment_data.get("reasoning", "No data"),
                "technical": f"RSI: {technical.get('rsi', '-')}, Trend: {technical.get('trend', '-')}"
            }
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}
