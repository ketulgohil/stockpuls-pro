import asyncio
from datetime import datetime
import pytz

class ISTScheduler:
    @staticmethod
    def get_ist_now() -> datetime:
        try:
            return datetime.now(pytz.timezone("Asia/Kolkata"))
        except Exception:
            return datetime.now()

    @staticmethod
    def is_market_hours() -> bool:
        now = ISTScheduler.get_ist_now()
        # Monday=0, Friday=4
        if now.weekday() > 4:
            return False
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        return market_open <= now <= market_close
