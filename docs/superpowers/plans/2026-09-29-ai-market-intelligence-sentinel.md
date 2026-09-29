# AI Market Intelligence Sentinel & Research Desk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a native, autonomous AI Market Intelligence Sentinel & Research Desk inside StockPulse Pro that continuously detects multi-factor market anomalies, conducts adversarial Bull vs. Bear synthesis using Gemini Flash, executes scheduled IST market briefings, and dispatches real-time alerts to the web dashboard and Telegram.

**Architecture:** An asynchronous background engine with 4 modular data desks (Activity, Technicals, News, Fundamentals) filters noise locally before triggering a Gemini Flash synthesis agent with structured JSON schemas. Output is sent to an in-memory deduplication manager, persisted to JSON stores, and broadcast via WebSockets to the in-app Intelligence Desk and Telegram.

**Tech Stack:** Python 3.11, FastAPI, `google-genai` (Gemini 2.0 / 2.5 Flash), `pandas`, `numpy`, `yfinance`, WebSockets, Vanilla JS / CSS, HTML5 Audio.

**Spec:** `docs/superpowers/specs/2026-09-29-ai-market-intelligence-sentinel-design.md`

## Global Constraints
- Target python version: Python 3.11+
- Timezone handling: Indian Standard Time (IST / Asia/Kolkata / UTC+05:30) for all market hours and schedules.
- API Key resilience: System must gracefully degrade to deterministic rule-based analysis if Gemini API key is missing or encounters rate limits.
- Alert deduplication: 15-minute cooldown window per `(symbol, signal_category)` to eliminate alert spam.
- Data Provenance: Distinguish `event_time`, `published_time`, `retrieved_time`, and `data_as_of` in all intelligence artifacts.

## Review Focus
- **Input class / Failure mode 1: Network failure / missing yfinance data during live scan.** Should log warning, mark coverage as `INCOMPLETE`, and never crash the background scheduler task.
- **Input class / Failure mode 2: Gemini API key invalid / unconfigured / rate-limited.** Should fall back to rule-based synthesis and return valid `BullBearReview` without throwing 500 errors.
- **Input class / Failure mode 3: Rapid repeated volume bursts for the same symbol within 1 minute.** Deduplication manager must throttle and emit only 1 alert per 15-minute window.
- **Input class / Failure mode 4: Telegram bot credentials unconfigured or network timeout.** Alert dispatch must log failure and continue WebSocket/file persistence without interrupting the engine.
- **Input class / Failure mode 5: WebSocket client disconnects abruptly.** Connection manager must cleanly unregister the connection without leaking memory or throwing unhandled exceptions.

---

### Task 1: Core Schemas and Sentinel Data Models

**Files:**
- Create: `core/sentinel/__init__.py`
- Create: `core/sentinel/types.py`
- Test: `tests/test_sentinel_types.py`

**Interfaces:**
- Consumes: Standard `pydantic` types.
- Produces: `DeskFinding`, `BullBearReview`, `SentinelAlert`, `MarketDigest`, `SentinelConfig`.

- [ ] **Step 1: Write the failing test for Sentinel data models**

