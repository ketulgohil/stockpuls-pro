from core import upstox_data


def _map_news_item(item: dict) -> dict:
    """Map an Upstox/Downstox news item to the legacy output shape."""
    return {
        "title": item.get("title") or "No title",
        "summary": item.get("summary") or "No summary",
        "link": item.get("link") or "#",
        "source": item.get("publisher") or "Unknown",
        "published": item.get("publishedAt") or "",
        "thumbnail": "",
    }


def get_stock_news(symbol: str, limit: int = 10) -> list[dict]:
    try:
        # Market-wide requests arrive here with no symbol / a market marker.
        if not symbol or str(symbol).strip().lower() in {"market", "none", "^nsei", "^bsesn"}:
            return [
                {
                    "title": item.get("title") or "No title",
                    "summary": item.get("summary") or "No summary",
                    "link": item.get("link") or "#",
                    "source": item.get("publisher") or "Unknown",
                    "published": item.get("publishedAt") or "",
                    "thumbnail": "",
                }
                for item in upstox_data.get_market_news(limit=limit)
            ]

        news = upstox_data.get_instrument_news(symbol, limit=limit) or []
        return [_map_news_item(item) for item in news[:limit]]
    except Exception as e:
        print(f"Error fetching news for {symbol}: {e}")
        return []


def get_market_news(limit: int = 20) -> list[dict]:
    try:
        news = upstox_data.get_market_news(limit=limit) or []
        results = []
        for item in news[:limit]:
            results.append({
                "title": item.get("title") or "No title",
                "summary": item.get("summary") or "No summary",
                "link": item.get("link") or "#",
                "source": item.get("publisher") or "Unknown",
                "published": item.get("publishedAt") or "",
                "relatedSymbol": "",
            })
        return results
    except Exception as e:
        print(f"Error fetching market news: {e}")
        return []
