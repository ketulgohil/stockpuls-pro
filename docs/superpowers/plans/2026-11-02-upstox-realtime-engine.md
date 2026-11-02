# Upstox Real-Time Market Feed & Intraday Trading Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate Upstox API v2 / v3 and Inngest event workflows across StockPulse Pro to deliver sub-second real-time quotes, 5-level DOM depth, Opening Range Breakout (ORB) scanning, confluence buy signals, live paper trading, and durable background event processing.

**Architecture:** A high-frequency asynchronous market data engine polls Upstox batch quotes (all 50 NIFTY equities in 1 single HTTP GET request) and maintains an in-memory tick and rolling 5-minute candle cache. This powers deterministic ORB and Buy Signal detectors, real 5-level market depth order books, and a live paper trading ledger with MTM tracking and stop-loss triggers. High-priority events and scheduled routines are orchestrated via Inngest durable functions and broadcasted via dedicated WebSockets (`/ws/upstox/live`).

**Tech Stack:** Python 3.11, FastAPI, Upstox API v2/v3, Inngest SDK, HTTPX (AsyncClient), WebSockets, Pydantic v2, Vanilla JS, HTML5 Audio API.

**Spec:** `docs/superpowers/specs/2026-11-02-upstox-realtime-engine-design.md`

## Global Constraints

- **Python Version:** Python 3.9+ / 3.11 compatible.
- **Upstox Access Token:** Loaded securely from `.env` or environment as `UPSTOX_ACCESS_TOKEN`.
- **Inngest Credentials:** `INNGEST_EVENT_KEY` and `INNGEST_SIGNING_KEY` configured via `.env`.
- **Zero Breaking Changes:** Existing routes (`/ws/live-prices`, `/ws/sentinel`, `/api/stocks/*`, `/api/sentinel/*`) must continue operating without regression.
- **Performance:** NIFTY 50 quotes fetched in a single batch request under 250ms latency.
- **Timezone:** All market session calculations must strictly follow Indian Standard Time (IST / Asia/Kolkata, UTC+05:30).

## Review Focus

1. **Missing or Expired Upstox Token:** System gracefully degrades to cached data or returns clean 401/503 HTTP status without crashing server background threads.
2. **Off-Market Hours & Weekends:** Engine throttles polling interval (from 1.5s to 10s) and handles empty depth or closed market states smoothly.
3. **Closing Auction Volume Distortion:** Yesterday's 15:25–15:30 closing volume spikes are filtered out when calculating morning 20-period 5m volume averages.
4. **Paper Trading Balance Concurrency:** Simultaneous order placements or stop-loss executions do not corrupt account balance or cause negative margin.
5. **Inngest Signature Verification in Development:** Inngest endpoint (`/api/inngest`) operates cleanly in local development with valid signing keys.

---

### Task 1: Upstox Client & Instrument Resolver

**Files:**
- Create: `core/upstox/client.py`
- Create: `data/upstox_instruments.json`
- Test: `tests/test_upstox_client.py`

