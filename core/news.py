import yfinance as yf
from typing import Optional
from datetime import datetime


def get_stock_news(symbol: str, limit: int = 10) -> list[dict]:
    try:
        if not symbol.endswith(".NS"):
            symbol = symbol + ".NS"
        
        ticker = yf.Ticker(symbol)
        news = ticker.news
        
        if not news:
            return []
        
        results = []
        for item in news[:limit]:
            content = item.get("content", {})
            pub_date = content.get("pubDate", "")
            
            results.append({
                "title": content.get("title", "No title"),
                "summary": content.get("summary", "No summary"),
                "link": content.get("clickThroughUrl", {}).get("url", "#"),
                "source": content.get("provider", {}).get("displayName", "Unknown"),
                "published": pub_date,
                "thumbnail": content.get("thumbnail", {}).get("resolutions", [{}])[0].get("url", "") if content.get("thumbnail") else ""
            })
        
        return results
    except Exception as e:
        print(f"Error fetching news for {symbol}: {e}")
        return []


def get_market_news(limit: int = 20) -> list[dict]:
    try:
        from core.data_fetcher import NIFTY50_SYMBOLS
        symbols = ["^NSEI", "^BSESN"] + NIFTY50_SYMBOLS[:5]
        all_news = []
        
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                news = ticker.news
                if news:
                    for item in news[:5]:
                        content = item.get("content", {})
                        title = content.get("title", "")
                        if title and title not in [n.get("title") for n in all_news]:
                            all_news.append({
                                "title": title,
                                "summary": content.get("summary", ""),
                                "link": content.get("clickThroughUrl", {}).get("url", "#"),
                                "source": content.get("provider", {}).get("displayName", "Unknown"),
                                "published": content.get("pubDate", ""),
                                "relatedSymbol": symbol.replace(".NS", "").replace("^", "")
                            })
            except:
                continue
        
        return all_news[:limit]
    except Exception as e:
        print(f"Error fetching market news: {e}")
        return []