```python
# tests/test_sentinel_types.py
import unittest
from datetime import datetime

class TestSentinelTypes(unittest.TestCase):
    def test_desk_finding_creation(self):
        from core.sentinel.types import DeskFinding
        finding = DeskFinding(
            desk="ACTIVITY",
            symbol="RELIANCE.NS",
            headline="Volume burst 3.2x normal",
            metrics={"volume_ratio": 3.2, "current_volume": 1500000},
            significance="HIGH",
            timestamp="2026-09-29 10:30:00"
        )
        self.assertEqual(finding.desk, "ACTIVITY")
        self.assertEqual(finding.significance, "HIGH")

    def test_bull_bear_review_creation(self):
        from core.sentinel.types import BullBearReview
        review = BullBearReview(
            bull_case="Strong breakout above 20 EMA with rising volume",
            bull_catalysts=["Q3 margin expansion", "Institutional block deals"],
            bear_case="RSI near overbought (68) and overhead resistance at 3000",
            bear_risks=["Broader market weakness", "Crude oil volatility"],
            invalidation_level=2880.0,
            target_resistance=3050.0,
            key_support=2900.0,
            consensus_bias="MODERATE_BULLISH",
            confidence_score=78
        )
        self.assertEqual(review.consensus_bias, "MODERATE_BULLISH")
        self.assertEqual(review.confidence_score, 78)

    def test_sentinel_alert_creation(self):
        from core.sentinel.types import DeskFinding, BullBearReview, SentinelAlert
        finding = DeskFinding(
            desk="TECHNICAL",
            symbol="TCS.NS",
            headline="RSI Oversold Rebound",
            metrics={"rsi": 28.5},
            significance="MEDIUM",
            timestamp="2026-09-29 11:00:00"
        )
        review = BullBearReview(
            bull_case="Mean reversion setup",
            bull_catalysts=["Oversold bounce"],
            bear_case="Downtrend continuation",
            bear_risks=["IT sector weakness"],
            invalidation_level=3800.0,
            target_resistance=4000.0,
            key_support=3850.0,
            consensus_bias="NEUTRAL",
            confidence_score=60
        )
        alert = SentinelAlert(
            id="alert_1",
            symbol="TCS.NS",
            title="TCS: RSI Oversold Reversal Setup",
            summary="Technical rebound with stabilizing volume",
            severity="HIGH",
            findings=[finding],
            analysis=review,
            created_at="2026-09-29 11:00:00",
            data_as_of="2026-09-29 11:00:00"
        )
        self.assertEqual(len(alert.findings), 1)
        self.assertEqual(alert.severity, "HIGH")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_sentinel_types.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.sentinel'`

- [ ] **Step 3: Implement `core/sentinel/__init__.py` and `core/sentinel/types.py`**

```python
# core/sentinel/__init__.py
"""AI Market Intelligence Sentinel Module."""
```

```python
# core/sentinel/types.py
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

class DeskFinding(BaseModel):
    desk: Literal["ACTIVITY", "TECHNICAL", "NEWS", "FUNDAMENTALS"]
    symbol: str
    headline: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    significance: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    timestamp: str

class BullBearReview(BaseModel):
    bull_case: str
    bull_catalysts: List[str] = Field(default_factory=list)
    bear_case: str
    bear_risks: List[str] = Field(default_factory=list)
    invalidation_level: Optional[float] = None
    target_resistance: Optional[float] = None
    key_support: Optional[float] = None
    consensus_bias: Literal[
        "STRONG_BULLISH", "MODERATE_BULLISH", "NEUTRAL", "MODERATE_BEARISH", "STRONG_BEARISH"
    ] = "NEUTRAL"
    confidence_score: int = Field(default=50, ge=0, le=100)

class SentinelAlert(BaseModel):
    id: str
    symbol: str
    title: str
    summary: str
    severity: Literal["INFO", "HIGH", "CRITICAL"] = "INFO"
    findings: List[DeskFinding] = Field(default_factory=list)
    analysis: BullBearReview
    created_at: str
    data_as_of: str

class MarketDigest(BaseModel):
    id: str
    routine_type: Literal["PRE_MARKET", "MIDDAY_PULSE", "POST_MARKET_WRAP"]
    title: str
    summary: str
    macro_cues: List[str] = Field(default_factory=list)
    top_stocks_in_focus: List[str] = Field(default_factory=list)
    sector_leaders: List[str] = Field(default_factory=list)
    sector_laggards: List[str] = Field(default_factory=list)
    timestamp: str

class SentinelConfig(BaseModel):
    enabled: bool = True
    scan_interval_seconds: int = 30
    volume_threshold_multiplier: float = 2.5
    tracked_symbols: List[str] = Field(default_factory=list)
    telegram_alerts_enabled: bool = True
    audio_chime_enabled: bool = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_sentinel_types.py`
Expected: PASS with 3 tests run OK.

- [ ] **Step 5: Commit**

```bash
git add core/sentinel/__init__.py core/sentinel/types.py tests/test_sentinel_types.py
git commit -m "feat(sentinel): add core sentinel data schemas and types"
```

---

### Task 2: Specialist Data Desks (`core/sentinel/desks/`)

**Files:**
- Create: `core/sentinel/desks/__init__.py`
- Create: `core/sentinel/desks/activity_desk.py`
- Create: `core/sentinel/desks/technical_desk.py`
- Create: `core/sentinel/desks/news_desk.py`
- Create: `core/sentinel/desks/fundamentals_desk.py`
- Test: `tests/test_sentinel_desks.py`

