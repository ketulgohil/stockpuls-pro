"""trader_core.dashboard.alerts - Dashboard alert engine."""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional


class DashboardAlertEngine:
    """Manages price alerts for the dashboard."""

    def __init__(self):
        self._alerts: Dict[str, Dict[str, Any]] = {}
        self._lock = __import__("threading").Lock()

    def add_user_alert(
        self,
        symbol: str,
        price: float,
        direction: str = "above",
        note: str = "",
    ) -> Dict[str, Any]:
        """Add a user price alert."""
        sym = symbol.strip().upper()
        alert_id = f"{sym}_{direction}_{price}_{int(datetime.datetime.now().timestamp())}"
        alert = {
            "id": alert_id,
            "symbol": sym,
            "price": float(price),
            "direction": direction,
            "note": note,
            "triggered": False,
            "created_at": datetime.datetime.now().isoformat(),
        }
        with self._lock:
            self._alerts[alert_id] = alert
        return alert

    def check_alerts(
        self,
        current_prices: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """Check which alerts have been triggered by current prices."""
        triggered = []
        with self._lock:
            for alert_id, alert in self._alerts.items():
                if alert["triggered"]:
                    continue
                sym = alert["symbol"]
                if sym not in current_prices:
                    continue
                current_price = current_prices[sym]
                alert_price = alert["price"]
                direction = alert["direction"]

                fired = False
                if direction == "above" and current_price >= alert_price:
                    fired = True
                elif direction == "below" and current_price <= alert_price:
                    fired = True

                if fired:
                    alert["triggered"] = True
                    alert["triggered_at"] = datetime.datetime.now().isoformat()
                    triggered.append(alert)
        return triggered

    def get_alerts(self) -> List[Dict[str, Any]]:
        """Get all alerts."""
        with self._lock:
            return list(self._alerts.values())

    def remove_alert(self, alert_id: str) -> bool:
        """Remove an alert by ID."""
        with self._lock:
            if alert_id in self._alerts:
                del self._alerts[alert_id]
                return True
        return False
