from core.data_fetcher import get_stock_data, get_stock_info, ALL_SYMBOLS


STRATEGIES = {
    "value_investing": {
        "name": "Value Investing",
        "description": "Find undervalued stocks with low P/E, low P/B, high dividend yield",
        "filters": {
            "pe_max": 15,
            "pb_max": 2,
            "dividend_yield_min": 1.5
        }
    },
    "growth_stocks": {
        "name": "Growth Stocks",
        "description": "Find high growth stocks with strong earnings and revenue growth",
        "filters": {
            "earnings_growth_min": 15,
            "revenue_growth_min": 10,
            "profit_margin_min": 10
        }
    },
    "momentum": {
        "name": "Momentum",
        "description": "Stocks with strong upward momentum, RSI > 50, trading above SMA20",
        "filters": {
            "rsi_min": 50,
            "rsi_max": 70,
            "above_sma20": True
        }
    },
    "oversold_bounce": {
        "name": "Oversold Bounce",
        "description": "Stocks that are oversold (RSI < 30) and may bounce back",
        "filters": {
            "rsi_max": 30,
            "rsi_min": 15
        }
    },
    "blue_chip": {
        "name": "Blue Chip Quality",
        "description": "Large-cap quality stocks with stable earnings and low debt",
        "filters": {
            "market_cap_min": 50000,
            "debt_to_equity_max": 50,
            "roe_min": 15
        }
    },
    "high_dividend": {
        "name": "High Dividend",
        "description": "Stocks with high dividend yield for passive income",
        "filters": {
            "dividend_yield_min": 3,
            "payout_ratio_max": 80
        }
    },
    "breakout": {
        "name": "Breakout",
        "description": "Stocks breaking above resistance with high volume",
        "filters": {
            "volume_surge_min": 2,
            "above_52w_high_pct": 95
        }
    },
    "undervalued_smallcap": {
        "name": "Undervalued Small Cap",
        "description": "Small cap stocks with growth potential at reasonable valuations",
        "filters": {
            "pe_max": 25,
            "market_cap_max": 20000,
            "earnings_growth_min": 10
        }
    }
}


def run_strategy(strategy_key: str) -> list:
    strategy = STRATEGIES.get(strategy_key)
    if not strategy:
        return []

    results = []
    symbols_to_check = ALL_SYMBOLS[:30]

    for symbol in symbols_to_check:
        try:
            info = get_stock_info(symbol)
            if not info:
                continue

            stock_name = symbol.replace(".NS", "")
            pe = info.get("trailingPE")
            pb = info.get("priceToBook")
            div_yield = (info.get("dividendYield") or 0) * 100
            earnings_growth = (info.get("earningsGrowth") or 0) * 100
            revenue_growth = (info.get("revenueGrowth") or 0) * 100
            profit_margin = (info.get("profitMargins") or 0) * 100
            market_cap = (info.get("marketCap") or 0) / 1e6
            debt_to_equity = info.get("debtToEquity") or 0
            roe = (info.get("returnOnEquity") or 0) * 100
            price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
            change_pct = info.get("regularMarketChangePercent", 0)

            match = False
            f = strategy["filters"]

            if strategy_key == "value_investing":
                match = (pe and pe <= f.get("pe_max", 999)) and (pb and pb <= f.get("pb_max", 999)) and (div_yield >= f.get("dividend_yield_min", 0))
            elif strategy_key == "growth_stocks":
                match = (earnings_growth >= f.get("earnings_growth_min", 0)) and (revenue_growth >= f.get("revenue_growth_min", 0))
            elif strategy_key == "oversold_bounce":
                from core.indicators import calculate_rsi
                data = get_stock_data(symbol, period="3mo")
                if data is not None and len(data) > 14:
                    rsi = calculate_rsi(data['Close'])
                    if rsi is not None:
                        match = rsi <= f.get("rsi_max", 30) and rsi >= f.get("rsi_min", 0)
            elif strategy_key == "blue_chip":
                match = (market_cap >= f.get("market_cap_min", 0)) and (debt_to_equity <= f.get("debt_to_equity_max", 9999)) and (roe >= f.get("roe_min", 0))
            elif strategy_key == "high_dividend":
                match = div_yield >= f.get("dividend_yield_min", 0)
            elif strategy_key == "undervalued_smallcap":
                match = (pe and pe <= f.get("pe_max", 999)) and (market_cap <= f.get("market_cap_max", 999999)) and (earnings_growth >= f.get("earnings_growth_min", 0))
            else:
                match = True

            if match:
                results.append({
                    "symbol": symbol,
                    "name": stock_name,
                    "price": round(price, 2),
                    "changePercent": round(change_pct, 2),
                    "pe": round(pe, 2) if pe else None,
                    "pb": round(pb, 2) if pb else None,
                    "dividendYield": round(div_yield, 2),
                    "marketCap": round(market_cap, 0),
                    "earningsGrowth": round(earnings_growth, 2),
                    "revenueGrowth": round(revenue_growth, 2),
                    "profitMargin": round(profit_margin, 2),
                    "roe": round(roe, 2),
                })
        except Exception:
            continue

    results.sort(key=lambda x: x.get("changePercent", 0), reverse=True)
    return results


def get_all_strategies() -> dict:
    return {k: {"name": v["name"], "description": v["description"]} for k, v in STRATEGIES.items()}
