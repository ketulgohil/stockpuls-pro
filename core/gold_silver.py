import yfinance as yf
from typing import Optional


def get_gold_prices() -> dict:
    try:
        gold = yf.Ticker("GC=F")
        hist = gold.history(period="1y")
        
        if hist.empty:
            return {"error": "No gold data available"}
        
        current = round(float(hist["Close"].iloc[-1]), 2)
        prev = round(float(hist["Close"].iloc[-2]), 2) if len(hist) > 1 else current
        change = round(current - prev, 2)
        change_pct = round((change / prev) * 100, 2)
        
        high_52w = round(float(hist["Close"].max()), 2)
        low_52w = round(float(hist["Close"].min()), 2)
        
        chart_data = []
        for date, row in hist.iterrows():
            chart_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "price": round(float(row["Close"]), 2)
            })
        
        return {
            "symbol": "GC=F",
            "name": "Gold (USD/oz)",
            "price": current,
            "change": change,
            "changePercent": change_pct,
            "high52w": high_52w,
            "low52w": low_52w,
            "currency": "USD",
            "chartData": chart_data[-90:]
        }
    except Exception as e:
        return {"error": str(e)}


def get_silver_prices() -> dict:
    try:
        silver = yf.Ticker("SI=F")
        hist = silver.history(period="1y")
        
        if hist.empty:
            return {"error": "No silver data available"}
        
        current = round(float(hist["Close"].iloc[-1]), 2)
        prev = round(float(hist["Close"].iloc[-2]), 2) if len(hist) > 1 else current
        change = round(current - prev, 2)
        change_pct = round((change / prev) * 100, 2)
        
        high_52w = round(float(hist["Close"].max()), 2)
        low_52w = round(float(hist["Close"].min()), 2)
        
        chart_data = []
        for date, row in hist.iterrows():
            chart_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "price": round(float(row["Close"]), 2)
            })
        
        return {
            "symbol": "SI=F",
            "name": "Silver (USD/oz)",
            "price": current,
            "change": change,
            "changePercent": change_pct,
            "high52w": high_52w,
            "low52w": low_52w,
            "currency": "USD",
            "chartData": chart_data[-90:]
        }
    except Exception as e:
        return {"error": str(e)}


def get_gold_etfs() -> list[dict]:
    etfs = [
        {"symbol": "GLD", "name": "SPDR Gold Shares", "type": "ETF"},
        {"symbol": "IAU", "name": "iShares Gold Trust", "type": "ETF"},
        {"symbol": "SGOL", "name": "Aberdeen Gold ETF", "type": "ETF"},
        {"symbol": "GLDM", "name": "SPDR Mini Gold", "type": "ETF"},
        {"symbol": "AAAU", "name": "Gold ETF Peru", "type": "ETF"},
    ]
    
    results = []
    for etf in etfs:
        try:
            ticker = yf.Ticker(etf["symbol"])
            hist = ticker.history(period="5d")
            if len(hist) >= 2:
                current = round(float(hist["Close"].iloc[-1]), 2)
                prev = round(float(hist["Close"].iloc[-2]), 2)
                change_pct = round(((current - prev) / prev) * 100, 2)
                results.append({
                    **etf,
                    "price": current,
                    "changePercent": change_pct
                })
        except:
            continue
    
    return results


def get_gold_nifty_ratio() -> dict:
    try:
        gold = yf.Ticker("GC=F")
        nifty = yf.Ticker("^NSEI")
        
        gold_hist = gold.history(period="1y")
        nifty_hist = nifty.history(period="1y")
        
        if gold_hist.empty or nifty_hist.empty:
            return {"error": "No data available"}
        
        gold_start = float(gold_hist["Close"].iloc[0])
        gold_end = float(gold_hist["Close"].iloc[-1])
        gold_return = ((gold_end - gold_start) / gold_start) * 100
        
        nifty_start = float(nifty_hist["Close"].iloc[0])
        nifty_end = float(nifty_hist["Close"].iloc[-1])
        nifty_return = ((nifty_end - nifty_start) / nifty_start) * 100
        
        ratio_start = gold_start / nifty_start
        ratio_end = gold_end / nifty_end
        
        return {
            "gold_return_1y": round(gold_return, 2),
            "nifty_return_1y": round(nifty_return, 2),
            "gold_current": round(gold_end, 2),
            "nifty_current": round(nifty_end, 2),
            "ratio": round(ratio_end, 4),
            "ratio_change": round(((ratio_end - ratio_start) / ratio_start) * 100, 2),
            "better_performer": "Gold" if gold_return > nifty_return else "Nifty"
        }
    except Exception as e:
        return {"error": str(e)}


def calculate_gold_value(weight_grams: float, purity: str = "24K") -> dict:
    purity_map = {
        "24K": 0.999,
        "22K": 0.916,
        "18K": 0.750,
        "14K": 0.585,
    }
    
    try:
        gold = yf.Ticker("GC=F")
        hist = gold.history(period="5d")
        
        if hist.empty:
            return {"error": "No gold price data available"}
        
        price_per_oz = float(hist["Close"].iloc[-1])

        try:
            from core.currency import get_exchange_rate
            rate_data = get_exchange_rate("USD", "INR")
            usd_inr = rate_data.get("rate", 83.5) if rate_data else 83.5
        except Exception:
            usd_inr = 83.5
        
        price_per_gram = price_per_oz / 31.1035
        inr_per_gram = price_per_gram * usd_inr
        
        purity_factor = purity_map.get(purity, 0.999)
        value = weight_grams * inr_per_gram * purity_factor
        
        return {
            "weight_grams": weight_grams,
            "purity": purity,
            "purity_factor": purity_factor,
            "gold_price_usd_per_oz": round(price_per_oz, 2),
            "gold_price_inr_per_gram": round(inr_per_gram, 2),
            "usd_inr_rate": round(usd_inr, 2),
            "total_value_inr": round(value, 2),
            "total_value_usd": round(value / usd_inr, 2)
        }
    except Exception as e:
        return {"error": str(e)}
