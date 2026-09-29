import asyncio
from typing import List, Optional
from datetime import datetime
from core.data_fetcher import get_stock_data, get_stock_info, ALL_SYMBOLS
from core.indicators import add_all_indicators
from core.sentinel.types import SentinelAlert, DeskFinding, MarketDigest
from core.sentinel.desks.activity_desk import ActivityDesk
from core.sentinel.desks.technical_desk import TechnicalDesk
from core.sentinel.desks.news_desk import NewsDesk
from core.sentinel.desks.fundamentals_desk import FundamentalsDesk
from core.sentinel.synthesizer import GeminiSynthesizer
from core.sentinel.dispatcher import dispatcher
from core.sentinel.scheduler import ISTScheduler

DEFAULT_TRACKED = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "KOTAKBANK.NS", "LT.NS",
    "TATAMOTORS.NS", "BAJFINANCE.NS", "AXISBANK.NS", "MARUTI.NS", "SUNPHARMA.NS"
]

class SentinelEngine:
    def __init__(self):
        self.is_running: bool = False
        self.tracked_symbols: List[str] = list(DEFAULT_TRACKED)
        self.worker_task: Optional[asyncio.Task] = None
        self.last_routine_check: str = ""

    def scan_symbol(self, symbol: str) -> Optional[SentinelAlert]:
        try:
            df = get_stock_data(symbol, period="1mo", interval="1d")
            if df is not None and not df.empty:
                df = add_all_indicators(df)

            activity_findings = ActivityDesk.scan(symbol, df)
            technical_findings = TechnicalDesk.scan(symbol, df)
            news_findings = NewsDesk.scan(symbol)
            fundamentals_findings = FundamentalsDesk.scan(symbol)

            all_findings = activity_findings + technical_findings + news_findings + fundamentals_findings
            high_sig = [f for f in all_findings if f.significance in ("HIGH", "CRITICAL")]

            if not high_sig:
                return None

            primary_category = high_sig[0].desk
            if dispatcher.is_cooldown_active(symbol, primary_category):
                return None

            latest_price = float(df.iloc[-1]['Close']) if (df is not None and not df.empty) else 0.0
            review = GeminiSynthesizer.synthesize_alert(symbol, latest_price, all_findings)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            alert = SentinelAlert(
                id=f"alert_{symbol}_{int(datetime.now().timestamp())}",
                symbol=symbol,
                title=f"{symbol.replace('.NS', '')}: {high_sig[0].headline}",
                summary=f"Confluence of {len(all_findings)} desk signals detected: {review.bull_case[:100]}...",
                severity="CRITICAL" if any(f.significance == "CRITICAL" for f in all_findings) else "HIGH",
                findings=all_findings,
                analysis=review,
                created_at=now_str,
                data_as_of=now_str
            )
            dispatcher.record_alert_time(symbol, primary_category)
            return alert
        except Exception:
            return None

    async def run_routine(self, routine_type: str):
        cues = ["GIFT Nifty flat to positive", "US indices closed steady", "Crude oil stable at $78"]
        leaders = ["NIFTY IT (+1.2%)", "NIFTY AUTO (+0.8%)"]
        digest = GeminiSynthesizer.synthesize_market_digest(
            routine_type=routine_type,
            macro_cues=cues,
            stocks_in_focus=self.tracked_symbols[:5],
            sector_leaders=leaders
        )
        dispatcher.save_digest(digest)
        await dispatcher.broadcast_ws({"type": "SENTINEL_DIGEST", "digest": digest.model_dump()})

    async def _loop(self):
        while self.is_running:
            try:
                ist_now = ISTScheduler.get_ist_now()
                time_str = ist_now.strftime("%H:%M")

                # Routine triggers
                if time_str == "08:30" and self.last_routine_check != f"PRE_{ist_now.date()}":
                    self.last_routine_check = f"PRE_{ist_now.date()}"
                    await self.run_routine("PRE_MARKET")
                elif time_str == "12:30" and self.last_routine_check != f"MID_{ist_now.date()}":
                    self.last_routine_check = f"MID_{ist_now.date()}"
                    await self.run_routine("MIDDAY_PULSE")
                elif time_str == "15:40" and self.last_routine_check != f"POST_{ist_now.date()}":
                    self.last_routine_check = f"POST_{ist_now.date()}"
                    await self.run_routine("POST_MARKET_WRAP")

                # Scanning loop
                for symbol in self.tracked_symbols:
                    if not self.is_running:
                        break
                    alert = self.scan_symbol(symbol)
                    if alert:
                        await dispatcher.dispatch_alert(alert)
                    await asyncio.sleep(1)

            except Exception:
                pass
            await asyncio.sleep(15)

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.worker_task = asyncio.create_task(self._loop())

    def stop(self):
        self.is_running = False
        if self.worker_task:
            self.worker_task.cancel()

sentinel_engine = SentinelEngine()
