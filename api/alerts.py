from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import json
import os

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

ALERTS_FILE = "data/alerts.json"


class AlertRequest(BaseModel):
    symbol: str
    alert_type: str
    target_price: Optional[float] = None
    message: Optional[str] = ""


def load_alerts():
    if os.path.exists(ALERTS_FILE):
        with open(ALERTS_FILE, "r") as f:
            return json.load(f)
    return {"alerts": []}


def save_alerts(data):
    os.makedirs(os.path.dirname(ALERTS_FILE), exist_ok=True)
    with open(ALERTS_FILE, "w") as f:
        json.dump(data, f, indent=2)


@router.get("")
def get_alerts():
    return load_alerts()


@router.post("")
def create_alert(request: AlertRequest):
    data = load_alerts()
    
    alert = {
        "id": len(data["alerts"]) + 1,
        "symbol": request.symbol,
        "alert_type": request.alert_type,
        "target_price": request.target_price,
        "message": request.message,
        "active": True,
        "created_at": "2024-01-01"
    }
    
    data["alerts"].append(alert)
    save_alerts(data)
    
    return alert


@router.delete("/{alert_id}")
def delete_alert(alert_id: int):
    data = load_alerts()
    data["alerts"] = [a for a in data["alerts"] if a["id"] != alert_id]
    save_alerts(data)
    return {"message": "Alert deleted"}


@router.post("/telegram/setup")
def setup_telegram(bot_token: str, chat_id: str):
    config = {"bot_token": bot_token, "chat_id": chat_id}
    os.makedirs("data", exist_ok=True)
    with open("data/telegram_config.json", "w") as f:
        json.dump(config, f)
    return {"message": "Telegram config saved", "note": "Restart server to activate"}


@router.get("/telegram/status")
def telegram_status():
    if os.path.exists("data/telegram_config.json"):
        with open("data/telegram_config.json", "r") as f:
            config = json.load(f)
        return {"configured": True, "bot_token": config.get("bot_token", "")[:10] + "..."}
    return {"configured": False}
