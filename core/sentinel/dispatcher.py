import json
import os
import time
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.sentinel.types import SentinelAlert, MarketDigest

class SentinelDispatcher:
    def __init__(self, storage_file: str = "data/sentinel_alerts.json", digest_file: str = "data/sentinel_digests.json"):
        self.storage_file = storage_file
        self.digest_file = digest_file
        self.cooldown_tracker: Dict[str, float] = {}  # key: "symbol:category" -> timestamp
        self.cooldown_seconds = 900  # 15 minutes default cooldown
        self.ws_subscribers: list = []

    def register_ws(self, ws):
        if ws not in self.ws_subscribers:
            self.ws_subscribers.append(ws)

    def unregister_ws(self, ws):
        if ws in self.ws_subscribers:
            self.ws_subscribers.remove(ws)

    def is_cooldown_active(self, symbol: str, category: str) -> bool:
        key = f"{symbol}:{category}"
        last_time = self.cooldown_tracker.get(key, 0.0)
        return (time.time() - last_time) < self.cooldown_seconds

    def record_alert_time(self, symbol: str, category: str):
        key = f"{symbol}:{category}"
        self.cooldown_tracker[key] = time.time()

    def save_alert(self, alert: SentinelAlert):
        os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
        alerts = self.get_alerts()
        alerts.insert(0, alert.model_dump())
        alerts = alerts[:100]  # Keep latest 100
        with open(self.storage_file, "w") as f:
            json.dump({"alerts": alerts}, f, indent=2)

    def get_alerts(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r") as f:
                    data = json.load(f)
                    return data.get("alerts", [])
            except Exception:
                pass
        return []

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Returns the current list of alerts saved in storage."""
        return self.get_alerts()

    def save_digest(self, digest: MarketDigest):
        os.makedirs(os.path.dirname(self.digest_file), exist_ok=True)
        digests = self.get_digests()
        digests.insert(0, digest.model_dump())
        digests = digests[:30]  # Keep latest 30
        with open(self.digest_file, "w") as f:
            json.dump({"digests": digests}, f, indent=2)

    def get_digests(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.digest_file):
            try:
                with open(self.digest_file, "r") as f:
                    data = json.load(f)
                    return data.get("digests", [])
            except Exception:
                pass
        return []

    async def broadcast_ws(self, message: dict):
        dead_conns = []
        for ws in self.ws_subscribers:
            try:
                await ws.send_json(message)
            except Exception:
                dead_conns.append(ws)
        for dead in dead_conns:
            self.unregister_ws(dead)

    def send_telegram(self, alert: SentinelAlert):
        config_path = "data/telegram_config.json"
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")

        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                bot_token = cfg.get("bot_token") or bot_token
                chat_id = cfg.get("chat_id") or chat_id
            except Exception:
                pass

        if not bot_token or not chat_id:
            return

        try:
            target_str = f"₹{alert.analysis.target_resistance}" if alert.analysis.target_resistance is not None else "N/A"
            sl_str = f"₹{alert.analysis.invalidation_level}" if alert.analysis.invalidation_level is not None else "N/A"

            text = f"""🚨 *StockPulse Sentinel Alert* 🚨
*Stock:* `{alert.symbol}` ({alert.severity})
*Title:* {alert.title}
*Summary:* {alert.summary}

🐂 *Bull Case:* {alert.analysis.bull_case}
🐻 *Bear Case:* {alert.analysis.bear_case}
🎯 *Target:* {target_str} | 🛑 *SL:* {sl_str}
📊 *Confidence:* {alert.analysis.confidence_score}% ({alert.analysis.consensus_bias})
"""
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }).encode("utf-8")
            req = urllib.request.Request(url, data=data)
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    async def dispatch_alert(self, alert: SentinelAlert):
        self.save_alert(alert)
        await self.broadcast_ws({"type": "SENTINEL_ALERT", "alert": alert.model_dump()})
        self.send_telegram(alert)

    async def dispatch_digest(self, digest: MarketDigest):
        self.save_digest(digest)
        await self.broadcast_ws({"type": "SENTINEL_DIGEST", "digest": digest.model_dump()})

dispatcher = SentinelDispatcher()
