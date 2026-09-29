from typing import List
from datetime import datetime
from core.data_fetcher import get_stock_info
from core.sentinel.types import DeskFinding

class FundamentalsDesk:
    @staticmethod
    def scan(symbol: str) -> List[DeskFinding]:
        findings = []
        try:
            info = get_stock_info(symbol)
            if not info or "error" in info:
                return findings

            pe = info.get("pe_ratio") if info.get("pe_ratio") is not None else info.get("pe")
            eps = info.get("eps") if info.get("eps") is not None else info.get("trailingEps")
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if pe is not None and pe > 0:
                findings.append(DeskFinding(
                    desk="FUNDAMENTALS",
                    symbol=symbol,
                    headline=f"Valuation: Trailing P/E {float(pe):.1f}x (EPS: ₹{eps if eps is not None else 'N/A'})",
                    metrics={"pe": float(pe), "eps": eps},
                    significance="LOW",
                    timestamp=now_str
                ))
        except Exception:
            pass
        return findings
