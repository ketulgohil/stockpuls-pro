from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import json
import os

router = APIRouter(prefix="/api/gemini", tags=["gemini"])

CONFIG_FILE = "data/gemini_config.json"


class AnalyzeRequest(BaseModel):
    symbol: str


class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = ""


class ConfigRequest(BaseModel):
    api_key: str


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_config(data):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f)


@router.post("/config")
def set_api_key(request: ConfigRequest):
    save_config({"api_key": request.api_key})
    
    from core.gemini import configure_gemini
    configure_gemini(request.api_key)
    
    return {"message": "API key saved", "status": "configured"}


@router.get("/config")
def get_config():
    config = load_config()
    if config.get("api_key"):
        key = config["api_key"]
        masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
        return {"configured": True, "api_key_masked": masked}
    return {"configured": False}


@router.post("/analyze")
def analyze_stock(request: AnalyzeRequest):
    config = load_config()
    if not config.get("api_key"):
        return {"error": "Gemini API key not configured. Go to AI tab → Settings."}
    
    from core.gemini import configure_gemini, analyze_stock_with_gemini
    configure_gemini(config["api_key"])
    
    result = analyze_stock_with_gemini(request.symbol)
    return result


@router.post("/chat")
def chat(request: ChatRequest):
    config = load_config()
    if not config.get("api_key"):
        return {"error": "Gemini API key not configured. Go to AI tab → Settings."}
    
    from core.gemini import configure_gemini, ai_chat, get_market_context
    configure_gemini(config["api_key"])
    
    context = get_market_context()
    result = ai_chat(request.message, context)
    return result


@router.get("/status")
def status():
    config = load_config()
    if config.get("api_key"):
        from core.gemini import get_gemini_model
        model = get_gemini_model()
        if model:
            return {"status": "ready", "model": "gemini-2.0-flash"}
    return {"status": "not_configured"}
