# Design Specification: AI Market Intelligence Sentinel & Research Desk

- **Date:** 2026-09-29
- **Platform:** StockPulse Pro v5.0 (FastAPI / Python 3.11 / SPA Vanilla JS / TradingView Charts)
- **Status:** Approved for Implementation Planning

---

## 1. Executive Summary & Objective

The **AI Market Intelligence Sentinel** is an institutional-grade, multi-analyst research desk engine built natively into StockPulse Pro. It continuously scans Indian equities (NSE/BSE), identifies high-significance technical, volume, and news anomalies in real-time, runs adversarial Bull vs. Bear validation using Gemini Flash (`gemini-2.0-flash` / `gemini-2.5-flash`), and delivers structured flash intelligence via an in-app Live Feed, Audio/Browser Push Notifications, and Telegram alerts.

Additionally, the engine runs scheduled market intelligence routines (Pre-Market Briefing, Midday Momentum Pulse, Post-Market Wrap) aligned to Indian Standard Time (IST).

---

## 2. Architecture & System Flow

```
+-----------------------------------------------------------------------------------+
|                            FASTAPI BACKEND LIFECYCLE                              |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                 Specialist Data Desks (core/sentinel/desks/)                |  |
|  |  - ActivityDesk: Volume bursts (>2.5x), 5-level depth imbalances, block deals|  |
|  |  - TechnicalDesk: EMA/VWAP breakouts, RSI divergences, Bollinger squeezes   |  |
|  |  - NewsDesk: RSS/Yahoo corporate announcements & news credibility           |  |
|  |  - FundamentalsDesk: Quarterly metrics, valuation (P/E), debt/margin check   |  |
|  +-----------------------------------------------------------------------------+  |
|                                       |                                           |
|                                       v                                           |
|  +-----------------------------------------------------------------------------+  |
|  |                    Deduplication & Cooldown Manager                         |  |
|  |  - 15-minute cooldown per symbol per category to prevent alert fatigue      |  |
|  |  - Confluence Aggregator (combines Volume + Technical + News triggers)     |  |
|  +-----------------------------------------------------------------------------+  |
|                                       | (Confluence Triggers)                     |
|                                       v                                           |
|  +-----------------------------------------------------------------------------+  |
|  |             Gemini Chief Intelligence & Adversarial Reviewer                |  |
|  |  - Model: google-genai Client (gemini-2.0-flash / gemini-2.5-flash)         |  |
|  |  - Strict JSON output: Bull Case vs Bear Case, Key Levels, Confidence Score|  |
|  |  - Strict Data Provenance (Event Time, Data-As-Of, Source attribution)      |  |
|  +-----------------------------------------------------------------------------+  |
|                                       |                                           |
|                                       v                                           |
|  +-----------------------------------------------------------------------------+  |
|  |                       Multi-Channel Dispatcher                              |  |
|  |  - WebSocket (/ws/sentinel): In-App Real-time Feed & Audio Toast Alerts     |  |
|  |  - Telegram Dispatcher: Formatted markdown flash alerts to Telegram DM/Group|  |
|  |  - Data Persistence: data/sentinel_alerts.json & data/sentinel_digests.json |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 3. Detailed Component Specifications

### 3.1 Specialist Desks (`core/sentinel/desks/`)

1. **`ActivityDesk` (`activity_desk.py`)**:
   - Compares current 15m/1D volume against 20-period rolling average volume.
   - Triggers: `VOLUME_SPIKE` when current volume > 2.5x average; `ORDER_BOOK_IMBALANCE` when bid/ask depth skew > 65%.
   - Extracts block deals or institutional buying/selling footprint.

2. **`TechnicalDesk` (`technical_desk.py`)**:
   - Evaluates multi-timeframe indicators:
     - `BREAKOUT`: Price crosses 20 EMA / 50 SMA with ATR expansion.
     - `RSI_DIVERGENCE`: RSI oversold (<30) turning up or overbought (>70) turning down.
     - `BOLLINGER_SQUEEZE_EXPANSION`: Price breaking outside contracted 20,2 Bollinger bands.

3. **`NewsDesk` (`news_desk.py`)**:
   - Pulls recent news and exchange corporate filings.
   - Categorizes source credibility (Exchange Filing > Investor Relations > Financial News).
   - Distinguishes timestamps: `event_time`, `published_time`, `retrieved_time`.

4. **`FundamentalsDesk` (`fundamentals_desk.py`)**:
   - Quick valuation & quality screen: P/E, EPS growth, Debt-to-Equity, quarterly profit trajectory.

---

### 3.2 Data Schemas & Provenance (`core/sentinel/types.py`)

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

class DeskFinding(BaseModel):
    desk: Literal["ACTIVITY", "TECHNICAL", "NEWS", "FUNDAMENTALS"]
    symbol: str
    headline: str
    metrics: dict
    significance: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    timestamp: str

class BullBearReview(BaseModel):
    bull_case: str
    bull_catalysts: List[str]
    bear_case: str
    bear_risks: List[str]
    invalidation_level: Optional[float] = None
    target_resistance: Optional[float] = None
    key_support: Optional[float] = None
    consensus_bias: Literal["STRONG_BULLISH", "MODERATE_BULLISH", "NEUTRAL", "MODERATE_BEARISH", "STRONG_BEARISH"]
    confidence_score: int = Field(ge=0, le=100)

class SentinelAlert(BaseModel):
    id: str
    symbol: str
    title: str
    summary: str
    severity: Literal["INFO", "HIGH", "CRITICAL"]
    findings: List[DeskFinding]
    analysis: BullBearReview
    created_at: str
    data_as_of: str
```