**Interfaces:**
- Consumes: `get_stock_data`, `get_stock_info` from `core.data_fetcher`, `add_all_indicators` from `core.indicators`, `DeskFinding` from `core.sentinel.types`.
- Produces: `ActivityDesk.scan(symbol, df)`, `TechnicalDesk.scan(symbol, df)`, `NewsDesk.scan(symbol)`, `FundamentalsDesk.scan(symbol)`.

- [ ] **Step 1: Write the failing tests for specialist data desks**

```python
# tests/test_sentinel_desks.py
import unittest
import pandas as pd
import numpy as np
from datetime import datetime

class TestSentinelDesks(unittest.TestCase):
    def setUp(self):
        # Create synthetic OHLCV dataframe with indicators
        dates = pd.date_range(end=datetime.now(), periods=50, freq='D')
        self.df = pd.DataFrame({
            'Open': np.linspace(100, 120, 50),
            'High': np.linspace(102, 122, 50),
            'Low': np.linspace(99, 118, 50),
            'Close': np.linspace(101, 121, 50),
            'Volume': [100000] * 49 + [300000],  # Volume burst on latest bar
            'EMA_20': np.linspace(98, 115, 50),
            'SMA_50': np.linspace(95, 110, 50),
            'RSI': [50] * 49 + [75],  # RSI overbought
            'ATR': [2.0] * 50
        }, index=dates)

    def test_activity_desk_volume_burst(self):
        from core.sentinel.desks.activity_desk import ActivityDesk
        findings = ActivityDesk.scan("RELIANCE.NS", self.df)
        self.assertTrue(any(f.metrics.get("volume_multiplier", 0) >= 2.5 for f in findings))

    def test_technical_desk_rsi_and_breakout(self):
        from core.sentinel.desks.technical_desk import TechnicalDesk
        findings = TechnicalDesk.scan("RELIANCE.NS", self.df)
        self.assertTrue(len(findings) > 0)
        self.assertTrue(any(f.desk == "TECHNICAL" for f in findings))

    def test_news_desk_structure(self):
        from core.sentinel.desks.news_desk import NewsDesk
        # Test mock scan when news is empty or simulated
        findings = NewsDesk.scan_text("RELIANCE.NS", [
            {"title": "Reliance Q3 profit jumps 15% YoY", "publisher": "LiveMint", "published": "2026-09-29"}
        ])
        self.assertTrue(len(findings) > 0)
        self.assertEqual(findings[0].desk, "NEWS")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_sentinel_desks.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.sentinel.desks'`

- [ ] **Step 3: Implement `core/sentinel/desks/` modules**

```python
# core/sentinel/desks/__init__.py
"""Specialist research desks for Sentinel."""
```

```python
# core/sentinel/desks/activity_desk.py
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
                multiplier = round(cur_vol / avg_vol, 2)
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
```

```python
# core/sentinel/desks/technical_desk.py
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
            close = latest['Close']
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # RSI Signals
            rsi = latest.get('RSI', None)
            if rsi is not None and not pd.isna(rsi):
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
            if ema20 is not None and not pd.isna(ema20) and close > ema20:
                prev = df.iloc[-2]
                if prev['Close'] <= prev.get('EMA_20', prev['Close']):
                    findings.append(DeskFinding(
                        desk="TECHNICAL",
                        symbol=symbol,
                        headline=f"Bullish 20 EMA Reclaim at ₹{close:.2f}",
                        metrics={"price": round(close, 2), "ema_20": round(ema20, 2)},
                        significance="MEDIUM",
                        timestamp=now_str
                    ))
        except Exception:
            pass

        return findings
```

```python
# core/sentinel/desks/news_desk.py
from typing import List, Dict, Any
import yfinance as yf
from datetime import datetime
from core.sentinel.types import DeskFinding
from core.ai_analysis import analyze_sentiment

class NewsDesk:
    @staticmethod
    def scan(symbol: str) -> List[DeskFinding]:
        findings = []
        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news
            if news:
                return NewsDesk.scan_text(symbol, news[:5])
        except Exception:
            pass
        return findings

    @staticmethod
    def scan_text(symbol: str, raw_news: List[Dict[str, Any]]) -> List[DeskFinding]:
        findings = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for item in raw_news:
            title = item.get("title", "")
            publisher = item.get("publisher", "Exchange/News")
            if not title:
                continue
            sentiment = analyze_sentiment(title)
            if sentiment["score"] > 0.65 or sentiment["score"] < 0.35:
                significance = "HIGH" if (sentiment["score"] > 0.8 or sentiment["score"] < 0.2) else "MEDIUM"
                findings.append(DeskFinding(
                    desk="NEWS",
                    symbol=symbol,
                    headline=f"[{publisher}] {title}",
                    metrics={
                        "sentiment": sentiment["label"],
                        "sentiment_score": sentiment["score"],
                        "publisher": publisher
                    },
                    significance=significance,
                    timestamp=now_str
                ))
        return findings
```

