import yfinance as yf
from typing import Optional
import json
import urllib.request
import urllib.error


def get_block_deals() -> list:
    """Fetch real block deals from NSE"""
    try:
        url = "https://www.nseindia.com/api/block-deal"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json",
            "Referer": "https://www.nseindia.com/market-data/block-deals"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        if data.get("data"):
            deals = []
            for item in data["data"][:15]:
                deals.append({
                    "symbol": item.get("symbol", ""),
                    "series": item.get("series", ""),
                    "client": item.get("clientName", ""),
                    "dealType": item.get("dealType", ""),
                    "quantity": item.get("quantity", 0),
                    "price": item.get("tradePrice", 0),
                    "value": item.get("value", 0),
                    "date": item.get("lastDate", ""),
                })
            return deals
    except Exception:
        pass

    return []


def get_bulk_deals() -> list:
    """Fetch real bulk deals from NSE"""
    try:
        url = "https://www.nseindia.com/api/bulk-deal"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json",
            "Referer": "https://www.nseindia.com/market-data/bulk-deals"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        if data.get("data"):
            deals = []
            for item in data["data"][:15]:
                deals.append({
                    "symbol": item.get("symbol", ""),
                    "series": item.get("series", ""),
                    "client": item.get("clientName", ""),
                    "dealType": item.get("dealType", ""),
                    "quantity": item.get("quantity", 0),
                    "price": item.get("tradePrice", 0),
                    "value": item.get("value", 0),
                    "date": item.get("lastDate", ""),
                })
            return deals
    except Exception:
        pass

    return []
