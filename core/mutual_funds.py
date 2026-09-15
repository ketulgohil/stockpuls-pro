import yfinance as yf
import json
import os
import urllib.request
import urllib.error
from typing import Optional
from datetime import datetime


def _fetch_downstox(endpoint: str) -> Optional[dict]:
    try:
        url = f"https://downstox.com/api{endpoint}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _get_downstox_mf_schemes(page: int = 1, limit: int = 20) -> list:
    data = _fetch_downstox(f"/mf/schemes?page={page}&limit={limit}")
    if data and data.get("success"):
        return data.get("schemes", [])
    return []


def _get_downstox_mf_scheme_detail(code: str) -> Optional[dict]:
    data = _fetch_downstox(f"/mf/scheme/{code}")
    if data and data.get("success"):
        return data.get("scheme", data)
    return None


# Popular Indian Mutual Funds - Yahoo Finance fallback
MF_FUNDS = {
    "HDFC Mid-Cap Opportunities Fund": "HDFC Mid-Cap Opportunities Fund-Growth",
    "SBI Small Cap Fund": "SBI Small Cap Fund-Growth",
    "Mirae Asset Large Cap Fund": "Mirae Asset Large Cap Fund-Growth",
    "Axis Bluechip Fund": "Axis Bluechip Fund-Growth",
    "ICICI Prudential Bluechip Fund": "ICICI Prudential Bluechip Fund-Growth",
    "Nippon India Small Cap Fund": "Nippon India Small Cap Fund-Growth",
    "Parag Parikh Flexi Cap Fund": "Parag Parikh Flexi Cap Fund-Growth",
    "HDFC Flexi Cap Fund": "HDFC Flexi Cap Fund-Growth",
    "UTI Nifty Index Fund": "UTI Nifty Index Fund-Growth",
    "SBI Nifty Index Fund": "SBI Nifty Index Fund-Growth",
    "Kotak Equity Opps Fund": "Kotak Equity Opportunities Fund-Growth",
    "L&T Midcap Fund": "L&T Midcap Fund-Growth",
    "Aditya Birla Sun Life Digital India Fund": "Aditya Birla Sun Life Digital India Fund-Growth",
    "Tata Digital India Fund": "Tata Digital India Fund-Growth",
    "Navi Nifty 50 Index Fund": "Navi Nifty 50 Index Fund-Growth",
}


def get_mf_nav(fund_name: str) -> Optional[dict]:
    try:
        ticker = yf.Ticker(fund_name)
        hist = ticker.history(period="1y")
        
        if hist.empty or len(hist) < 2:
            return None
        
        current_nav = hist['Close'].iloc[-1]
        prev_nav = hist['Close'].iloc[-2]
        
        # Calculate returns
        hist_1w = hist.tail(5)
        hist_1m = hist.tail(22)
        hist_3m = hist.tail(66)
        hist_6m = hist.tail(132)
        hist_1y = hist
        
        returns = {
            "1W": round(((current_nav / hist_1w['Close'].iloc[0]) - 1) * 100, 2) if len(hist_1w) > 0 else 0,
            "1M": round(((current_nav / hist_1m['Close'].iloc[0]) - 1) * 100, 2) if len(hist_1m) > 0 else 0,
            "3M": round(((current_nav / hist_3m['Close'].iloc[0]) - 1) * 100, 2) if len(hist_3m) > 0 else 0,
            "6M": round(((current_nav / hist_6m['Close'].iloc[0]) - 1) * 100, 2) if len(hist_6m) > 0 else 0,
            "1Y": round(((current_nav / hist_1y['Close'].iloc[0]) - 1) * 100, 2) if len(hist_1y) > 0 else 0,
        }
        
        return {
            "name": fund_name,
            "nav": round(current_nav, 2),
            "dailyChange": round(current_nav - prev_nav, 2),
            "dailyChangePct": round(((current_nav - prev_nav) / prev_nav) * 100, 2),
            "returns": returns,
            "category": get_fund_category(fund_name)
        }
    except Exception as e:
        return None


def get_fund_category(fund_name: str) -> str:
    for cat, funds in MF_CATEGORIES.items():
        if fund_name in funds:
            return cat
    return "Other"


def get_all_mf_data() -> list:
    results = []

    downstox_schemes = _get_downstox_mf_schemes(page=1, limit=20)
    if downstox_schemes:
        for scheme in downstox_schemes:
            try:
                nav = float(scheme.get("nav", 0) or 0)
            except (ValueError, TypeError):
                nav = 0
            try:
                ret_1m = float(scheme.get("return_1m", 0) or 0)
            except (ValueError, TypeError):
                ret_1m = 0
            try:
                ret_1y = float(scheme.get("return_1y", 0) or 0)
            except (ValueError, TypeError):
                ret_1y = 0
            try:
                ret_3y = float(scheme.get("return_3y", 0) or 0)
            except (ValueError, TypeError):
                ret_3y = 0
            results.append({
                "name": scheme.get("scheme_name", ""),
                "nav": nav,
                "dailyChange": 0,
                "dailyChangePct": 0,
                "returns": {
                    "1M": ret_1m,
                    "1Y": ret_1y,
                    "3Y": ret_3y,
                },
                "category": scheme.get("category", "Other"),
                "schemeCode": scheme.get("scheme_code", ""),
            })
        return results

    for name in MF_FUNDS:
        data = get_mf_nav(name)
        if data:
            results.append(data)

    return results


def calculate_sip(monthly_amount: float, annual_return: float, years: int) -> dict:
    monthly_return = annual_return / (12 * 100)
    months = years * 12
    
    total_invested = monthly_amount * months
    future_value = 0
    
    for i in range(months):
        future_value = (future_value + monthly_amount) * (1 + monthly_return)
    
    wealth_gained = future_value - total_invested
    
    return {
        "monthlyAmount": monthly_amount,
        "annualReturn": annual_return,
        "years": years,
        "totalInvested": round(total_invested, 2),
        "futureValue": round(future_value, 2),
        "wealthGained": round(wealth_gained, 2),
        "returnMultiple": round(future_value / total_invested, 2) if total_invested > 0 else 0
    }