**Interfaces:**
- Consumes: `UPSTOX_ACCESS_TOKEN` from `.env` / `os.getenv`.
- Produces: 
  - `UpstoxClient.get_quotes(symbols: List[str]) -> Dict[str, dict]`
  - `UpstoxClient.get_candles(symbol: str, interval: str, to_date: Optional[str]) -> List[dict]`
  - `UpstoxClient.get_market_depth(symbol: str) -> dict`
  - `UpstoxClient.resolve_instrument_key(symbol: str) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_upstox_client.py
import pytest
from core.upstox.client import UpstoxClient

def test_instrument_resolution():
    client = UpstoxClient(token="mock_token")
    assert client.resolve_instrument_key("RELIANCE") == "NSE_EQ|INE002A01018"
    assert client.resolve_instrument_key("TCS") == "NSE_EQ|INE467B01029"
    assert client.resolve_instrument_key("NIFTY 50") == "NSE_INDEX|Nifty 50"

@pytest.mark.asyncio
async def test_parse_quotes_and_depth(monkeypatch):
    client = UpstoxClient(token="mock_token")
    mock_payload = {
        "status": "success",
        "data": {
            "NSE_EQ:RELIANCE": {
                "last_price": 1300.0,
                "average_price": 1250.0,
                "volume": 5000000,
                "ohlc": {"open": 1240.0, "high": 1305.0, "low": 1235.0, "close": 1250.0},
                "depth": {
                    "buy": [{"quantity": 100, "price": 1299.5, "orders": 5}],
                    "sell": [{"quantity": 200, "price": 1300.0, "orders": 10}]
                }
            }
        }
    }
    
    class MockResponse:
        status_code = 200
        def json(self): return mock_payload
        
    async def mock_get(*args, **kwargs):
        return MockResponse()
        
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    quotes = await client.get_quotes(["RELIANCE"])
    assert "RELIANCE" in quotes
    assert quotes["RELIANCE"]["last_price"] == 1300.0
    assert quotes["RELIANCE"]["vwap"] == 1250.0
    assert len(quotes["RELIANCE"]["depth"]["buy"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_upstox_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.upstox'`

- [ ] **Step 3: Implement `core/upstox/client.py` and `data/upstox_instruments.json`**

Create `data/upstox_instruments.json` mapping all 50 NIFTY 50 stocks + `NIFTY 50` and `BANK NIFTY` to their Upstox `NSE_EQ|ISIN` keys.
Implement `UpstoxClient` with `httpx.AsyncClient` supporting batch quotes (comma-joined `instrument_key`), historical candles, and structured output formatting.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_upstox_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add data/upstox_instruments.json core/upstox/client.py tests/test_upstox_client.py
git commit -m "feat(upstox): implement UpstoxClient and NIFTY 50 instrument mapping"
```

---

### Task 2: Real-Time Market Stream Engine & Rolling 5m Candle Aggregator

**Files:**
- Create: `core/upstox/stream.py`
- Test: `tests/test_upstox_stream.py`

**Interfaces:**
- Consumes: `UpstoxClient` from Task 1.
- Produces:
  - `UpstoxMarketEngine.start()`
  - `UpstoxMarketEngine.stop()`
  - `UpstoxMarketEngine.get_latest_quotes() -> Dict[str, dict]`
  - `UpstoxMarketEngine.get_5m_candles(symbol: str) -> List[dict]`
  - `UpstoxMarketEngine.get_opening_range(symbol: str) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_upstox_stream.py
import pytest
from core.upstox.stream import UpstoxMarketEngine
from datetime import datetime

def test_candle_aggregation():
    engine = UpstoxMarketEngine(client=None)
    # Feed simulated ticks for RELIANCE
    t1 = datetime(2026, 11, 2, 9, 15, 30)
    engine.record_tick("RELIANCE", 1250.0, 1000, t1)
    engine.record_tick("RELIANCE", 1260.0, 2000, datetime(2026, 11, 2, 9, 16, 0))
    engine.record_tick("RELIANCE", 1245.0, 3000, datetime(2026, 11, 2, 9, 17, 0))
    engine.record_tick("RELIANCE", 1255.0, 4000, datetime(2026, 11, 2, 9, 19, 59))
    
    candles = engine.get_5m_candles("RELIANCE")
    assert len(candles) >= 1
    c = candles[-1]
    assert c["open"] == 1250.0
    assert c["high"] == 1260.0
    assert c["low"] == 1245.0
    assert c["close"] == 1255.0
    assert c["volume"] == 10000

