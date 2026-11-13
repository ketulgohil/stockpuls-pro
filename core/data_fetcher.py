"""Market data access layer.

All Indian equity / index data now comes from Upstox (via
``core.upstox_data``).  Fundamentals that Upstox does not expose are
sourced from the Downstox API.  yfinance has been removed.
"""

import json
import urllib.request
from typing import Optional

import pandas as pd

from core.cache import stock_cache, price_cache, cached
from core import upstox_data


# ---------------------------------------------------------------------------
# Symbol universe (current NSE trading symbols)
# ---------------------------------------------------------------------------

NIFTY50_SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "TMPV.NS",
    "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "NESTLEIND.NS", "WIPRO.NS",
    "ONGC.NS", "TATASTEEL.NS", "NTPC.NS", "POWERGRID.NS", "M&M.NS",
    "JSWSTEEL.NS", "ADANIENT.NS", "ADANIPORTS.NS", "TECHM.NS", "HCLTECH.NS",
    "BAJFINANCE.NS", "BAJAJFINSV.NS", "INDUSINDBK.NS", "DRREDDY.NS", "CIPLA.NS",
    "DIVISLAB.NS", "EICHERMOT.NS", "GRASIM.NS", "HEROMOTOCO.NS", "HINDALCO.NS",
    "TATACONSUM.NS", "APOLLOHOSP.NS", "COALINDIA.NS", "BRITANNIA.NS", "BPCL.NS",
    "COLPAL.NS", "SBILIFE.NS", "HDFCLIFE.NS", "BAJAJ-AUTO.NS", "TMCV.NS",
]

MIDCAP_SYMBOLS = [
    "PIDILITIND.NS", "DABUR.NS", "MARICO.NS", "BERGEPAINT.NS", "INDIGO.NS",
    "BIOCON.NS", "TRENT.NS", "ETERNAL.NS", "PAYTM.NS", "POLICYBZR.NS",
    "NYKAA.NS", "DELHIVERY.NS", "CLEAN.NS", "DEEPAKNTR.NS", "AFFLE.NS",
    "TANLA.NS", "HAPPSTMNDS.NS", "ZENSARTECH.NS", "MASTEK.NS",
    "FEDERALBNK.NS", "BANDHANBNK.NS", "IDFCFIRSTB.NS", "PNB.NS", "CANBK.NS",
    "UNIONBANK.NS", "INDIANB.NS", "CENTRALBK.NS", "BANKBARODA.NS", "PSB.NS",
]

NIFTY500_POPULAR = [
    "TATACHEM.NS", "TATAPOWER.NS", "TATAELXSI.NS",
    "ADANIGREEN.NS", "ADANIENSOL.NS", "ATGL.NS", "ADANIPOWER.NS",
    "LICI.NS", "IRFC.NS", "RECLTD.NS", "PFC.NS", "NHPC.NS", "SJVN.NS",
    "HAL.NS", "BEL.NS", "BDL.NS", "CDSL.NS", "CAMS.NS", "KFINTECH.NS",
    "IIFL.NS", "MUTHOOTFIN.NS", "MANAPPURAM.NS", "BAJAJHLDNG.NS",
    "CHOLAFIN.NS", "SBICARD.NS", "HDFCAMC.NS", "CROMPTON.NS", "VOLTAS.NS",
    "BLUESTARCO.NS", "KAJARIACER.NS", "ASAHIINDIA.NS",
    "GRINDWELL.NS", "FIVESTAR.NS", "CERA.NS", "SUNTV.NS", "NETWORK18.NS",
    "IDEA.NS", "MTNL.NS",
]