---

### 3.3 Gemini Synthesis Engine (`core/sentinel/synthesizer.py`)

- **Model**: `google.genai` SDK using `gemini-2.0-flash` or `gemini-2.5-flash`.
- **System Prompt**: Enforces institutional research discipline:
  - Separate verified facts from hypotheses.
  - No unsupported claims (never claim price causation from sentiment alone).
  - Explicitly construct both Bull & Bear scenarios before assigning a consensus score.
  - Return clean JSON strictly adhering to `BullBearReview`.

---

### 3.4 Scheduled Market Routines (`core/sentinel/scheduler.py`)

Runs as a non-blocking background task in FastAPI (`asyncio.create_task`):

1. **Pre-Market Briefing (08:30 IST)**:
   - Scans global indices (GIFT Nifty, Asian markets, S&P 500 futures), commodities, and overnight corporate filings.
   - Generates the Daily Market Thesis and key stocks in focus.
2. **Intraday Live Sentinel Scanner (09:15–15:30 IST)**:
   - Runs every 30 seconds across active symbols (NIFTY 50 + User Watchlist).
   - Filters noise via local desk thresholds before invoking Gemini for qualified anomalies.
3. **Midday Momentum Pulse (12:30 IST)**:
   - Summarizes morning sector rotation, top volume gainers, and morning breakout sustainability.
4. **Post-Market Wrap (15:40 IST)**:
   - Summarizes market closing breadth, final FII/DII institutional net numbers, and key lessons/setups for next day.

---

### 3.5 Delivery & Dispatcher (`core/sentinel/dispatcher.py`)

- **WebSocket `/ws/sentinel`**:
  - Broadcasts structured JSON events to all active in-app dashboard sessions.
- **Telegram Bot Dispatcher**:
  - If `data/telegram_config.json` is configured, automatically formats high-priority alerts with emoji badges, Bull/Bear thesis, and target/support levels and sends to the user's Telegram chat.
- **Deduplication**:
  - Implements an in-memory 15-minute sliding window per `(symbol, alert_type)` to avoid alert spamming.

---

### 3.6 Frontend: In-App AI Intelligence Desk (`static/`)

1. **Navigation**: Add a prominent **"🧠 AI Intelligence Desk"** tab to the navigation header.
2. **Live Feed Stream**:
   - Real-time card feed showing new alerts as they stream in.
   - Severity badges (`CRITICAL`, `HIGH`, `INFO`), Bull/Bear probability meters, and quick "Inspect Chart" action buttons.
3. **Daily Routine Digest Drawer**:
   - Collapsible tabs for Pre-Market Briefing, Midday Pulse, and Post-Market Wrap.
4. **On-Demand Stock Research Investigator**:
   - Symbol search bar allowing the user to trigger an immediate deep multi-desk investigation and view the full Bull vs Bear dossier.
5. **Interactive Controls**:
   - Audio Chime toggle, Browser Desktop Notification toggle, and Telegram Bot setup modal.

---

## 4. Testing & Acceptance Criteria

1. **Desk Detection Tests**:
   - Unit tests for `ActivityDesk`, `TechnicalDesk`, and `NewsDesk` validating threshold triggers and edge cases.
2. **Synthesis & Schema Enforcement**:
   - Test Gemini synthesizer with mocked and live data ensuring valid JSON schemas and non-empty Bull/Bear fields.
3. **Deduplication & Cooldown Verification**:
   - Test that identical triggers for the same symbol within 15 minutes are suppressed.
4. **Scheduled Routines Validation**:
   - Verify IST time calculation and manual execution trigger endpoints for pre-market, midday, and post-market routines.
5. **WebSocket & UI Integration**:
   - Verify real-time alert reception in browser, audio play, and rendering in the AI Intelligence Desk tab.
