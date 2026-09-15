import yfinance as yf
from typing import Optional
from core.portfolio import get_portfolio
from core.data_fetcher import get_stock_info, SECTOR_MAP


def get_portfolio_analytics() -> dict:
    holdings = get_portfolio()
    
    if not holdings:
        return {"error": "No holdings in portfolio"}
    
    total_invested = 0
    total_current = 0
    sector_allocation = {}
    stock_returns = []
    
    for holding in holdings:
        symbol = holding["symbol"]
        qty = holding["quantity"]
        buy_price = holding["buyPrice"]
        
        try:
            info = get_stock_info(symbol)
            current_price = info.get("currentPrice", buy_price) if info else buy_price
        except:
            current_price = buy_price
        
        invested = buy_price * qty
        current_value = current_price * qty
        pnl = current_value - invested
        return_pct = ((current_value - invested) / invested) * 100 if invested > 0 else 0
        
        total_invested += invested
        total_current += current_value
        
        # Find sector
        sector = "Others"
        name = symbol.replace(".NS", "")
        for s, members in SECTOR_MAP.items():
            if name in members:
                sector = s
                break
        
        if sector not in sector_allocation:
            sector_allocation[sector] = 0
        sector_allocation[sector] += current_value
        
        stock_returns.append({
            "symbol": symbol,
            "name": name,
            "buyPrice": buy_price,
            "currentPrice": current_price,
            "quantity": qty,
            "invested": round(invested, 2),
            "currentValue": round(current_value, 2),
            "pnl": round(pnl, 2),
            "returnPercent": round(return_pct, 2)
        })
    
    # Convert sector allocation to percentage
    sector_pct = {}
    for sector, value in sector_allocation.items():
        sector_pct[sector] = round((value / total_current) * 100, 2)
    
    # Sort by value
    stock_returns.sort(key=lambda x: x["currentValue"], reverse=True)
    
    total_pnl = total_current - total_invested
    total_return = ((total_current - total_invested) / total_invested) * 100 if total_invested > 0 else 0
    
    return {
        "summary": {
            "totalInvested": round(total_invested, 2),
            "totalCurrentValue": round(total_current, 2),
            "totalPnL": round(total_pnl, 2),
            "totalReturn": round(total_return, 2),
            "holdingCount": len(holdings)
        },
        "holdings": stock_returns,
        "sectorAllocation": sector_pct,
        "topPerformers": sorted(stock_returns, key=lambda x: x["returnPercent"], reverse=True)[:3],
        "worstPerformers": sorted(stock_returns, key=lambda x: x["returnPercent"])[:3]
    }
