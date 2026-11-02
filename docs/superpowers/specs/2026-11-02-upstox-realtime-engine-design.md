# Design Specification: Upstox Real-Time Market Feed & Intraday Trading Engine

- **Date:** 2026-11-02
- **Platform:** StockPulse Pro v5.1 (FastAPI / Python 3.11 / Vanilla JS / WebSocket / TradingView Lightweight Charts)
- **Status:** Approved for Implementation Planning

---

## 1. Executive Summary & Objective

The primary objective of this integration is to establish an institutional-grade, real-time intraday trading and market intelligence engine powered by Upstox's official API v2 / v3. This replaces legacy, delayed, or scraped market data (such as Yahoo Finance) across all live intraday workflows for NSE equities (specifically NIFTY 50), while retaining Yahoo Finance purely as a secondary fallback for long-term historical charts.

The system will ingest real-time ticks, real 5-level market depth (order books), and intraday historical candles to power:
1. **Live NIFTY 50 Stock Scanner:** Sub-second price, volume spike, and depth monitoring.
2. **Opening Range Breakout (ORB) Scanner:** Real-time 09:15–09:30 IST opening range tracking with 5-minute candle breakout confirmation.
3. **Multi-Confluence Buy Entry Signals:** High-probability long setups using live price, VWAP, 9/20 EMA, RSI, and volume confirmation.
4. **Live Paper Trading & Active Risk Monitor:** Simulated long executions against live bid/ask prices with real-time mark-to-market (MTM) P&L, stop-loss/target tracking, and automated exit alerts.
5. **Real-Time Market Depth & Sentinel Feed:** Live 5-level order book depth replacing simulated data, feeding directly into existing Sentinel Desks and WebSocket feeds.
6. **Intraday Strategy Backtester:** Historical intraday candle analysis (1m, 5m, 15m) using Upstox historical candle APIs.

---

## 2. Upstox API Architecture & Capabilities

### 2.1 Credentials & Authentication
- **Token Type:** Upstox v2 JWT Bearer Token (extended validity through late 2027).
- **Client ID:** `6MBUHE`.
- **Environment Storage:** `.env` and `config.py` as `UPSTOX_ACCESS_TOKEN`.
- **Rate Limits & Resilience:**
  - Upstox Market Quote API supports batch queries of up to 500 instrument keys in a single HTTP GET request (`/v2/market-quote/quotes?instrument_key=NSE_EQ|...`).
  - Upstox Market Feed WebSocket v3 (`/v3/feed/market-data-feed/authorize`) provides streaming tick updates.
  - Asynchronous HTTP client (`httpx.AsyncClient`) with connection pooling, exponential backoff, and circuit breaker.

### 2.2 Instrument Key Resolution & Bootstrap
- **Pre-bundled Universe (`data/upstox_instruments.json`):**
  - Contains deterministic static mapping for all 50 NIFTY 50 equities (e.g. `RELIANCE` -> `NSE_EQ|INE002A01018`, `TCS` -> `NSE_EQ|INE467B01029`) and key indices (`NSE_INDEX|Nifty 50`, `NSE_INDEX|Nifty Bank`).
  - Zero-latency startup: No external network dependency required to initialize the Nifty 50 scanner.
  - Dynamic fallback: An on-demand resolver queries Upstox instrument master if an arbitrary out-of-universe NSE stock is requested.

