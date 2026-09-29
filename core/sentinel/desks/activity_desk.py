from typing import List, Optional
import pandas as pd
from datetime import datetime
from core.sentinel.types import DeskFinding

class ActivityDesk:
    @staticmethod
    def scan(symbol: str, df: Optional[pd.DataFrame]) -> List[DeskFinding]:
        findings = []
        if df is None or len(df) < 21:
            return findings

        try:
            latest = df.iloc[-1]
            prev_20 = df.iloc[-21:-1]
            avg_vol = prev_20['Volume'].mean()
            cur_vol = latest['Volume']

            if avg_vol > 0:
                multiplier = round(float(cur_vol / avg_vol), 2)
                if multiplier >= 2.5:
                    significance = "CRITICAL" if multiplier >= 4.0 else "HIGH"
                    findings.append(DeskFinding(
                        desk="ACTIVITY",
                        symbol=symbol,
                        headline=f"Unusual Volume Surge: {multiplier}x 20-period average volume",
                        metrics={
                            "current_volume": int(cur_vol),
                            "average_volume": int(avg_vol),
                            "volume_multiplier": multiplier
                        },
                        significance=significance,
                        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))
        except Exception:
            pass

        return findings
