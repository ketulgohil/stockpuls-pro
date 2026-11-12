# Day Trader CLI → StockPulse Pro UI Integration Plan

Source skill: `~/Developer/indian-day-trader` (11 CLI scripts, Indian market edition, Upstox V3).
Target: StockPulse Pro (`~/Developer/Trading`) — FastAPI backend + vanilla JS frontend.

## 1. Current state (verified)

| Day trader CLI | Already in backend? | Endpoint(s) | Used by UI today |
| --- | --- | --- | --- |
| trader-scanner | ✅ condensed port | `POST /api/scanner/daily`, `POST /api/scanner/orb`, `GET /api/scanner/universe` | ❌ |
| trader-news | ✅ | `GET /api/news`, `GET /api/news/{symbol}`, `POST /api/news/check` | News tab (partial) |
| trader-entry | ✅ | `POST /api/entry/check` | ❌ |
| trader-exit | ✅ | `POST /api/exit/plan`, `GET /api/exit/plan/{symbol}` | ❌ |
| trader-timemachine | ✅ | `POST /api/timemachine/run` (sync, heavy) | ❌ |
| trader-risk | ✅ | `POST /api/risk/check` | ❌ |
| trader-budget | ✅ | `POST /api/budget/size`, `POST /api/budget/size/weights` | ❌ |
| trader-broker | ✅ | `POST /api/broker/slip`, `GET /api/broker/slips`, `POST /api/broker/fill` | ❌ |
| trader-alerts | ✅ | `GET /api/alerts/clock`, `POST /api/alerts/rules`, `POST /api/alerts/check` | Tools tab (old generic) |
| trader-analyst | ✅ | `GET /api/analyst/facts/{symbol}`, `GET /api/analyst/metrics` | ❌ |
| trader-institutional | ✅ | `GET /api/institutional/deals`, `GET /api/institutional/pit` | ❌ |

Persistence already exists in `data/`: `broker_slips.json`, `budget_orders.json`, `exit_plans.json`, `entry.json`, `risk.json`, `timemachine.json`, `institutional_deals.json`, `news_state.json`.

Inngest workers already live in `core/workflows/functions.py`: alert dispatch (Telegram), ORB check, paper EOD square-off.

**Gap = frontend only.** Nothing in `app.js` calls entry/exit/risk/budget/broker/timemachine/institutional/analyst endpoints.

## 2. Principles

