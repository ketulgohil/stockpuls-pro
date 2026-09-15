from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from core.data_fetcher import get_stock_list, get_stock_data, get_stock_info, get_live_price, search_stocks
from core.indicators import add_all_indicators, get_latest_indicators, calculate_support_resistance

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("")
def list_stocks():
    return get_stock_list()


@router.get("/search")
def search(query: str = Query(..., min_length=1)):
    return search_stocks(query)


@router.get("/{symbol}")
def stock_detail(symbol: str):
    info = get_stock_info(symbol)
    if not info:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
    return info


@router.get("/{symbol}/history")
def stock_history(
    symbol: str,
    period: str = Query(default="6mo", pattern="^(1d|5d|1mo|3mo|6mo|1y|2y|5y)$"),
    interval: str = Query(default="1d", pattern="^(1d|1wk|1mo)$")
):
    df = get_stock_data(symbol, period=period, interval=interval)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

    df = add_all_indicators(df)

    data = []
    for date, row in df.iterrows():
        point = {
            "date": date,
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]),
        }
        for col in ["SMA_20", "SMA_50", "SMA_200", "BB_Upper", "BB_Lower", "RSI", "MACD", "MACD_Signal"]:
            if col in row.index and not df[col].isna().all():
                point[col.lower()] = round(float(row[col]), 2) if not row[col] != row[col] else None
            else:
                point[col.lower()] = None
        data.append(point)

    return {"symbol": symbol, "data": data}


@router.get("/{symbol}/analyze")
def stock_analysis(symbol: str):
    df = get_stock_data(symbol, period="6mo")
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

    df = add_all_indicators(df)
    indicators = get_latest_indicators(df)
    sr_levels = calculate_support_resistance(df)
    info = get_stock_info(symbol)

    return {
        "symbol": symbol,
        "info": info,
        "indicators": indicators,
        "supportResistance": sr_levels
    }


@router.get("/{symbol}/live")
def stock_live(symbol: str):
    price = get_live_price(symbol)
    if not price:
        raise HTTPException(status_code=404, detail=f"No live price for {symbol}")
    return price