### 2.3 Market Data Ingestion Strategy
- **Primary Mechanism:** Batch REST Snapshot Streamer.
  - Upstox `/v2/market-quote/quotes` allows batching up to 500 instrument keys in a single HTTP GET request.
  - Background worker polls all 50 Nifty equities every 1.5 seconds during market hours (09:15–15:30 IST), consuming only ~0.67 requests/sec (well within Upstox's 25 req/sec quota).
  - Each response provides full real-time LTP, 5-level market depth, true VWAP (`average_price`), volume, circuit limits, and OHLC.
- **WebSocket Streaming Gate:**
  - The backend ingests the Upstox batch data, synthesizes tick deltas and rolling 5-minute candles, and immediately broadcasts them downstream to browser UI clients via FastAPI's native WebSocket (`/ws/live-prices`). This isolates the browser from broker-specific protocols and provides zero-latency updates.


---

## 3. System Architecture & Component Design

```
+-----------------------------------------------------------------------------------------+
|                                    UPSTOX API CLOUD                                     |
|  - Realtime Quotes (Batch REST)    - Live 5-Level Depth       - Historical Candlesticks |
|  - Market Feeder WebSocket (v3)    - Intraday Candles         - Circuit Limits / VWAP   |
+-----------------------------------------------------------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------------+
|                         UPSTOX ENGINE CORE (FastAPI Backend)                            |
|                                                                                         |
|  +-----------------------------------------------------------------------------------+  |
|  |                     UpstoxClient (core/upstox/client.py)                          |  |
|  |  - Auth header injection & token validation                                       |  |
|  |  - Batch quote fetcher (50 Nifty equities in 1 call)                              |  |
|  |  - Historical candle retrieval (1m, 5m, 15m, 30m, 1d) with local caching         |  |
|  |  - Real 5-level depth extractor                                                   |  |
|  +-----------------------------------------------------------------------------------+  |
|                                           |                                             |
|                                           v                                             |
|  +-----------------------------------------------------------------------------------+  |
|  |                   Live Market Engine (core/upstox/stream.py)                      |  |
|  |  - Asynchronous background polling / WS feeder (1-2s tick updates)                 |  |
|  |  - In-memory tick cache: LTP, VWAP, Change %, Day High/Low, Total Buy/Sell Qty     |  |
|  |  - Rolling 5-minute candle aggregator (Open, High, Low, Close, Volume)           |  |
|  +-----------------------------------------------------------------------------------+  |
|                     |                             |                    |                |
|                     v                             v                    v                |
|  +----------------------+  +------------------------+  +-----------------------------+  |
|  |   ORB Scanner        |  |  Entry Signal Engine   |  |   Paper Trading & Risk Desk |  |
|  | (core/intraday/      |  |  (core/intraday/       |  |   (core/intraday/           |  |
|  |  orb.py)             |  |   signals.py)          |  |    paper_trading.py)        |  |
|  | - 09:15-09:30 range  |  | - VWAP Crossover       |  | - Virtual capital account   |  |
|  | - 5m candle break    |  | - 9/20 EMA Alignment   |  | - Live MTM P&L calculation  |  |
|  | - Volume > 1.5x avg  |  | - RSI Momentum (50-70) |  | - SL / Target auto-triggers |  |
|  +----------------------+  +------------------------+  +-----------------------------+  |
|                     |                             |                    |                |
|                     +-----------------------------+--------------------+                |
|                                                   |                                     |
|                                                   v                                     |
|  +-----------------------------------------------------------------------------------+  |
|  |                          Event Dispatcher & WebSocket Gate                        |  |
|  |  - `/ws/live-prices`: Real-time streaming quotes to all web clients               |  |
|  |  - `/ws/sentinel`: Confluence alerts & breakout notifications                     |  |
|  |  - Telegram Dispatcher: Push immediate trigger alerts with charts/levels         |  |
|  +-----------------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------------+
|                                FRONTEND TRADING DESK                                    |
|  - Realtime Scanner Matrix (Sortable Nifty 50 with live flashing green/red ticks)       |
|  - Opening Range Breakout (ORB) Dashboard (Active status, 15m Range H/L, Break status)  |
|  - Confluence Buy Signals Board (VWAP + EMA + RSI + Volume indicators)                  |
|  - Paper Trading Terminal (Holdings, Unrealized P&L, 1-Click Buy/Square-off, History)  |
|  - Real 5-Level Depth Order Book Modal & Audio Chimes on Triggers                       |
+-----------------------------------------------------------------------------------------+
```

---

## 4. Detailed Component Specifications

### 4.1 Upstox Client & Instrument Resolver (`core/upstox/client.py`)
- **Initialization:** Loads token from environment or config, verifies token health.
- **Symbol Resolver:**
  - Fast hash map: `NIFTY50_MAP = {"RELIANCE": "NSE_EQ|INE002A01018", ...}` covering all 50 Nifty equities and indices (`NSE_INDEX|Nifty 50`, `NSE_INDEX|Nifty Bank`).
  - Fallback resolver to load full NSE symbols if user queries arbitrary NSE stocks.
- **`get_live_quotes(symbols: List[str]) -> Dict[str, UpstoxQuote]`:**
  - Queries `https://api.upstox.com/v2/market-quote/quotes` in batches of 50.
  - Returns structured quote data: `last_price`, `ohlc`, `depth` (5-level bid/ask with quantities and order counts), `volume`, `average_price` (true VWAP), `net_change`, `lower_circuit_limit`, `upper_circuit_limit`, `last_trade_time`.
- **`get_historical_candles(symbol: str, interval: str, to_date: str) -> List[List]`:**
  - Retrieves Upstox official candles (`1minute`, `5minute`, `15minute`, `30minute`, `day`).
  - Formats data into standard OHLCV tuples `[timestamp, open, high, low, close, volume, oi]`.

### 4.2 In-Memory Live Feed & Market Engine (`core/upstox/engine.py`)
- Runs as an asynchronous background worker inside FastAPI lifecycle (`@app.on_event("startup")`).
- Refreshes all NIFTY 50 quotes every 1 to 2 seconds during market hours (09:15–15:30 IST), and throttles to 10 seconds during off-market hours.
- Constructs live rolling 5-minute candles from consecutive ticks to supply candle-based indicator calculations without API latency.
- Broadcasts updates to connected WebSocket clients (`/ws/live-prices`).

### 4.3 Opening Range Breakout (ORB) Scanner (`core/intraday/orb.py`)
- **Parameters:**
  - Market Opening Time: 09:15 IST.
  - Opening Range Window: 09:15 to 09:30 IST (first 15 minutes).
  - Confirmation Candle: 5-minute candle closing after 09:30.
- **Workflow:**
  1. Record `high` and `low` between 09:15 and 09:30 for all Nifty 50 stocks.
  2. Calculate `range_spread = (high - low) / low * 100`. (Filter out abnormal wide ranges > 3%).
  3. At 09:35, 09:40, etc., monitor if `close > opening_range_high`:
     - Requires `volume > 1.3 * 20_period_avg_5m_volume`.
     - Requires `current_price > vwap`.
  4. If confirmed:
     - Mark status: `BULLISH_ORB_BREAKOUT`.
     - Entry Price: Breakout candle close or current LTP.
     - Stop-Loss: `opening_range_low` or mid-range.
     - Target 1: `entry + 1.5 * (high - low)`.
     - Target 2: `entry + 2.5 * (high - low)`.
     - Push alert to Sentinel Feed & Telegram.

### 4.4 Multi-Confluence Entry Signals Engine (`core/intraday/signals.py`)
Identifies high-probability long intraday setups based on 4 confirming pillars:
1. **VWAP Position:** `LTP > VWAP` (indicates institutional buyer control; Upstox provides direct exchange-computed `average_price`).
2. **Moving Average Alignment:** `EMA(9) > EMA(20)` and `LTP > EMA(9)` on 5-minute candles.
3. **Momentum (RSI):** 14-period RSI on 5-minute timeframe is between `55 and 70` (bullish momentum without being excessively exhausted).
4. **Volume Expansion:** Current 5m volume > `1.5x` the 20-period moving average volume.
- **Output:** Confluence Score (0 to 100), Entry Zone, Invalidation Level (Stop-Loss), and Targets (R:R ratio ≥ 1:2).

### 4.5 Paper Trading & Risk Management Desk (`core/intraday/paper_trading.py`)
A risk-free execution environment using live Upstox ticks:
- **Default Virtual Portfolio:** ₹10,00,000 (configurable, persistable in `data/paper_trading_portfolio.json`).
- **Order Execution:**
  - Instant simulated fill at current Upstox ask price (for long buys).
  - Validates available margin, calculates position size based on user risk per trade (e.g. 1% risk).
- **Position Tracking & Auto-Alert Semantics:**
  - Computes real-time MTM P&L on every tick: `pnl = (ltp - buy_price) * quantity`.
  - P&L % and Day Gain.
  - **Stop-Loss Breach:** When `LTP <= stop_loss`, the paper position is marked as `CLOSED (SL_TRIGGERED)`, realizes the simulated loss, and immediately dispatches a critical audio chime, UI toast, and Telegram notification so the user can manually close or adjust their live broker position.
  - **Target Reached:** When `LTP >= target_1` or `target_2`, the paper position is marked as `CLOSED (TARGET_HIT)` or partial profit locked, with instant notifications.
  - **Manual Exit:** User can click "Square Off" at any time from the UI to exit at current market bid.
  - **End of Day Square-Off:** Optional auto-close at 15:20 IST to mimic intraday MIS brokerage rules.

### 4.6 Intraday Backtesting Module (`core/intraday/backtest.py`)
- Pulls historical 1m and 5m candles from Upstox API for any Nifty stock across the last 5 to 30 trading days (Upstox returns up to 30 days of 5m candles in a single high-speed query).
- Caches candle datasets locally in `data/candles/{symbol}_{interval}.json` to minimize API latency and respect rate limits.
- Simulates the exact ORB and VWAP/EMA confluence strategy across historical sessions.
- Generates institutional performance metrics:
  - Total Trades, Win Rate %, Profit Factor, Max Drawdown %, Average R:R, Sharpe Ratio.
  - Detailed trade log showing entry time, exit time, entry price, exit price, reason for exit (Target / SL / EOD).

---

## 5. API Endpoints Specification

### 5.1 Upstox Market & Scanner Endpoints (`api/upstox_trading.py`)
- `GET /api/upstox/status`: Health check, token validity check, and connection latency.
- `GET /api/upstox/quotes`: Live batch quotes for all NIFTY 50 equities (LTP, change, volume, VWAP, high, low).
- `GET /api/upstox/quote/{symbol}`: Deep quote with 5-level market depth order book.
- `GET /api/upstox/candles/{symbol}?interval=5m&days=5`: Official historical/intraday OHLCV candles.
- `GET /api/upstox/scanner/orb`: Active ORB status for Nifty 50 (Range High, Range Low, Breakout Status, Breakout Price).
- `GET /api/upstox/scanner/signals`: Real-time qualified buy entry setups with technical scores.
- `POST /api/upstox/backtest`: Execute backtest for ORB or VWAP strategy on a symbol with custom date range.

### 5.2 Paper Trading Endpoints
- `GET /api/upstox/paper/portfolio`: Virtual cash, margin used, realized P&L, unrealized P&L, active positions.
- `POST /api/upstox/paper/order`: Place a paper trade (`symbol`, `quantity`, `stop_loss`, `target`, `notes`).
- `POST /api/upstox/paper/close/{position_id}`: Square off an active position at current live price.
- `POST /api/upstox/paper/reset`: Reset paper trading account balance to initial ₹10,00,000.
- `GET /api/upstox/paper/history`: Past closed paper trades and performance stats.

### 5.3 WebSocket Channels
- `/ws/live-prices`: Broadcasts live price updates and scanner triggers to all connected tabs.

---

## 6. Frontend UI: Intraday Trading Desk

Add a high-performance **"⚡ Upstox Intraday Desk"** view into `static/index.html` and `static/js/app.js`:
1. **Top Metric Bar:**
   - Upstox API Status (`Active 🟢`, Latency `~120ms`), Live NIFTY 50 & BANKNIFTY ticks, Market Session Phase (Pre-Open, ORB Formation 09:15–09:30, Active Breakouts, Intraday Trading).
2. **Sub-Tab Navigation:**
   - **Tab 1: Live Scanner & ORB:** Sortable heat matrix of Nifty 50 with live flashing green/red ticks, 15m Opening Range (High/Low/Range %), and Breakout Badges (`READY`, `BREAKOUT_CONFIRMED 🚀`, `PULLBACK`).
   - **Tab 2: Buy Signals (Confluence Board):** Cards displaying stocks meeting VWAP + EMA + RSI + Volume conditions with recommended Entry, SL, and Target.
   - **Tab 3: Paper Trading Terminal:**
     - Left: Order entry ticket (Symbol, Quantity, Risk Calculator, Auto-SL based on ATR or Range Low, "Execute Paper Buy").
     - Right: Live Positions Table with real-time streaming MTM P&L, SL/Target visual progress bars, and 1-click "Square Off" button.
     - Bottom: Trade Performance Summary (Win Rate, Total P&L, Profit Factor).
   - **Tab 4: Strategy Backtester:** Interactive backtesting tool to test ORB or VWAP setups on any stock with interactive equity curve chart.
3. **Interactive 5-Level Depth Modal:**
   - Clicking any stock displays the live Upstox 5-level bid/ask order book ladder with visual bar depth.

---

## 7. Migration & Backward Compatibility
- **Yahoo Finance:** Retained as a secondary fallback for long-term historical daily/weekly charts or if Upstox token is unconfigured.
- **Sentinel Engine Integration:** Existing `ActivityDesk` and `TechnicalDesk` will seamlessly read from the new `UpstoxLiveEngine` cache when available, guaranteeing real-time accuracy and zero latency in AI Sentinel alerts.
- **Existing Routes:** Existing routes (`/api/market/depth/{symbol}`) will now return real Upstox order book depth instead of random simulations.

---

## 8. Verification & Acceptance Criteria
1. **API Token & Connectivity:** Verify Upstox REST and Market Feed authorization endpoints return 200 OK.
2. **NIFTY 50 Live Streaming:** 50 stocks updating in real time with correct LTP, VWAP, and volume.
3. **ORB Engine Accuracy:** Correctly computes and locks 09:15–09:30 high/low and flags breakouts on 5-minute candle closes.
4. **Paper Trading Integrity:** Orders execute at live tick prices, MTM P&L updates continuously, and Stop-Loss triggers fire accurately when threshold is touched.
5. **Backtester Validation:** Backtest runs against real historical Upstox candles and outputs consistent trade logs.
6. **Zero Breaking Changes:** Existing platform features (Sentinel Desk, Technicals, Screeners, Portfolio) continue to operate cleanly.
