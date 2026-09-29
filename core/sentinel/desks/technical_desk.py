from typing import List, Optional
import pandas as pd
from datetime import datetime
from core.sentinel.types import DeskFinding

class TechnicalDesk:
    @staticmethod
    def scan(symbol: str, df: Optional[pd.DataFrame]) -> List[DeskFinding]:
        findings = []
        if df is None or len(df) < 5:
            return findings

        try:
            latest = df.iloc[-1]
            close = float(latest['Close'])
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # RSI Signals
            rsi = latest.get('RSI', None)
            if rsi is not None and not pd.isna(rsi):
                rsi = float(rsi)
                if rsi >= 75:
                    findings.append(DeskFinding(
                        desk="TECHNICAL",
                        symbol=symbol,
                        headline=f"RSI Overbought Alert ({rsi:.1f}) - Potential mean reversion or momentum peak",
                        metrics={"rsi": round(rsi, 2), "price": round(close, 2)},
                        significance="MEDIUM" if rsi < 80 else "HIGH",
                        timestamp=now_str
                    ))
                elif rsi <= 25:
                    findings.append(DeskFinding(
                        desk="TECHNICAL",
                        symbol=symbol,
                        headline=f"RSI Oversold Bounce Setup ({rsi:.1f}) - Potential capitulation bottom",
                        metrics={"rsi": round(rsi, 2), "price": round(close, 2)},
                        significance="HIGH",
                        timestamp=now_str
                    ))

            # EMA 20 & SMA 50 breakout
            ema20 = latest.get('EMA_20', None)
            if ema20 is not None and not pd.isna(ema20) and close > float(ema20):
                prev = df.iloc[-2]
                prev_close = float(prev['Close'])
                prev_ema20 = prev.get('EMA_20', prev_close)
                if not pd.isna(prev_ema20) and prev_close <= float(prev_ema20):
                    findings.append(DeskFinding(
                        desk="TECHNICAL",
                        symbol=symbol,
                        headline=f"Bullish 20 EMA Reclaim at ₹{close:.2f}",
                        metrics={"price": round(close, 2), "ema_20": round(float(ema20), 2)},
                        significance="MEDIUM",
                        timestamp=now_str
                    ))
        except Exception:
            pass

        return findings