SECTOR_MAP = {
    "RELIANCE.NS": "Oil & Gas", "TCS.NS": "IT", "HDFCBANK.NS": "Banking",
    "INFY.NS": "IT", "ICICIBANK.NS": "Banking", "HINDUNILVR.NS": "FMCG",
    "SBIN.NS": "Banking", "BHARTIARTL.NS": "Telecom", "ITC.NS": "FMCG",
    "KOTAKBANK.NS": "Banking", "LT.NS": "Infrastructure", "AXISBANK.NS": "Banking",
    "ASIANPAINT.NS": "Paints", "MARUTI.NS": "Automobile", "TMPV.NS": "Automobile",
    "TMCV.NS": "Automobile", "SUNPHARMA.NS": "Pharma", "TITAN.NS": "Consumer",
    "ULTRACEMCO.NS": "Cement", "NESTLEIND.NS": "FMCG", "WIPRO.NS": "IT",
    "ONGC.NS": "Oil & Gas", "TATASTEEL.NS": "Metals", "NTPC.NS": "Power",
    "POWERGRID.NS": "Power", "M&M.NS": "Automobile", "JSWSTEEL.NS": "Metals",
    "ADANIENT.NS": "Conglomerate", "ADANIPORTS.NS": "Infrastructure",
    "TECHM.NS": "IT", "HCLTECH.NS": "IT", "BAJFINANCE.NS": "Finance",
    "BAJAJFINSV.NS": "Finance", "INDUSINDBK.NS": "Banking",
    "DRREDDY.NS": "Pharma", "CIPLA.NS": "Pharma", "DIVISLAB.NS": "Pharma",
    "EICHERMOT.NS": "Automobile", "GRASIM.NS": "Cement",
    "HEROMOTOCO.NS": "Automobile", "HINDALCO.NS": "Metals",
    "TATACONSUM.NS": "FMCG", "APOLLOHOSP.NS": "Healthcare",
    "COALINDIA.NS": "Mining", "BRITANNIA.NS": "FMCG", "BPCL.NS": "Oil & Gas",
    "COLPAL.NS": "FMCG", "SBILIFE.NS": "Insurance", "HDFCLIFE.NS": "Insurance",
    "BAJAJ-AUTO.NS": "Automobile",
    "JPL.NS": "Telecom", "LGEINDIA.NS": "Consumer Durables",
    "HDFIRE.NS": "Industrials", "ANANTRAJ.NS": "Realty",
}

ALL_SYMBOLS = list(dict.fromkeys(NIFTY50_SYMBOLS + MIDCAP_SYMBOLS + NIFTY500_POPULAR))


def _fetch_downstox(endpoint: str) -> Optional[dict]:
    try:
        url = f"https://downstox.com/api{endpoint}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def get_dynamic_stock_list() -> list[dict]:
    """Try to fetch live stock lists from Downstox, fallback to hardcoded."""
    data = _fetch_downstox("/stocks?page=1&limit=500")
    if data and data.get("success") and data.get("stocks"):
        stocks = []
        for item in data["stocks"]:
            symbol = item.get("symbol", "")
            if not symbol.endswith(".NS"):
                symbol = symbol + ".NS"
            stocks.append({
                "symbol": symbol,
                "name": item.get("name", symbol.replace(".NS", "")),
                "exchange": item.get("exchange", "NSE"),
                "sector": item.get("sector", "Unknown"),
            })
        return stocks

    return get_stock_list()


def get_stock_list() -> list[dict]:
    stocks = []
    for symbol in ALL_SYMBOLS:
        name = symbol.replace(".NS", "")
        stocks.append({
            "symbol": symbol,
            "name": upstox_data.instrument_name(symbol) or name,
            "exchange": "NSE",
            "sector": SECTOR_MAP.get(symbol, "Unknown"),
        })
    return sorted(stocks, key=lambda x: x["name"])


# ---------------------------------------------------------------------------
# Data accessors (Upstox-backed)
# ---------------------------------------------------------------------------

@cached(stock_cache)
def get_stock_data(symbol: str, period: str = "6mo", interval: str = "1d") -> Optional[pd.DataFrame]:
    return upstox_data.get_stock_data(symbol, period=period, interval=interval)


@cached(stock_cache)
def get_stock_info(symbol: str) -> Optional[dict]:
    return upstox_data.get_stock_info(symbol)


@cached(price_cache)
def get_live_price(symbol: str) -> Optional[dict]:
    return upstox_data.get_live_price(symbol)


def search_stocks(query: str) -> list[dict]:
    return upstox_data.search_stocks(query)


def get_sector_data() -> dict:
    sectors = {}
    for symbol, sector in SECTOR_MAP.items():
        if sector not in sectors:
            sectors[sector] = []
        sectors[sector].append(symbol)
    return sectors


def get_sector_stocks(sector: str) -> list[dict]:
    stocks = []
    for symbol, s in SECTOR_MAP.items():
        if s == sector:
            name = symbol.replace(".NS", "")
            stocks.append({
                "symbol": symbol,
                "name": name,
                "exchange": "NSE",
                "sector": sector,
            })
    return stocks