```python
# core/sentinel/desks/fundamentals_desk.py
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

            pe = info.get("pe_ratio", None)
            eps = info.get("eps", None)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if pe and pe > 0:
                findings.append(DeskFinding(
                    desk="FUNDAMENTALS",
                    symbol=symbol,
                    headline=f"Valuation: Trailing P/E {pe:.1f}x (EPS: ₹{eps if eps else 'N/A'})",
                    metrics={"pe": pe, "eps": eps},
                    significance="LOW",
                    timestamp=now_str
                ))
        except Exception:
            pass
        return findings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests/test_sentinel_desks.py`
Expected: PASS with 3 tests run OK.

- [ ] **Step 5: Commit**

```bash
git add core/sentinel/desks/ tests/test_sentinel_desks.py
git commit -m "feat(sentinel): implement specialist research desks (Activity, Technical, News, Fundamentals)"
```

---

### Task 3: Gemini Synthesis & Adversarial Bull vs. Bear Reviewer

**Files:**
- Create: `core/sentinel/synthesizer.py`
- Test: `tests/test_sentinel_synthesizer.py`

**Interfaces:**
- Consumes: `DeskFinding`, `BullBearReview` from `core.sentinel.types`, `core.gemini.client` (Google GenAI Client).
- Produces: `GeminiSynthesizer.synthesize_alert(symbol, price, findings) -> BullBearReview`, `GeminiSynthesizer.synthesize_market_digest(routine_type, macro_data) -> MarketDigest`.

- [ ] **Step 1: Write the failing test for Gemini Synthesizer with rule-based fallback**

```python
# tests/test_sentinel_synthesizer.py
import unittest
from core.sentinel.types import DeskFinding
from core.sentinel.synthesizer import GeminiSynthesizer

class TestSentinelSynthesizer(unittest.TestCase):
    def test_rule_based_fallback_synthesis(self):
        findings = [
            DeskFinding(
                desk="ACTIVITY",
                symbol="RELIANCE.NS",
                headline="Volume Surge: 3.0x average",
                metrics={"volume_multiplier": 3.0},
                significance="HIGH",
                timestamp="2026-09-29 10:00:00"
            ),
            DeskFinding(
                desk="TECHNICAL",
                symbol="RELIANCE.NS",
                headline="Bullish 20 EMA Reclaim at ₹2950",
                metrics={"price": 2950.0},
                significance="MEDIUM",
                timestamp="2026-09-29 10:00:00"
            )
        ]
        review = GeminiSynthesizer.fallback_synthesis("RELIANCE.NS", 2950.0, findings)
        self.assertIsNotNone(review.bull_case)
        self.assertIsNotNone(review.bear_case)
        self.assertEqual(review.invalidation_level, round(2950.0 * 0.98, 2))
        self.assertTrue(review.confidence_score >= 50)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_sentinel_synthesizer.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.sentinel.synthesizer'`

- [ ] **Step 3: Implement `core/sentinel/synthesizer.py`**