1. **All data from Upstox** — no Yahoo; reuse `upstox_data` + `liveQuoteCache`.
2. **Read-only decision support** — no automated order placement. Order Desk only generates copy-paste slips and reconciles manual fills (matches the skill's zero-auto-execution rule).
3. **Reuse existing platform infra**: `api()` helper (X-API-Key), `data-live-*` DOM live-quote attributes, toast + Web Audio alerts, `.sub-nav-btn`/`.upstox-sub-content` tab pattern from Upstox Intraday Desk, IST session clock.
4. **Heavy work off the UI thread** — Time Machine and universe scans run server-side as jobs; UI polls results.

## 3. UI structure

One new sidebar item **⚡ Trader Desk** (reuses the sub-nav pattern; keeps the sidebar from growing another 10 items), with internal sub-tabs:

```
Trader Desk
├─ Session strip (always visible at top): IST clock, market phase, ORB window,
│   entry-window open/close, flat-by 15:15 countdown, next scheduled scan
├─ 1 Scanner        — ORB + daily setup scans across the universe
├─ 2 Entry Timer    — bar-by-bar trigger watchlist with alerts
├─ 3 Exit Planner   — stop/target plan with full statutory cost netting
├─ 4 Position Sizer — budget sizing (single + weighted basket)
├─ 5 Risk Check     — order list validator (loss caps, window, tick, circuits)
├─ 6 Order Desk     — manual order slips + fill reconciliation
├─ 7 Time Machine   — 10k-replay Monte Carlo + walk-forward validation
├─ 8 Institutional  — bulk/block deals + SEBI PIT filings
├─ 9 Analyst        — quarterly facts/metrics (SEBI LODR Reg 33)
└─ 10 Session Alerts— opening bell / target / stop / MIS square-off rules
```

Deep links from elsewhere: chart page "Plan trade" button (prefills symbol + entry from LTP), drawer "Time Machine" button, watchlist "Watch entry" button.

## 4. Sub-tab specs (endpoint ↔ UI mapping)

### 1. Scanner
- Controls: universe select (Nifty 50 / ALL_SYMBOLS 117 / full instruments), scan type (ORB / daily setups), OR minutes, min volume-x.
- `POST /api/scanner/orb` (engine-backed) and `POST /api/scanner/daily`; render result cards: symbol, setup, side, trigger bar, volume-x, distance to level.
- Row actions → "Check entry", "Plan exit", "Size", "Time Machine" (prefill downstream tabs).
- Last scan cached in `data/scanner_scans.json`; show "last run 09:35" and auto-rerun at 09:31 IST.

### 2. Entry Timer
- Left: watched symbols (default = scanner hits; add/remove via symbol search).
- `POST /api/entry/check` per symbol (payload: `symbol, setup=orb|level, or_minutes=15, interval=5m, level?, min_volume_x`).
- Poll every 60s during session (client `setInterval`, IST-guarded); server Inngest ORB job already runs scheduled checks.
- Status chips: `waiting → triggered → expired → no-data`; on `triggered` show trigger bar time, close, volume-x, % over level → toast + beep + flash row.
- Show opening-range box (high/low/avg volume) and "last 5m bar" mini table.

### 3. Exit Planner
- Form: symbol (prefill from LTP), entry, stop rule (`orb_mid|orb_low|price|pct|atr`) + param, OR high/low auto-fill from Entry Timer result, target rule (`r|price`) + param, qty, broker profile, exchange, ATR override.
- `POST /api/exit/plan` → render plan card: stop, target, R:R, net R:R after costs, breakeven, total hurdle ₹, slippage, statutory cost table (STT/GST/SEBI/stamp), **flat-by 15:15** countdown, warnings.
- History list from `data/exit_plans.json` (add `GET /api/exit/plans`).

### 4. Position Sizer
- Single: `POST /api/budget/size` (capital, risk %, entry, stop, target, budget cap) → qty, bound-by (risk/budget/max-loss), cost, max loss, order proposal.
- Basket: weighted mode `POST /api/budget/size/weights` → table of per-symbol qty.
- Button → "Create order slip" (passes proposal to Order Desk).

### 5. Risk Check
- Orders table (symbol, side, qty, type, limit/stop) + config panel (max loss/trade, daily loss ceiling, entry window, ADV bounds).
- `POST /api/risk/check` → per-order verdicts (PASS/REJECT + reasons: window, tick size, circuit, ADV, loss cap) and portfolio state summary; store/display history from `data/risk.json`.

### 6. Order Desk
- Create from sizer/exit plan or manually: `POST /api/broker/slip` (symbol, qty, price, stop, target, exchange, product MIS, order type, broker zerodha|groww|upstox|angelone, note).
- Slip card = formatted, copy-to-clipboard order slip per broker (no auto execution).
- `GET /api/broker/slips` list with states; "Record fill" modal → `POST /api/broker/fill` (ticket, price, qty) reconciles and updates paper portfolio.

### 7. Time Machine
- Form: symbol, session date, entry/stop/target, entry time (IST), side, shares, replays (default 10k, cap 20k), until 15:30, walk-forward split/embargo.
- **Async job**: `POST /api/timemachine/run` → `{job_id}`; server runs in `asyncio.to_thread`; `GET /api/timemachine/result/{job_id}` polls; keep history list in `data/timemachine.json`.
- Results: win-rate, expectancy ₹, P50/P95 band chart (lightweight-charts line series of band quantiles), walk-forward table per session, cost breakdown; verdict banner ("honest odds").

### 8. Institutional
- `GET /api/institutional/deals` (bulk/block deals) and `GET /api/institutional/pit` (promoter/director filings); date-range + symbol filters; tables with `data-live-symbol` last-price columns; store badge when new deals appear since last visit.

### 9. Analyst
- Symbol search → `GET /api/analyst/facts/{symbol}` (EPS, revenue, margins in ₹ Cr/L) + `GET /api/analyst/metrics`; quarter-over-quarter delta arrows; link to Results tab.

### 10. Session Alerts
- Rules list (target/stop/bell/square-off) via existing `/api/alerts` endpoints + clock cards from `GET /api/alerts/clock`.
- Client-side instant checks off `liveQuoteCache` (no network per tick) + server-side Inngest cron during 09:15–15:15; urgent MIS square-off reminder at 15:10/15:15 with audio.

## 5. Backend additions (small, frontend-enabling)

1. `GET /api/entry/history`, `GET /api/exit/plans`, `GET /api/budget/orders`, `GET /api/risk/checks`, `GET /api/timemachine/history` — read existing JSON stores (list views).
2. Async job wrapper for Time Machine: submit → job id → poll; cap `replays ≤ 20000`; reuse `_save_tm`.
3. `POST /api/entry/scan` (optional convenience): universe ORB scan reusing `api/scanner` evaluate; batched, cached per bar.
4. Time Machine Monte Carlo currently writes single result — convert store to append-list with cap 20.
5. No new data sources; everything stays on Upstox (`get_stock_data` 1d/5m, `get_quotes`, instruments).

## 6. Live-data wiring (existing conventions)

- Every rendered row/card gets `data-live-symbol` + `data-live-price` / `data-live-change-pct` so `applyLiveDomQuotes()` fills prices from `liveQuoteCache` and `refreshLiveSubscriptions()` subscribes them (cap 200 symbols/client).
- Entry Timer rows also show the forming bar from `response.forming/last` and refresh on WS tick of that symbol.
- Fallback: `startLivePriceFallback()` REST batch poll covers WS outages (already live).

## 7. Phases

| Phase | Scope | Est. |
| --- | --- | --- |
| 0 | Backend gaps (history GETs, async TM job, TM store list) | 0.5 d |
| 1 | Trader Desk shell: nav item, sub-nav, session strip, shared card/table CSS | 0.5 d |
| 2 | Scanner + Entry Timer (highest intraday value) | 1 d |
| 3 | Exit Planner + Position Sizer + Risk Check | 1 d |
| 4 | Order Desk (slips, copy, fills) | 0.5 d |
| 5 | Time Machine (job + band chart + walk-forward table) | 1 d |
| 6 | Institutional + Analyst | 0.5 d |
| 7 | Session Alerts + Inngest crons (09:31 scan, 5-min entry checks, 15:10/15:15 square-off) | 0.5 d |
| 8 | QA: pytest for new endpoints, `node --check`, headless-Chrome tab walk (same CDP harness used for live-price/chart fixes) | 0.5 d |

## 8. Risks & mitigations

- **Upstox intraday coverage/rate limits** for universe scans → default universe = `ALL_SYMBOLS` (117); full 2990 instruments optional; batch `get_quotes` (500/batch); cache per 5-min bar.
- **Time Machine CPU** → background job + replay cap; never blocks event loop (`asyncio.to_thread`).
- **Token expiry** → every tool renders a fail-closed state ("live data unavailable — check Upstox token") instead of blank panels.
- **Session gating** → scans/entries only meaningful 09:15–15:30 IST; UI disables runs outside window with clear reason (calendar helper already in `core.trader_core`).
- **Auth** → all POSTs already require X-API-Key; frontend `api()` helper already sends it.

## 9. Acceptance criteria

- Every one of the 11 CLI jobs reachable from the UI without the terminal.
- No hardcoded symbol lists: universes from instruments/ALL_SYMBOLS.
- Live prices on every table via the existing WS pipeline.
- Time Machine runs never block the page or the server event loop.
- Order Desk cannot place orders — slips only, fills manual.
- `python3 -m pytest -q tests --ignore=tests/test_upstox_api.py` green; `node --check static/js/app.js` green; headless tab-walk shows all 10 sub-tabs with non-zero layout.
