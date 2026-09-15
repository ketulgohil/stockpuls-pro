from fastapi import APIRouter, Query
from typing import Optional
import csv
import io
from fastapi.responses import StreamingResponse
from core.data_fetcher import get_stock_list, get_stock_data
from core.indicators import add_all_indicators

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/csv")
def export_screener_csv(
    rsi_below: Optional[float] = None,
    rsi_above: Optional[float] = None,
    format: str = "csv"
):
    from core.screener import screen_stocks
    
    results = screen_stocks(
        rsi_below=rsi_below,
        rsi_above=rsi_above,
        limit=50
    )
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Symbol", "Name", "Price", "Change%", "RSI", "MACD", "Volume"])
    
    for stock in results:
        writer.writerow([
            stock["symbol"],
            stock["name"],
            stock["price"],
            stock["changePercent"],
            stock.get("rsi", ""),
            stock.get("macd", ""),
            stock["volume"]
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=screener_results.csv"}
    )


@router.get("/portfolio/csv")
def export_portfolio_csv():
    from core.portfolio import get_portfolio
    
    holdings = get_portfolio()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Symbol", "Quantity", "Buy Price", "Buy Date"])
    
    for h in holdings:
        writer.writerow([
            h["symbol"],
            h["quantity"],
            h["buyPrice"],
            h.get("buyDate", "")
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=portfolio.csv"}
    )
