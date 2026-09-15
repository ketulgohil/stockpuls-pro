from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import json
import os

router = APIRouter(prefix="/api/advanced", tags=["advanced"])


@router.get("/heatmap")
def heatmap():
    from core.advanced import get_heatmap_data
    result = get_heatmap_data()
    return result


@router.get("/global")
def global_markets():
    from core.advanced import get_global_markets
    result = get_global_markets()
    return result


@router.get("/promoter/{symbol}")
def promoter_data(symbol: str):
    from core.advanced import get_promoter_data
    result = get_promoter_data(symbol)
    return result


# Telegram Alerts
TELEGRAM_CONFIG = "data/telegram_config.json"
TELEGRAM_ALERTS = "data/telegram_alerts.json"


class TelegramConfigRequest(BaseModel):
    bot_token: str
    chat_id: str


class TelegramAlertRequest(BaseModel):
    symbol: str
    alert_type: str
    target_price: Optional[float] = None


def load_telegram_config():
    if os.path.exists(TELEGRAM_CONFIG):
        with open(TELEGRAM_CONFIG, "r") as f:
            return json.load(f)
    return {}


def save_telegram_config(data):
    os.makedirs(os.path.dirname(TELEGRAM_CONFIG), exist_ok=True)
    with open(TELEGRAM_CONFIG, "w") as f:
        json.dump(data, f)


def load_telegram_alerts():
    if os.path.exists(TELEGRAM_ALERTS):
        with open(TELEGRAM_ALERTS, "r") as f:
            return json.load(f)
    return {"alerts": []}


def save_telegram_alerts(data):
    os.makedirs(os.path.dirname(TELEGRAM_ALERTS), exist_ok=True)
    with open(TELEGRAM_ALERTS, "w") as f:
        json.dump(data, f)


@router.post("/telegram/config")
def set_telegram_config(request: TelegramConfigRequest):
    save_telegram_config({
        "bot_token": request.bot_token,
        "chat_id": request.chat_id
    })
    return {"message": "Telegram config saved", "status": "configured"}


@router.get("/telegram/config")
def get_telegram_config():
    config = load_telegram_config()
    if config.get("bot_token"):
        return {"configured": True}
    return {"configured": False}


@router.post("/telegram/alert")
def create_telegram_alert(request: TelegramAlertRequest):
    data = load_telegram_alerts()
    alert = {
        "id": len(data["alerts"]) + 1,
        "symbol": request.symbol,
        "alert_type": request.alert_type,
        "target_price": request.target_price,
        "active": True
    }
    data["alerts"].append(alert)
    save_telegram_alerts(data)
    return alert


@router.get("/telegram/alerts")
def get_telegram_alerts():
    return load_telegram_alerts()


@router.delete("/telegram/alert/{alert_id}")
def delete_telegram_alert(alert_id: int):
    data = load_telegram_alerts()
    data["alerts"] = [a for a in data["alerts"] if a["id"] != alert_id]
    save_telegram_alerts(data)
    return {"message": "Alert deleted"}


@router.post("/telegram/test")
def test_telegram():
    config = load_telegram_config()
    if not config.get("bot_token"):
        return {"error": "Telegram not configured"}
    
    try:
        import urllib.request
        import urllib.parse
        
        message = "StockPulse Alert Test! Your Telegram alerts are working."
        url = f"https://api.telegram.org/bot{config['bot_token']}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": config["chat_id"],
            "text": message
        }).encode()
        
        req = urllib.request.Request(url, data=data)
        response = urllib.request.urlopen(req)
        
        return {"message": "Test message sent successfully"}
    except Exception as e:
        return {"error": str(e)}
