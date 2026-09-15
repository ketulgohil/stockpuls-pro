from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import json
import os

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/portfolio")
def portfolio_analytics():
    from core.portfolio_analytics import get_portfolio_analytics
    result = get_portfolio_analytics()
    return result


# Market Status Banner
@router.get("/market-status")
def market_status():
    from core.more_features import get_market_status
    result = get_market_status()
    return result


# Alerts Pro
ALERTS_PRO_FILE = "data/alerts_pro.json"


class AlertProRequest(BaseModel):
    symbol: str
    conditions: dict
    name: Optional[str] = ""


def load_alerts_pro():
    if os.path.exists(ALERTS_PRO_FILE):
        with open(ALERTS_PRO_FILE, "r") as f:
            return json.load(f)
    return {"alerts": []}


def save_alerts_pro(data):
    os.makedirs(os.path.dirname(ALERTS_PRO_FILE), exist_ok=True)
    with open(ALERTS_PRO_FILE, "w") as f:
        json.dump(data, f, indent=2)


@router.get("/alerts")
def get_alerts_pro():
    return load_alerts_pro()


@router.post("/alerts")
def create_alert_pro(request: AlertProRequest):
    data = load_alerts_pro()
    alert = {
        "id": len(data["alerts"]) + 1,
        "symbol": request.symbol,
        "name": request.name or f"Alert on {request.symbol}",
        "conditions": request.conditions,
        "active": True
    }
    data["alerts"].append(alert)
    save_alerts_pro(data)
    return alert


@router.delete("/alerts/{alert_id}")
def delete_alert_pro(alert_id: int):
    data = load_alerts_pro()
    data["alerts"] = [a for a in data["alerts"] if a["id"] != alert_id]
    save_alerts_pro(data)
    return {"message": "Alert deleted"}


# PDF Export (simple text format)
@router.get("/portfolio/report")
def portfolio_report():
    from core.portfolio_analytics import get_portfolio_analytics
    from core.more_features import get_market_status
    
    analytics = get_portfolio_analytics()
    status = get_market_status()
    
    if "error" in analytics:
        return {"error": "No portfolio data"}
    
    report = {
        "title": "StockPulse Portfolio Report",
        "generatedAt": status.get("currentTime", ""),
        "marketStatus": status.get("status", ""),
        "summary": analytics.get("summary", {}),
        "holdings": analytics.get("holdings", []),
        "sectorAllocation": analytics.get("sectorAllocation", {}),
        "topPerformers": analytics.get("topPerformers", []),
        "worstPerformers": analytics.get("worstPerformers", [])
    }
    
    return report
