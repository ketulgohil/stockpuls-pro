from fastapi import APIRouter
from typing import List
from core.data_fetcher import get_stock_data, get_stock_info
from core.indicators import add_all_indicators, get_latest_indicators

router = APIRouter(prefix="/api/compare", tags=["compare"])


@router.get("")
def compare_stocks(symbols: str = "RELIANCE.NS,TCS.NS,HDFCBANK.NS"):
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    
    if len(symbol_list) < 2:
        return {"error": "Please provide at least 2 symbols"}
    
    if len(symbol_list) > 5:
        symbol_list = symbol_list[:5]
    
    results = []
    for symbol in symbol_list:
        try:
            info = get_stock_info(symbol)
            df = get_stock_data(symbol, period="6mo")
            
            if df is None or df.empty:
                continue
            
            df = add_all_indicators(df)
            indicators = get_latest_indicators(df)
            
            price_6mo_ago = float(df["Close"].iloc[0])
            price_now = float(df["Close"].iloc[-1])
            returns_6mo = ((price_now - price_6mo_ago) / price_6mo_ago) * 100
            
            high_52w = float(df["High"].max())
            low_52w = float(df["Low"].min())
            
            results.append({
                "symbol": symbol,
                "name": info.get("name", symbol.replace(".NS", "")) if info else symbol.replace(".NS", ""),
                "sector": info.get("sector", "Unknown") if info else "Unknown",
                "price": indicators.get("close"),
                "change": indicators.get("change"),
                "changePercent": indicators.get("changePercent"),
                "rsi": indicators.get("RSI"),
                "macd": indicators.get("MACD"),
                "sma20": indicators.get("SMA_20"),
                "sma50": indicators.get("SMA_50"),
                "pe": info.get("pe") if info else None,
                "marketCap": info.get("marketCap") if info else None,
                "returns6Month": round(returns_6mo, 2),
                "high6Month": round(high_52w, 2),
                "low6Month": round(low_52w, 2)
            })
        except Exception as e:
            print(f"Error comparing {symbol}: {e}")
            continue
    
    return {"stocks": results, "count": len(results)}