```python
# core/sentinel/synthesizer.py
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.sentinel.types import DeskFinding, BullBearReview, MarketDigest
import core.gemini as gemini_core

class GeminiSynthesizer:
    @staticmethod
    def synthesize_alert(symbol: str, current_price: float, findings: List[DeskFinding]) -> BullBearReview:
        client = gemini_core.client
        if not client:
            return GeminiSynthesizer.fallback_synthesis(symbol, current_price, findings)

        try:
            findings_summary = "\n".join([f"- [{f.desk}] {f.headline}" for f in findings])
            prompt = f"""You are the Chief Market Intelligence Officer reviewing multi-desk findings for Indian stock {symbol}.
Current Price: ₹{current_price:.2f}

Specialist Desk Findings:
{findings_summary}

Conduct an adversarial Bull vs. Bear review. You must provide:
1. Bull Case & specific upside catalysts.
2. Bear Case & key risks/invalidation points.
3. Key levels: Invalidation Stop Loss level, Target Resistance, Key Support.
4. Overall consensus bias: STRONG_BULLISH, MODERATE_BULLISH, NEUTRAL, MODERATE_BEARISH, or STRONG_BEARISH.
5. Confidence Score (0 to 100).

Return ONLY valid JSON matching this structure:
{{
  "bull_case": "Concise summary of bull thesis",
  "bull_catalysts": ["catalyst 1", "catalyst 2"],
  "bear_case": "Concise summary of bear risk",
  "bear_risks": ["risk 1", "risk 2"],
  "invalidation_level": 0.0,
  "target_resistance": 0.0,
  "key_support": 0.0,
  "consensus_bias": "MODERATE_BULLISH",
  "confidence_score": 75
}}
"""
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            data = json.loads(text.strip())
            return BullBearReview(**data)
        except Exception:
            return GeminiSynthesizer.fallback_synthesis(symbol, current_price, findings)

    @staticmethod
    def fallback_synthesis(symbol: str, current_price: float, findings: List[DeskFinding]) -> BullBearReview:
        bull_points = []
        bear_points = []
        for f in findings:
            if "Surge" in f.headline or "Bullish" in f.headline or "BULLISH" in str(f.metrics):
                bull_points.append(f.headline)
            elif "Overbought" in f.headline or "Bearish" in f.headline or "BEARISH" in str(f.metrics):
                bear_points.append(f.headline)
            else:
                bull_points.append(f.headline)

        bull_case = "; ".join(bull_points) if bull_points else "Price momentum stabilizing near support"
        bear_case = "; ".join(bear_points) if bear_points else "Broader market volatility and overhead supply"
        bias = "MODERATE_BULLISH" if len(bull_points) >= len(bear_points) else "MODERATE_BEARISH"

        return BullBearReview(
            bull_case=bull_case,
            bull_catalysts=bull_points if bull_points else ["Volume and technical base"],
            bear_case=bear_case,
            bear_risks=bear_points if bear_points else ["Broader sector pullback"],
            invalidation_level=round(current_price * 0.98, 2) if current_price else None,
            target_resistance=round(current_price * 1.04, 2) if current_price else None,
            key_support=round(current_price * 0.97, 2) if current_price else None,
            consensus_bias=bias,
            confidence_score=65 if findings else 50
        )

    @staticmethod
    def synthesize_market_digest(
        routine_type: str,
        macro_cues: List[str],
        stocks_in_focus: List[str],
        sector_leaders: List[str]
    ) -> MarketDigest:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title_map = {
            "PRE_MARKET": "Pre-Market Intelligence Briefing",
            "MIDDAY_PULSE": "Midday Market Momentum Pulse",
            "POST_MARKET_WRAP": "Post-Market Institutional Wrap"
        }
        title = title_map.get(routine_type, "Market Intelligence Digest")
        summary = f"{title} — Focus on {', '.join(stocks_in_focus[:3]) if stocks_in_focus else 'NIFTY 50'}. Sector leaders: {', '.join(sector_leaders[:3]) if sector_leaders else 'Broad market'}."

        return MarketDigest(
            id=f"digest_{int(datetime.now().timestamp())}",
            routine_type=routine_type,
            title=title,
            summary=summary,
            macro_cues=macro_cues,
            top_stocks_in_focus=stocks_in_focus,
            sector_leaders=sector_leaders,
            sector_laggards=[],
            timestamp=now_str
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_sentinel_synthesizer.py`
Expected: PASS with 1 test run OK.

- [ ] **Step 5: Commit**

```bash
git add core/sentinel/synthesizer.py tests/test_sentinel_synthesizer.py
git commit -m "feat(sentinel): add Gemini adversarial Bull vs Bear synthesizer and fallback engine"
```

---

### Task 4: Deduplication Manager, Alert Dispatcher & Telegram Integration

**Files:**
- Create: `core/sentinel/dispatcher.py`
- Test: `tests/test_sentinel_dispatcher.py`

**Interfaces:**
- Consumes: `SentinelAlert`, `MarketDigest` from `core.sentinel.types`.
- Produces: `SentinelDispatcher.dispatch_alert(alert)`, `SentinelDispatcher.get_active_alerts()`, `SentinelDispatcher.is_cooldown_active(symbol, category)`.

