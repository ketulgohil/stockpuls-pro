import yfinance as yf
from typing import Optional
from core.data_fetcher import ALL_SYMBOLS, SECTOR_MAP


def get_heatmap_data() -> dict:
    sector_stocks = {}
    for symbol in ALL_SYMBOLS[:50]:
        sector = "Others"
        for s, members in SECTOR_MAP.items():
            if symbol.replace(".NS", "") in members:
                sector = s
                break
        if sector not in sector_stocks:
            sector_stocks[sector] = []
        sector_stocks[sector].append(symbol)
    
    heatmap = []
    
    for sector, stocks in sector_stocks.items():
        sector_data = {"name": sector, "stocks": []}
        sector_change = 0
        count = 0
        
        for symbol in stocks[:8]:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5d")
                if len(hist) >= 2:
                    prev = hist["Close"].iloc[-2]
                    curr = hist["Close"].iloc[-1]
                    change_pct = ((curr - prev) / prev) * 100
                    
                    sector_data["stocks"].append({
                        "symbol": symbol,
                        "name": symbol.replace(".NS", ""),
                        "change": round(float(change_pct), 2),
                        "price": round(float(curr), 2)
                    })
                    sector_change += change_pct
                    count += 1
            except:
                continue
        
        sector_data["avgChange"] = round(sector_change / max(count, 1), 2)
        sector_data["stockCount"] = len(sector_data["stocks"])
        heatmap.append(sector_data)
    
    heatmap.sort(key=lambda x: x["avgChange"], reverse=True)
    return {"sectors": heatmap}


def get_global_markets() -> dict:
    markets = []
    
    global_symbols = [
        {"symbol": "^DJI", "name": "Dow Jones", "country": "US"},
        {"symbol": "^GSPC", "name": "S&P 500", "country": "US"},
        {"symbol": "^IXIC", "name": "Nasdaq", "country": "US"},
        {"symbol": "^FTSE", "name": "FTSE 100", "country": "UK"},
        {"symbol": "^N225", "name": "Nikkei 225", "country": "Japan"},
        {"symbol": "^HSI", "name": "Hang Seng", "country": "Hong Kong"},
        {"symbol": "^GDAXI", "name": "DAX", "country": "Germany"},
        {"symbol": "000001.SS", "name": "Shanghai", "country": "China"},
        {"symbol": "^NSEI", "name": "NIFTY 50", "country": "India"},
        {"symbol": "^BSESN", "name": "SENSEX", "country": "India"},
        {"symbol": "USDINR=X", "name": "USD/INR", "country": "Currency"},
        {"symbol": "GC=F", "name": "Gold", "country": "Commodity"},
        {"symbol": "SI=F", "name": "Silver", "country": "Commodity"},
        {"symbol": "CL=F", "name": "Crude Oil", "country": "Commodity"},
    ]
    
    for item in global_symbols:
        try:
            ticker = yf.Ticker(item["symbol"])
            hist = ticker.history(period="5d")
            
            if len(hist) >= 2:
                prev = hist["Close"].iloc[-2]
                curr = hist["Close"].iloc[-1]
                change = curr - prev
                change_pct = (change / prev) * 100
            elif len(hist) == 1:
                curr = hist["Close"].iloc[-1]
                change = 0
                change_pct = 0
            else:
                continue
            
            markets.append({
                "symbol": item["symbol"],
                "name": item["name"],
                "country": item["country"],
                "price": round(float(curr), 2),
                "change": round(float(change), 2),
                "changePercent": round(float(change_pct), 2)
            })
        except:
            continue
    
    return {"markets": markets}


def get_promoter_data(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        promoters = info.get("heldPercentInsiders", 0)
        institutions = info.get("heldPercentInstitutions", 0)
        mutual_funds = info.get("heldPercentMutualFunds", 0)
        
        return {
            "symbol": symbol,
            "name": symbol.replace(".NS", ""),
            "promoterHolding": round(promoters * 100, 2) if promoters else None,
            "institutionHolding": round(institutions * 100, 2) if institutions else None,
            "mutualFundHolding": round(mutual_funds * 100, 2) if mutual_funds else None,
            "floatShares": info.get("floatShares"),
            "sharesOutstanding": info.get("sharesOutstanding"),
            "shortRatio": info.get("shortRatio"),
            "shortPercentOfFloat": info.get("shortPercentOfFloat"),
            "note": "Data from Yahoo Finance. For detailed Indian promoter data, check BSE/NSE directly."
        }
    except Exception as e:
        return {"error": str(e)}