def test_opening_range_lock():
    engine = UpstoxMarketEngine(client=None)
    # Ticks between 09:15 and 09:30
    engine.record_tick("RELIANCE", 1250.0, 100, datetime(2026, 11, 2, 9, 15, 10))
    engine.record_tick("RELIANCE", 1280.0, 100, datetime(2026, 11, 2, 9, 22, 0))
    engine.record_tick("RELIANCE", 1240.0, 100, datetime(2026, 11, 2, 9, 28, 0))
    
    orb = engine.get_opening_range("RELIANCE")
    assert orb["high"] == 1280.0
    assert orb["low"] == 1240.0
    assert round(orb["spread_pct"], 2) == round(((1280 - 1240) / 1240) * 100, 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_upstox_stream.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.upstox.stream'`

- [ ] **Step 3: Implement `core/upstox/stream.py`**

Build `UpstoxMarketEngine` with:
- Asynchronous polling loop (1.5s in-market, 10s off-market) querying `client.get_quotes(NIFTY_SYMBOLS)`.
- In-memory tick cache, 5-minute candle aggregation bucketed by `(timestamp.minute // 5) * 5`.
- 09:15–09:30 IST Opening Range Tracker (`high`, `low`, `locked`).
- Broadcast hook to notify registered WebSocket queues.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_upstox_stream.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/upstox/stream.py tests/test_upstox_stream.py
git commit -m "feat(upstox): add background market engine and 5m candle aggregator"
```

---

### Task 3: Opening Range Breakout (ORB) Scanner & Confluence Buy Signal Engine

**Files:**
- Create: `core/intraday/orb.py`
- Create: `core/intraday/signals.py`
- Test: `tests/test_intraday_scanners.py`

**Interfaces:**
- Consumes: `UpstoxMarketEngine` from Task 2.
- Produces:
  - `ORBScanner.scan(symbol: str) -> Optional[ORBBreakout]`
  - `ConfluenceSignalEngine.evaluate(symbol: str) -> Optional[BuySignal]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_intraday_scanners.py
import pytest
from core.intraday.orb import ORBScanner
from core.intraday.signals import ConfluenceSignalEngine

def test_orb_breakout_detection():
    scanner = ORBScanner()
    orb_range = {"high": 1000.0, "low": 980.0, "locked": True}
    current_candle = {
        "open": 995.0,
        "high": 1010.0,
        "low": 992.0,
        "close": 1008.0,
        "volume": 50000
    }
    avg_volume = 30000
    vwap = 998.0
    
    breakout = scanner.evaluate_breakout("INFY", orb_range, current_candle, avg_volume, vwap)
    assert breakout is not None
    assert breakout["status"] == "BULLISH_ORB_BREAKOUT"
    assert breakout["entry_price"] == 1008.0
    assert breakout["stop_loss"] == 980.0
    assert breakout["target_1"] > 1008.0

def test_confluence_buy_signal():
    engine = ConfluenceSignalEngine()
    signal = engine.evaluate_signal(
        symbol="TCS",
        ltp=3500.0,
        vwap=3480.0,
        ema9=3495.0,
        ema20=3485.0,
        rsi=62.0,
        current_volume=120000,
        avg_volume=70000
    )
    assert signal is not None
    assert signal["qualified"] is True
    assert signal["confluence_score"] >= 80
    assert signal["invalidation_sl"] == 3480.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_intraday_scanners.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.intraday'`

- [ ] **Step 3: Implement `core/intraday/orb.py` and `core/intraday/signals.py`**

- `ORBScanner`: Checks `close > opening_range_high`, `close > vwap`, `volume > 1.3 * avg_volume`. Sets target 1 (`entry + 1.5 * spread`) and target 2 (`entry + 2.5 * spread`).
- `ConfluenceSignalEngine`: Validates `LTP > VWAP`, `EMA9 > EMA20`, `LTP > EMA9`, `RSI between 55 and 70`, `Volume > 1.5x avg`. Computes weighted confluence score (0–100).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_intraday_scanners.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/intraday/ tests/test_intraday_scanners.py
git commit -m "feat(intraday): implement ORB breakout scanner and confluence signal engine"
```

---

### Task 4: Paper Trading & Active Risk Management Desk

**Files:**
- Create: `core/intraday/paper_trading.py`
- Test: `tests/test_paper_trading.py`

**Interfaces:**
- Consumes: Live quotes from `UpstoxMarketEngine`.
- Produces:
  - `PaperTradingDesk.execute_buy(symbol, quantity, stop_loss, target, notes) -> Position`
  - `PaperTradingDesk.update_mtm(current_quotes: Dict[str, dict]) -> List[dict]`
  - `PaperTradingDesk.close_position(position_id, exit_price, reason) -> Position`
  - `PaperTradingDesk.get_summary() -> dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_paper_trading.py
import pytest
from core.intraday.paper_trading import PaperTradingDesk

def test_paper_trade_lifecycle():
    desk = PaperTradingDesk(initial_capital=1000000.0, filepath=None)
    
    # 1. Place buy order
    pos = desk.execute_buy("RELIANCE", quantity=100, buy_price=1250.0, stop_loss=1230.0, target=1290.0)
    assert pos["symbol"] == "RELIANCE"
    assert pos["status"] == "OPEN"
    assert desk.virtual_cash == 1000000.0 - 125000.0
    
    # 2. Update MTM price up
    events = desk.update_mtm({"RELIANCE": {"last_price": 1270.0}})
    summary = desk.get_summary()
    assert summary["unrealized_pnl"] == (1270.0 - 1250.0) * 100
    assert summary["total_current_value"] > 1000000.0
    
    # 3. Simulate Stop Loss breach
    sl_events = desk.update_mtm({"RELIANCE": {"last_price": 1225.0}})
    assert len(sl_events) == 1
    assert sl_events[0]["type"] == "STOP_LOSS_HIT"
    assert desk.positions[0]["status"] == "CLOSED"
    assert desk.positions[0]["realized_pnl"] == (1225.0 - 1250.0) * 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_paper_trading.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.intraday.paper_trading'`

- [ ] **Step 3: Implement `core/intraday/paper_trading.py`**

Build `PaperTradingDesk`:
- Margin checks and virtual cash balance ledger.
- Persistent JSON store in `data/paper_trading_portfolio.json`.
- Thread-safe updates and MTM valuation.
- Automated SL/Target triggers returning actionable exit event records.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_paper_trading.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/intraday/paper_trading.py tests/test_paper_trading.py
git commit -m "feat(intraday): add paper trading ledger and risk management desk"
```

---

### Task 5: Intraday Backtesting Engine

**Files:**
- Create: `core/intraday/backtest.py`
- Test: `tests/test_intraday_backtest.py`

**Interfaces:**
- Consumes: `UpstoxClient.get_candles` from Task 1.
- Produces:
  - `IntradayBacktester.run_orb_backtest(candles_5m: List[dict]) -> BacktestResult`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_intraday_backtest.py
import pytest
from core.intraday.backtest import IntradayBacktester

def test_backtest_orb_run():
    backtester = IntradayBacktester()
    # Mock a 1-day series of 5m candles (9:15 to 15:30)
    mock_candles = [
        # 09:15, 09:20, 09:25 (Opening Range: High 1000, Low 990)
        {"timestamp": "2026-11-02T09:15:00+05:30", "open": 995, "high": 1000, "low": 992, "close": 998, "volume": 10000},
        {"timestamp": "2026-11-02T09:20:00+05:30", "open": 998, "high": 999, "low": 990, "close": 993, "volume": 12000},
        {"timestamp": "2026-11-02T09:25:00+05:30", "open": 993, "high": 997, "low": 991, "close": 995, "volume": 11000},
        # 09:30 Breakout candle (Close 1005 > 1000, High 1008)
        {"timestamp": "2026-11-02T09:30:00+05:30", "open": 995, "high": 1008, "low": 995, "close": 1005, "volume": 25000},
        # 09:35 Target hit (High 1025 >= Target 1020)
        {"timestamp": "2026-11-02T09:35:00+05:30", "open": 1005, "high": 1025, "low": 1004, "close": 1022, "volume": 30000},
    ]
    
    result = backtester.run_orb_backtest("TEST_STOCK", mock_candles)
    assert result["total_trades"] == 1
    assert result["winning_trades"] == 1
    assert result["win_rate"] == 100.0
    assert result["total_profit"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_intraday_backtest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.intraday.backtest'`

- [ ] **Step 3: Implement `core/intraday/backtest.py`**

Build `IntradayBacktester`:
- Parses historical 5-minute candles into day sessions.
- Computes 09:15–09:30 range, triggers entry on breakout candle, simulates SL/Target/EOD square-off.
- Generates win rate, profit factor, max drawdown, and detailed trade execution logs.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_intraday_backtest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/intraday/backtest.py tests/test_intraday_backtest.py
git commit -m "feat(intraday): implement historical intraday strategy backtester"
```

---

### Task 6: Inngest Event Client & Durable Workflows

**Files:**
- Create: `core/workflows/inngest_client.py`
- Create: `core/workflows/functions.py`
- Modify: `main.py`
- Test: `tests/test_inngest_workflows.py`

**Interfaces:**
- Consumes: Inngest SDK, credentials from `.env`.
- Produces:
  - Inngest client mounted at `/api/inngest` via `inngest.fast_api.serve`.
  - Durable functions: `fn_dispatch_alert`, `fn_orb_check`, `fn_paper_eod_square_off`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_inngest_workflows.py
import pytest
from core.workflows.inngest_client import inngest_client
from core.workflows.functions import inngest_functions

def test_inngest_configuration():
    assert inngest_client is not None
    assert inngest_client.app_id == "stockpulse-pro"
    assert len(inngest_functions) >= 3

@pytest.mark.asyncio
async def test_alert_dispatch_payload():
    from core.workflows.functions import format_telegram_alert
    msg = format_telegram_alert({
        "symbol": "RELIANCE",
        "type": "ORB_BREAKOUT",
        "price": 1300.0,
        "target": 1330.0,
        "stop_loss": 1280.0
    })
    assert "RELIANCE" in msg
    assert "1300.0" in msg
    assert "TARGET" in msg.upper()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_inngest_workflows.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.workflows'`

- [ ] **Step 3: Implement Inngest client and functions**

- `core/workflows/inngest_client.py`: Initialize `inngest.Inngest` with `app_id="stockpulse-pro"`, reading keys from `.env`.
- `core/workflows/functions.py`: Define `inngest.create_function` handlers for:
  - `upstox/alert.dispatch` (formats and dispatches Telegram + audio alerts with retries).
  - `upstox/orb.check` (evaluates opening ranges).
  - `upstox/paper.eod` (end-of-day square-off at 15:20 IST).
- In `main.py`, mount via `inngest.fast_api.serve(app, inngest_client, inngest_functions)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_inngest_workflows.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/workflows/ tests/test_inngest_workflows.py main.py
git commit -m "feat(workflows): integrate Inngest client and durable event functions"
```

---

### Task 7: REST API Endpoints & Real-Time WebSocket Route

**Files:**
- Create: `api/upstox_trading.py`
- Modify: `main.py`
- Test: `tests/test_upstox_api.py`

**Interfaces:**
- Consumes: `UpstoxMarketEngine`, `PaperTradingDesk`, `ORBScanner`, `ConfluenceSignalEngine`.
- Produces:
  - REST endpoints at `/api/upstox/*`
  - Dedicated WebSocket route at `/ws/upstox/live`
  - Updated `/api/market/depth/{symbol}` using real Upstox order book.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_upstox_api.py
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_upstox_status_endpoint():
    response = client.get("/api/upstox/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "token_configured" in data

def test_paper_portfolio_endpoint():
    response = client.get("/api/upstox/paper/portfolio")
    assert response.status_code == 200
    data = response.json()
    assert "virtual_cash" in data
    assert "positions" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_upstox_api.py -v`
Expected: FAIL with 404 Not Found on `/api/upstox/status`

- [ ] **Step 3: Implement `api/upstox_trading.py` and mount in `main.py`**

Implement router endpoints:
- `GET /api/upstox/status`
- `GET /api/upstox/quotes`
- `GET /api/upstox/quote/{symbol}` (with real 5-level depth)
- `GET /api/upstox/scanner/orb`
- `GET /api/upstox/scanner/signals`
- `GET /api/upstox/paper/portfolio`
- `POST /api/upstox/paper/order`
- `POST /api/upstox/paper/close/{position_id}`
- `POST /api/upstox/paper/reset`
- `POST /api/upstox/backtest`
- WebSocket `/ws/upstox/live` broadcasting ticks and alert events.
- Upgrade `main.py` `/api/market/depth/{symbol}` to return real Upstox depth with fallback.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_upstox_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/upstox_trading.py main.py tests/test_upstox_api.py
git commit -m "feat(api): add Upstox trading REST endpoints and /ws/upstox/live route"
```

---

### Task 8: Frontend "⚡ Upstox Intraday Desk" UI

**Files:**
- Modify: `static/index.html`
- Modify: `static/js/app.js`
- Modify: `static/css/style.css`

**Interfaces:**
- Consumes: `/api/upstox/*` REST routes and `/ws/upstox/live` WebSocket.
- Produces:
  - Sidebar navigation item "⚡ Upstox Intraday Desk".
  - Live NIFTY 50 Scanner Matrix with flashing price ticks.
  - ORB Breakout Tracker with 15m range markers.
  - Confluence Buy Signals Board.
  - Paper Trading Terminal with Live MTM P&L, 1-Click Buy / Square-off, and Trade Log.
  - 5-Level Market Depth DOM Modal.
  - Web Audio dual-tone notification chime for breakouts and SL hits.

- [ ] **Step 1: Write integration tests for static assets & HTML markup**

```python
# tests/test_frontend_markup.py
def test_upstox_tab_in_html():
    with open("static/index.html", "r") as f:
        html = f.read()
    assert "upstox-intraday" in html
    assert "Upstox Intraday Desk" in html
    assert "ws/upstox/live" in open("static/js/app.js").read()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_frontend_markup.py -v`
Expected: FAIL (tab not yet in index.html)

- [ ] **Step 3: Implement frontend changes**

- In `static/index.html`: Add navigation button and the full `upstox-intraday` view section (KPI bar, Sub-tabs: Scanner, ORB, Signals, Paper Trading, Backtester).
- In `static/js/app.js`: Implement `UpstoxDesk` controller, auto-reconnecting WebSocket client to `/ws/upstox/live`, price flashing, paper order submission, 1-click square-off, and audio chime.
- In `static/css/style.css`: Add styling for market depth DOM bars, ORB status badges, and MTM profit meters.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_frontend_markup.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add static/index.html static/js/app.js static/css/style.css tests/test_frontend_markup.py
git commit -m "feat(ui): add Upstox Intraday Desk frontend with live feed and paper trading"
```

---

### Task 9: Full System Verification & End-to-End Integration

**Files:**
- Test: `tests/test_full_upstox_integration.py`
- Modify: `README.md` (document Upstox and Inngest setup)

**Interfaces:**
- Consumes: All modules from Tasks 1–8.
- Produces: 100% verified live test suite across Upstox ingestion, ORB scanning, Paper Trading, and Inngest workflows.

- [ ] **Step 1: Run complete test suite**

Run: `pytest tests/ -v`
Expected: All tests pass (existing 35 + new Upstox tests).

- [ ] **Step 2: Verify live server startup and endpoints**

Run: `python3 -m uvicorn main:app --host 0.0.0.0 --port 8000`
Verify via curl:
- `curl -s http://localhost:8000/api/upstox/status` -> returns `{"status": "ok", "token_configured": true}`
- `curl -s http://localhost:8000/api/upstox/quotes` -> returns 50 live NIFTY quotes.
- `curl -s http://localhost:8000/api/upstox/paper/portfolio` -> returns virtual portfolio.

- [ ] **Step 3: Commit**

```bash
git add tests/ README.md
git commit -m "test(upstox): verify full Upstox intraday engine integration and documentation"
```