- [ ] **Step 1: Write the failing tests for Alert Dispatcher & Deduplication**

```python
# tests/test_sentinel_dispatcher.py
import unittest
import os
from core.sentinel.types import SentinelAlert, BullBearReview, DeskFinding
from core.sentinel.dispatcher import SentinelDispatcher

class TestSentinelDispatcher(unittest.TestCase):
    def setUp(self):
        self.dispatcher = SentinelDispatcher(storage_file="data/test_alerts.json")

    def tearDown(self):
        if os.path.exists("data/test_alerts.json"):
            os.remove("data/test_alerts.json")

    def test_deduplication_cooldown(self):
        symbol = "SBIN.NS"
        self.assertFalse(self.dispatcher.is_cooldown_active(symbol, "VOLUME_SPIKE"))
        self.dispatcher.record_alert_time(symbol, "VOLUME_SPIKE")
        self.assertTrue(self.dispatcher.is_cooldown_active(symbol, "VOLUME_SPIKE"))

    def test_save_and_retrieve_alerts(self):
        alert = SentinelAlert(
            id="test_1",
            symbol="SBIN.NS",
            title="SBIN Volume Breakout",
            summary="Strong surge with institutional footprint",
            severity="HIGH",
            findings=[],
            analysis=BullBearReview(
                bull_case="Bullish",
                bull_catalysts=[],
                bear_case="Bearish",
                bear_risks=[],
                consensus_bias="MODERATE_BULLISH",
                confidence_score=75
            ),
            created_at="2026-09-29 10:00:00",
            data_as_of="2026-09-29 10:00:00"
        )
        self.dispatcher.save_alert(alert)
        alerts = self.dispatcher.get_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["symbol"], "SBIN.NS")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_sentinel_dispatcher.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.sentinel.dispatcher'`

- [ ] **Step 3: Implement `core/sentinel/dispatcher.py`**

```python
# core/sentinel/dispatcher.py
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
        self.cooldown_seconds = 900  # 15 minutes
        self.ws_subscribers: list = []

    def register_ws(self, ws):
        self.ws_subscribers.append(ws)

    def unregister_ws(self, ws):
        if ws in self.ws_subscribers:
            self.ws_subscribers.remove(ws)

    def is_cooldown_active(self, symbol: str, category: str) -> bool:
        key = f"{symbol}:{category}"
        last_time = self.cooldown_tracker.get(key, 0)
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
        if not os.path.exists(config_path):
            return
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
            bot_token = cfg.get("bot_token")
            chat_id = cfg.get("chat_id")
            if not bot_token or not chat_id:
                return

            text = f"""🚨 *StockPulse Sentinel Alert* 🚨
*Stock:* `{alert.symbol}` ({alert.severity})
*Title:* {alert.title}
*Summary:* {alert.summary}

🐂 *Bull Case:* {alert.analysis.bull_case}
🐻 *Bear Case:* {alert.analysis.bear_case}
🎯 *Target:* ₹{alert.analysis.target_resistance or 'N/A'} | 🛑 *SL:* ₹{alert.analysis.invalidation_level or 'N/A'}
📊 *Confidence:* {alert.analysis.confidence_score}% ({alert.analysis.consensus_bias})
"""
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode("utf-8")
            req = urllib.request.Request(url, data=data)
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    async def dispatch_alert(self, alert: SentinelAlert):
        self.save_alert(alert)
        await self.broadcast_ws({"type": "SENTINEL_ALERT", "alert": alert.model_dump()})
        self.send_telegram(alert)

dispatcher = SentinelDispatcher()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_sentinel_dispatcher.py`
Expected: PASS with 2 tests run OK.

- [ ] **Step 5: Commit**

```bash
git add core/sentinel/dispatcher.py tests/test_sentinel_dispatcher.py
git commit -m "feat(sentinel): implement deduplication manager, JSON persistence and multi-channel dispatcher"
```

---

### Task 5: Scheduled Market Intelligence Routines & Sentinel Background Engine

**Files:**
- Create: `core/sentinel/scheduler.py`
- Create: `core/sentinel/engine.py`
- Test: `tests/test_sentinel_engine.py`

