from typing import Optional
import pandas as pd
from core.portfolio import get_portfolio
from core.data_fetcher import get_live_price, SECTOR_MAP
from core import upstox_data


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
        
        # Use the same price path as /api/portfolio (get_live_price) so the
        # analytics summary always matches the holdings table.
        price_data = get_live_price(symbol)
        if price_data:
            current_price = price_data["price"]
            prev_close = price_data.get("previousClose") or current_price
        else:
            current_price = buy_price
            prev_close = current_price
        day_pnl = (current_price - prev_close) * qty
        
        invested = buy_price * qty
        current_value = current_price * qty
        pnl = current_value - invested
        return_pct = ((current_value - invested) / invested) * 100 if invested > 0 else 0
        
        total_invested += invested
        total_current += current_value
        
        # Sector: static map first (instant), then Downstox fundamentals.
        ticker = symbol.replace(".NS", "")
        sector = SECTOR_MAP.get(symbol)
        if not sector:
            sector = upstox_data.get_stock_profile(symbol).get("sector") or "Others"

        # Display name: Upstox master (short → full), Downstox fallback.
        name = upstox_data.instrument_display_name(symbol) or ticker
        
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
            "returnPercent": round(return_pct, 2),
            "dayChangePnl": round(day_pnl, 2)
        })
    
    # Disambiguate holdings sharing a display name (e.g. Tata Motors demerged
    # into TMCV + TMPV) so performer lists aren't confusing.
    name_counts = {}
    for row in stock_returns:
        name_counts[row["name"]] = name_counts.get(row["name"], 0) + 1
    for row in stock_returns:
        if name_counts[row["name"]] > 1:
            row["name"] = f'{row["name"]} ({row["symbol"].replace(".NS", "")})'

    # Convert sector allocation to percentage
    sector_pct = {}
    for sector, value in sector_allocation.items():
        sector_pct[sector] = round((value / total_current) * 100, 2)
    
    # Sort by value
    stock_returns.sort(key=lambda x: x["currentValue"], reverse=True)
    
    total_pnl = total_current - total_invested
    total_return = ((total_current - total_invested) / total_invested) * 100 if total_invested > 0 else 0
    total_day_pnl = sum(r["dayChangePnl"] for r in stock_returns)

    return {
        "summary": {
            "totalInvested": round(total_invested, 2),
            "totalCurrentValue": round(total_current, 2),
            "totalPnL": round(total_pnl, 2),
            "totalReturn": round(total_return, 2),
            "totalDayPnl": round(total_day_pnl, 2),
            "holdingCount": len(holdings)
        },
        "holdings": stock_returns,
        "sectorAllocation": sector_pct,
        # A "top performer" must actually be profitable and a "worst
        # performer" must actually be losing money, so a single profitable
        # holding doesn't appear under both headings.
        "topPerformers": [s for s in sorted(stock_returns, key=lambda x: x["returnPercent"], reverse=True) if s["returnPercent"] > 0][:3],
        "worstPerformers": [s for s in sorted(stock_returns, key=lambda x: x["returnPercent"]) if s["returnPercent"] < 0][:3]
    }


# ---------------------------------------------------------------------------
# #7 Benchmark comparison — portfolio vs NIFTY 50 (buy-and-hold, normalized)
# ---------------------------------------------------------------------------

# period label -> (period string accepted by get_stock_data, label)
_BENCH_PERIODS = {
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "1Y": "1y",
    "ALL": "max",
}


def get_portfolio_benchmark(period: str = "1Y") -> dict:
    """Compare the portfolio against NIFTY 50 over a period.

    Both series are buy-and-hold and normalized to 100 at the start:
    each holding contributes its current market-value weight, grown from its
    first available close in the window (graceful for recently bought /
    newly listed stocks). Never mutates the portfolio.
    """
    period_key = (period or "1Y").upper()
    data_period = _BENCH_PERIODS.get(period_key)
    if not data_period:
        return {"error": "Period must be one of 1M, 3M, 6M, 1Y, ALL"}

    holdings = get_portfolio()
    if not holdings:
        return {"error": "No holdings in portfolio"}

    nifty = upstox_data.get_stock_data("^NSEI", period=data_period, interval="1d")
    if nifty is None or nifty.empty:
        return {"error": "Could not fetch NIFTY 50 data"}

    # Master axis: the index's trading days.
    nifty_closes = nifty["Close"].astype(float)
    dates = list(nifty_closes.index)
    bench_growth = nifty_closes / float(nifty_closes.iloc[0])

    # Current market value per holding = weight basis.
    values = []
    for holding in holdings:
        symbol = holding["symbol"]
        qty = holding.get("quantity", 0) or 0
        last_close = None
        frame = upstox_data.get_stock_data(symbol, period=data_period, interval="1d")
        if frame is not None and not frame.empty:
            last_close = float(frame["Close"].iloc[-1])
        if last_close is None:
            last_close = float(holding.get("buyPrice", 0) or 0)
        values.append(last_close * qty)

    total_value = sum(values)
    if total_value <= 0:
        return {"error": "Portfolio has no measurable value"}

    portfolio_growth = pd.Series(0.0, index=nifty_closes.index)
    used = 0.0
    stock_series = []
    for holding, value in zip(holdings, values):
        weight = value / total_value
        if weight <= 0:
            continue
        symbol = holding["symbol"]
        frame = upstox_data.get_stock_data(symbol, period=data_period, interval="1d")
        if frame is None or frame.empty:
            stock_series.append({"symbol": symbol, "weight": round(weight * 100, 2), "included": False})
            continue
        closes = frame["Close"].astype(float).reindex(nifty_closes.index).ffill().bfill()
        if closes.isna().all() or float(closes.iloc[0]) <= 0:
            stock_series.append({"symbol": symbol, "weight": round(weight * 100, 2), "included": False})
            continue
        growth = closes / float(closes.iloc[0])
        portfolio_growth = portfolio_growth.add(growth * weight)
        used += weight
        stock_series.append({
            "symbol": symbol,
            "weight": round(weight * 100, 2),
            "included": True,
            "firstDate": str(frame.index[0]),
            "return": round((float(closes.iloc[-1]) / float(closes.iloc[0]) - 1) * 100, 2),
        })

    # Weights of stocks without data are folded into the benchmark so the
    # chart still represents 100% of the portfolio.
    missing_weight = 1.0 - used
    if missing_weight > 0.0001:
        portfolio_growth = portfolio_growth.add(bench_growth * missing_weight)

    return {
        "period": period_key,
        "benchmark": "NIFTY 50",
        "dates": dates,
        "portfolioSeries": [round(float(v), 3) for v in portfolio_growth],
        "benchmarkSeries": [round(float(v), 3) for v in bench_growth],
        "portfolioReturn": round((float(portfolio_growth.iloc[-1]) - 1) * 100, 2),
        "benchmarkReturn": round((float(bench_growth.iloc[-1]) - 1) * 100, 2),
        "stocks": stock_series,
    }
