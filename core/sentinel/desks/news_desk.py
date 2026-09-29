from typing import List, Dict, Any
import yfinance as yf
from datetime import datetime
from core.sentinel.types import DeskFinding
from core.ai_analysis import analyze_sentiment

class NewsDesk:
    @staticmethod
    def scan(symbol: str) -> List[DeskFinding]:
        findings = []
        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news
            if news:
                return NewsDesk.scan_text(symbol, news[:5])
        except Exception:
            pass
        return findings

    @staticmethod
    def scan_text(symbol: str, raw_news: List[Dict[str, Any]]) -> List[DeskFinding]:
        findings = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for item in raw_news:
            title = item.get("title", "")
            publisher = item.get("publisher", "Exchange/News")
            if not title:
                continue
            sentiment = analyze_sentiment(title)
            if sentiment["score"] > 0.65 or sentiment["score"] < 0.35:
                significance = "HIGH" if (sentiment["score"] > 0.8 or sentiment["score"] < 0.2) else "MEDIUM"
                findings.append(DeskFinding(
                    desk="NEWS",
                    symbol=symbol,
                    headline=f"[{publisher}] {title}",
                    metrics={
                        "sentiment": sentiment["label"],
                        "sentiment_score": sentiment["score"],
                        "publisher": publisher
                    },
                    significance=significance,
                    timestamp=now_str
                ))
        return findings
