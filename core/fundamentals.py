import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional


def get_earnings_calendar(days: int = 30) -> list[dict]:
    from core.data_fetcher import NIFTY50_SYMBOLS
    symbols = NIFTY50_SYMBOLS
    
    earnings = []
    
    for symbol in symbols[:20]:
        try:
            ticker = yf.Ticker(symbol)
            cal = ticker.calendar
            
            if cal is not None and not (isinstance(cal, float) and cal != cal):
                if isinstance(cal, dict):
                    earnings_date = cal.get("Earnings Date")
                    if earnings_date:
                        for date in earnings_date:
                            try:
                                if hasattr(date, 'date'):
                                    date_obj = date.date()
                                else:
                                    date_obj = date
                                if isinstance(date_obj, str):
                                    date_obj = datetime.strptime(date_obj, "%Y-%m-%d")
                                earnings.append({
                                    "symbol": symbol,
                                    "name": symbol.replace(".NS", ""),
                                    "date": date_obj.strftime("%Y-%m-%d"),
                                    "daysUntil": "Check manually"
                                })
                                break
                            except Exception:
                                continue
        except Exception:
            continue
    
    return earnings


def get_dividend_stocks() -> list[dict]:
    from core.data_fetcher import NIFTY50_SYMBOLS
    symbols = NIFTY50_SYMBOLS
    
    dividend_stocks = []
    
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            div_yield = info.get("dividendYield")
            div_rate = info.get("dividendRate")
            
            if div_yield and div_yield > 0:
                dividend_stocks.append({
                    "symbol": symbol,
                    "name": symbol.replace(".NS", ""),
                    "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                    "dividendYield": round(div_yield * 100, 2),
                    "dividendRate": div_rate,
                    "payoutRatio": info.get("payoutRatio"),
                    "exDividendDate": info.get("exDividendDate"),
                    "sector": info.get("sector", "Unknown")
                })
        except:
            continue
    
    dividend_stocks.sort(key=lambda x: x.get("dividendYield", 0), reverse=True)
    return dividend_stocks


def get_fii_dii_data() -> dict:
    try:
        symbols = ["^NSEI", "^BSESN"]
        market_data = {}
        
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1mo")
                if not hist.empty:
                    market_data[symbol] = {
                        "current": round(float(hist["Close"].iloc[-1]), 2),
                        "monthHigh": round(float(hist["High"].max()), 2),
                        "monthLow": round(float(hist["Low"].min()), 2),
                        "avgVolume": int(hist["Volume"].mean())
                    }
            except:
                continue
        
        return {
            "note": "FII/DII actual data requires NSE API or paid data source",
            "marketData": market_data,
            "suggestion": "Check moneycontrol.com for real-time FII/DII data"
        }
    except Exception as e:
        return {"error": str(e)}