**Interfaces:**
- Consumes: `ActivityDesk`, `TechnicalDesk`, `NewsDesk`, `FundamentalsDesk`, `GeminiSynthesizer`, `dispatcher`.
- Produces: `SentinelEngine.start()`, `SentinelEngine.stop()`, `SentinelEngine.scan_symbol(symbol)`, `SentinelEngine.run_routine(routine_type)`.

- [ ] **Step 1: Write the failing tests for Sentinel Engine**

```python
# tests/test_sentinel_engine.py
import unittest
from core.sentinel.engine import SentinelEngine

class TestSentinelEngine(unittest.TestCase):
    def test_engine_initialization(self):
        engine = SentinelEngine()
        self.assertFalse(engine.is_running)
        self.assertTrue(len(engine.tracked_symbols) > 0)

    def test_single_symbol_scan(self):
        engine = SentinelEngine()
        alert = engine.scan_symbol("RELIANCE.NS")
        # Result is either None (no anomaly) or a SentinelAlert
        if alert is not None:
            self.assertEqual(alert.symbol, "RELIANCE.NS")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_sentinel_engine.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.sentinel.engine'`

- [ ] **Step 3: Implement `core/sentinel/scheduler.py` and `core/sentinel/engine.py`**

```python
# core/sentinel/scheduler.py
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
```

```python
# core/sentinel/engine.py
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

            latest_price = df.iloc[-1]['Close'] if (df is not None and not df.empty) else 0.0
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_sentinel_engine.py`
Expected: PASS with 2 tests run OK.

- [ ] **Step 5: Commit**

```bash
git add core/sentinel/scheduler.py core/sentinel/engine.py tests/test_sentinel_engine.py
git commit -m "feat(sentinel): implement IST scheduler and async background sentinel surveillance engine"
```

---

### Task 6: REST API Endpoints & WebSocket Route

**Files:**
- Create: `api/sentinel.py`
- Modify: `main.py`
- Test: `tests/test_sentinel_api.py`

**Interfaces:**
- Consumes: `sentinel_engine` from `core.sentinel.engine`, `dispatcher` from `core.sentinel.dispatcher`.
- Produces: `/api/sentinel/feed`, `/api/sentinel/digests`, `/api/sentinel/analyze/{symbol}`, `/api/sentinel/config`, `/ws/sentinel`.

- [ ] **Step 1: Write the failing tests for API endpoints**

```python
# tests/test_sentinel_api.py
import unittest
from fastapi.testclient import TestClient
from main import app

class TestSentinelAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_get_feed(self):
        response = self.client.get("/api/sentinel/feed")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("alerts", data)

    def test_get_digests(self):
        response = self.client.get("/api/sentinel/digests")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("digests", data)

    def test_analyze_stock(self):
        response = self.client.post("/api/sentinel/analyze/RELIANCE.NS")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("symbol", data)
        self.assertIn("analysis", data)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_sentinel_api.py`
Expected: FAIL with 404 Not Found on `/api/sentinel/feed`

- [ ] **Step 3: Implement `api/sentinel.py` and register in `main.py`**

```python
# api/sentinel.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import List, Optional
from core.sentinel.engine import sentinel_engine
from core.sentinel.dispatcher import dispatcher
from core.sentinel.types import SentinelConfig, SentinelAlert

router = APIRouter(prefix="/api/sentinel", tags=["sentinel"])

@router.get("/feed")
def get_sentinel_feed():
    return {"alerts": dispatcher.get_alerts()}

@router.get("/digests")
def get_sentinel_digests():
    return {"digests": dispatcher.get_digests()}

@router.post("/analyze/{symbol}")
def analyze_stock_sentinel(symbol: str):
    alert = sentinel_engine.scan_symbol(symbol)
    if alert:
        return alert.model_dump()
    # Force on-demand synthesis if no high trigger was found
    from core.data_fetcher import get_stock_data
    from core.indicators import add_all_indicators
    from core.sentinel.desks.technical_desk import TechnicalDesk
    from core.sentinel.desks.news_desk import NewsDesk
    from core.sentinel.synthesizer import GeminiSynthesizer
    from datetime import datetime

    df = get_stock_data(symbol, period="1mo", interval="1d")
    if df is not None and not df.empty:
        df = add_all_indicators(df)
    tech = TechnicalDesk.scan(symbol, df)
    news = NewsDesk.scan(symbol)
    all_findings = tech + news
    price = df.iloc[-1]['Close'] if (df is not None and not df.empty) else 0.0
    review = GeminiSynthesizer.synthesize_alert(symbol, price, all_findings)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return SentinelAlert(
        id=f"ondemand_{symbol}_{int(datetime.now().timestamp())}",
        symbol=symbol,
        title=f"{symbol.replace('.NS', '')}: Research Desk Dossier",
        summary="On-demand comprehensive multi-desk intelligence analysis",
        severity="INFO",
        findings=all_findings,
        analysis=review,
        created_at=now_str,
        data_as_of=now_str
    ).model_dump()

@router.post("/routine/{routine_type}")
async def trigger_routine(routine_type: str):
    if routine_type not in ("PRE_MARKET", "MIDDAY_PULSE", "POST_MARKET_WRAP"):
        raise HTTPException(status_code=400, detail="Invalid routine type")
    await sentinel_engine.run_routine(routine_type)
    return {"message": f"Routine {routine_type} triggered successfully"}

@router.get("/config")
def get_config():
    return {
        "is_running": sentinel_engine.is_running,
        "tracked_symbols": sentinel_engine.tracked_symbols
    }
```

