from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.data_fetcher import get_sector_data, get_sector_stocks, get_stock_data, get_stock_info, ALL_SYMBOLS
from core.indicators import add_all_indicators, get_latest_indicators

router = APIRouter(prefix="/api/sector", tags=["sector"])


@router.get("")
def list_sectors():
    sectors = get_sector_data()
    result = []
    for sector, stocks in sectors.items():
        result.append({
            "name": sector,
            "stockCount": len(stocks),
            "symbols": stocks[:5]
        })
    return sorted(result, key=lambda x: x["stockCount"], reverse=True)


@router.get("/{sector}")
def sector_detail(sector: str):
    stocks = get_sector_stocks(sector)
    if not stocks:
        raise HTTPException(status_code=404, detail=f"Sector {sector} not found")

    results = []
    for stock in stocks[:10]:
        try:
            info = get_stock_info(stock["symbol"])
            if info:
                results.append({
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "price": info.get("currentPrice"),
                    "pe": info.get("pe"),
                    "marketCap": info.get("marketCap"),
                    "sector": sector
                })
        except:
            continue

    return {
        "sector": sector,
        "stocks": results,
        "totalStocks": len(stocks)
    }
