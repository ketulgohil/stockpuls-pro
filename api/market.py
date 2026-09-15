import yfinance as yf
from fastapi import APIRouter

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("")
def market_overview():
    indices = {
        "^NSEI": {"name": "NIFTY 50", "exchange": "NSE"},
        "^BSESN": {"name": "SENSEX", "exchange": "BSE"},
        "^NSEBANK": {"name": "NIFTY Bank", "exchange": "NSE"},
        "^NSEIT": {"name": "NIFTY IT", "exchange": "NSE"},
        "^CNXMCAP": {"name": "NIFTY Midcap", "exchange": "NSE"},
    }
    
    results = []
    for symbol, info in indices.items():
        try:
            ticker = yf.Ticker(symbol)
            fast = ticker.fast_info
            hist = ticker.history(period="5d")
            
            if len(hist) >= 2:
                prev_close = hist["Close"].iloc[-2]
                current = hist["Close"].iloc[-1]
                change = current - prev_close
                change_pct = (change / prev_close) * 100
            else:
                current = fast.last_price
                change = 0
                change_pct = 0
            
            results.append({
                "symbol": symbol,
                "name": info["name"],
                "exchange": info["exchange"],
                "price": round(float(current), 2),
                "change": round(float(change), 2),
                "changePercent": round(float(change_pct), 2),
                "dayHigh": round(float(fast.day_high), 2) if fast.day_high else None,
                "dayLow": round(float(fast.day_low), 2) if fast.day_low else None,
                "previousClose": round(float(fast.previous_close), 2) if fast.previous_close else None
            })
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            continue
    
    return {"indices": results}


@router.get("/top-gainers")
def top_gainers():
    from core.data_fetcher import ALL_SYMBOLS
    symbols = ALL_SYMBOLS[:50]
    
    stocks = []
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            if len(hist) >= 2:
                prev = hist["Close"].iloc[-2]
                curr = hist["Close"].iloc[-1]
                change_pct = ((curr - prev) / prev) * 100
                stocks.append({
                    "symbol": symbol,
                    "name": symbol.replace(".NS", ""),
                    "price": round(float(curr), 2),
                    "changePercent": round(float(change_pct), 2)
                })
        except:
            continue
    
    stocks.sort(key=lambda x: x["changePercent"], reverse=True)
    return {"gainers": stocks[:10]}


@router.get("/top-losers")
def top_losers():
    from core.data_fetcher import ALL_SYMBOLS
    symbols = ALL_SYMBOLS[:50]
    
    stocks = []
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            if len(hist) >= 2:
                prev = hist["Close"].iloc[-2]
                curr = hist["Close"].iloc[-1]
                change_pct = ((curr - prev) / prev) * 100
                stocks.append({
                    "symbol": symbol,
                    "name": symbol.replace(".NS", ""),
                    "price": round(float(curr), 2),
                    "changePercent": round(float(change_pct), 2)
                })
        except:
            continue
    
    stocks.sort(key=lambda x: x["changePercent"])
    return {"losers": stocks[:10]}