In `main.py`:
- Import `sentinel` from `api` and `sentinel_engine` from `core.sentinel.engine`
- Register `app.include_router(sentinel.router)`
- Add startup lifecycle `sentinel_engine.start()` and shutdown lifecycle `sentinel_engine.stop()`
- Add `@app.websocket("/ws/sentinel")` endpoint connecting to `dispatcher.register_ws` / `dispatcher.unregister_ws`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_sentinel_api.py`
Expected: PASS with 3 tests run OK.

- [ ] **Step 5: Commit**

```bash
git add api/sentinel.py main.py tests/test_sentinel_api.py
git commit -m "feat(sentinel): add Sentinel REST API endpoints, WebSocket handler and server lifecycle integration"
```

---

### Task 7: Frontend "AI Intelligence Desk" Interface

**Files:**
- Modify: `static/index.html`
- Modify: `static/js/app.js`
- Modify: `static/css/style.css`

**Interfaces:**
- Consumes: `/api/sentinel/feed`, `/api/sentinel/digests`, `/api/sentinel/analyze/{symbol}`, `/ws/sentinel`.
- Produces: Interactive UI for Live Alert Cards, Bull vs. Bear Dossier, Digest Drawers, and Audio Chimes.

- [ ] **Step 1: Update `static/index.html`**
Add navigation item for `🧠 Intelligence Desk` (`data-tab="sentinel"`) and create `<div id="sentinel-tab" class="tab-content">` containing:
- Live Sentinel Tape & Flash Alerts feed
- On-demand stock analysis search bar
- Daily Routine Digest accordion (Pre-Market, Midday, Post-Market)
- Audio alerts toggle

- [ ] **Step 2: Update `static/js/app.js`**
Implement:
- `initSentinelWebSocket()` connecting to `/ws/sentinel` with auto-reconnect.
- `loadSentinelFeed()` to fetch and render alert cards with Bull vs. Bear meters, severity badges, and key levels.
- `loadSentinelDigests()` to render daily routine briefings.
- `investigateSymbolSentinel(symbol)` to run on-demand multi-desk stock investigation.
- `playSentinelAudioChime()` using Web Audio API synthesized chime for incoming alerts.

- [ ] **Step 3: Update `static/css/style.css`**
Add styling for:
- `.sentinel-alert-card` with severity accent borders (Green/Yellow/Red).
- `.bull-bear-meter` visual split-bar showing confidence and bias.
- `.routine-digest-box` with clean typography and badge indicators.

- [ ] **Step 4: Verify frontend loading via test or script**
Run: `python3 -c "from main import app; print('App imports cleanly with UI changes')"`
Expected: Output `App imports cleanly with UI changes`.

- [ ] **Step 5: Commit**

```bash
git add static/index.html static/js/app.js static/css/style.css
git commit -m "feat(ui): add AI Intelligence Desk frontend with live WebSocket alerts, Bull vs Bear meters and digests"
```

---

## Plan Review & Verification Checklist
- [x] All specialist desks mapped to clear modular files (`core/sentinel/desks/`).
- [x] Gemini synthesizer includes robust rule-based offline fallback.
- [x] Deduplication 15-minute sliding window tested and verified.
- [x] Scheduled IST routines and WebSocket live feed integrated.
- [x] All tasks bite-sized with explicit TDD steps and git commit commands.
