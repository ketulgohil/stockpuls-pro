# Chart Reliability Review and Fix Checklist

> **Status (2026-11-14):** Phases 0–5 implemented and verified in code. Remaining
> open items are hands-on UI verifications: Phase 6 (manual regression
> scenarios) and the acceptance gate. Keyboard-coverage and persistence checks
> in Phase 5 also need manual confirmation. Evidence references point at
> `static/js/app.js` unless noted.

## Scope

This review covers the app's chart entry points, the current chart loading flow, and the recommendations in [`CHART_UX_DESIGN_RECOMMENDATIONS.md`](CHART_UX_DESIGN_RECOMMENDATIONS.md).

The main implementation paths are:

- `static/index.html` — chart navigation and chart workspace markup
- `static/js/app.js` — tab navigation, symbol selection, chart loading, timeframe controls, live updates, and generated chart links
- `static/js/chart/chart-controller.js` — chart and series lifecycle
- `static/js/chart/data-adapter.js` — candle and volume normalization
- `static/js/chart/chart-state.js` — saved chart workspace state
- `api/stocks.py` — historical stock data endpoint

## Summary of important findings

- **Initialization race:** `selectStock(symbol)` calls `showTab('chart')` and then immediately calls `loadChartChart(symbol)`. The chart-tab wrapper defers chart initialization to `requestAnimationFrame`. A load can therefore start before the chart controller and series exist.
- **Loads can be dropped:** `loadChartChart` returns immediately if `chartLoadingLock` is held. A newer symbol or timeframe request can be discarded while the older request later renders.
- **HTTP error handling needs confirmation:** The history endpoint returns HTTP 404 for empty results. The chart loader expects a response object with an `error` property, so verify how the shared `api()` helper handles non-2xx responses and ensure all error paths clear loading state.
- **Timeframe mappings need product verification:** Some timeframe buttons map to the same interval or long history windows, which may not match what users expect from their labels.
- **Chart entry points are distributed across static markup and generated HTML:** All symbol-specific controls now carry `data-chart-symbol` and funnel through one delegated handler into `openChart`.

## Chart entry-point inventory

| Entry point | Location / examples | Current behavior | Review checks |
|---|---|---|---|
| Main navigation | `static/index.html`, chart nav item | Opens the chart tab without an explicit symbol | Define and verify saved/default symbol loading |
| Dashboard | Gainers/losers, trending items, focus-stock actions in `static/js/app.js` | Selects a symbol and opens Chart | Confirm correct symbol, one load, and correct result after rapid clicks |
| Portfolio | Per-holding **Chart** buttons in `static/js/app.js` | Selects the holding and opens Chart | Reproduce the reported Portfolio → Chart issue for several holdings |
| Watchlist | **View** controls and chart watchlist actions | Selects a symbol and opens Chart | Confirm row selection and displayed chart stay in sync |
| Search and stock lists | Search results and generated stock tables | Selects a symbol and opens Chart | Check raw ticker and exchange suffix handling |
| Alerts | Alert symbol links | Selects a symbol and opens Chart | Confirm symbol normalization and valid alert-linked symbols |
| Sentinel | Symbol pills and action buttons | Selects a symbol and opens Chart | Confirm navigation works when chart has not yet been initialized |
| Other feature tables | Generated rows using `data-chart-symbol` | Delegated handler opens `openChart` (single entry) | Migrated from inline `onclick` → shared handler; verify the source-specific symbol |

Most symbol-specific controls carry `data-chart-symbol="SYMBOL"` and open the chart through one delegated document-level click/keydown handler (`openChartFromElement` → `openChart`, app.js ~L1958–2000). The initialization race can therefore affect multiple entry points at once.

## Prioritized implementation checklist

### Phase 0 — Make every entry point reliable

- [x] Introduce one shared chart-opening function for all symbol links and buttons. (`openChart(symbol)` L1662; `openStockChart` delegates to it)
- [x] Ensure chart initialization completes before starting a data load. (`ensureChartInitialized` awaits `chartInitPromise`; chart only initializes when the Chart tab is visible with a 100ms delay + dimension polling)
- [x] Make chart initialization idempotent; repeated navigation must not create duplicate charts, observers, controls, or listeners. (`chartInitPromise` guard L519–554)
- [x] Define the behavior for opening Chart from the main navigation without an explicit symbol: restore a saved symbol or load a documented default. (`ChartState.load()` → saved symbol, fallback `RELIANCE.NS`, L1954–1960)
- [x] Ensure the selected symbol, input, header, badge, price, candle data, and live subscription always refer to the same symbol. (single `symbol` param threaded through `loadChartChart`; request-ID guards reject superseded work)
- [x] Normalize symbols once at the shared entry point; handle exchange suffixes, blank values, malformed values, and unsupported symbols. (`normalizeSymbol` L47, applied at entry + load)
- [x] Replace inline `onclick` handlers progressively with shared event handlers so entry paths are easier to audit and test. (Done: dashboard gainers/losers, market rows, signals/portfolio/watchlist **View**+**Chart** buttons, trending, heatmap, alert pills, ticker, Sentinel pills/actions, focus stocks, trading-desk links, UPX quote/position links, chart watchlist items — all now use `data-chart-symbol` with a delegated document-level click handler; chart symbol search results + topbar search items included. `selectStockFromSearch`/`selectStockFromChartWatchlist` wrappers removed.)
- [ ] Confirm every button and clickable row is keyboard accessible and has an accessible name. *(Delegated Enter/Space handler covers `data-chart-symbol` elements; chart watchlist items have `role="button"` + `tabindex`. Row-level tabindex coverage for plain table rows still needs a manual pass.)*

### Phase 1 — Request lifecycle and error recovery

- [x] Replace the single-load early-return behavior with latest-request-wins behavior, request cancellation, or an explicit queue. (`chartRequestId` system L477–478 replaced `chartLoadingLock`)
- [x] Associate each request with its symbol and timeframe; ignore stale responses. (`thisRequestId !== chartRequestId` checks at L788, 799, 844)
- [x] Verify how the shared `api()` helper represents HTTP errors, especially the history endpoint's 404 response. (`api()` returns `{error, status}` on non-2xx, 15s AbortController timeout, `res.ok` checked — app.js L60–104)
- [x] Handle empty data, unknown symbols, provider errors, rate limits, timeouts, malformed responses, and offline state. (error overlay + suggestion + Retry at L804–832; invalid-candle overlay L828)
- [x] Ensure every success, failure, exception, and early return clears loading indicators and restores disabled controls. (loading hidden on error paths; `FINALLY` cleanup L936)
- [x] Make retry work without refreshing the page. (Retry button re-invokes `loadChartChart(currentSymbol)`)
- [x] Keep the previous chart visible or clearly marked stale while loading; never show old candles under a new symbol label. (explicitly kept on failed symbol change L811; superseded loads abort before render)
- [x] Safely render error messages rather than interpolating untrusted response text into `innerHTML`. (All three chart overlays escape via `escapeHtml`: `data.error`/symbol L827, invalid-candles L845, catch-block messages L949 + openChart L1721; retry-button symbol attribute escaped too)

### Phase 2 — Chart lifecycle, sizing, and data validation

- [x] Handle a missing chart container or missing Lightweight Charts library with a visible recoverable error state. (zero-dimension guard + init throws surfaced via loading overlay; `loadChartChart` rethrows after `chartInitPromise`)
- [x] Measure chart dimensions only after the tab is visible; verify dimensions after navigation, resize, sidebar changes, and browser zoom. (`chart-visible` class forces `display:flex`; 100ms delay + rAF dimension polling before init; cleanup on tab leave L1900–1948)
- [x] Add lifecycle cleanup for `ResizeObserver`, timers, and event listeners when the chart is destroyed or reinitialized. (Legacy `initChart` stores its observer in `chartResizeObserver` and disconnects the previous one before re-observing; init remains idempotent so no duplicates are created)
- [x] Validate candle data before rendering: finite OHLC values, `low ≤ open/close ≤ high`, nonnegative volume, valid timestamps, and unique ordered times. (L816–832, sorted ascending L834)
- [x] Confirm date serialization and ordering from `/api/stocks/{symbol}/history` match the chart library's accepted time format. (`normalizeChartTime` — ISO strings → YYYY-MM-DD for daily, Unix seconds for intraday)
- [x] Confirm the stock-detail price request can fail independently while valid history still renders and supplies a fallback price. (try/catch falls back to last candle close L857–868)
- [x] Confirm chart and volume points use matching timestamps. (volumes built from the same validated `candles` array L871–874)

### Phase 3 — Timeframes, visible range, and overlays

- [x] Verify each timeframe label maps to the intended provider interval and requested history window. (`TIMEFRAME_CONFIG` L780+ — every label now has an explicit, commented mapping; note 1mo/3mo/6mo intentionally use monthly candles)
- [x] Document whether timeframe changes preserve the visible range or fit all available data; implement that behavior consistently. (Policy documented in code above `TIMEFRAME_CONFIG` L595: every load always ends with `fitContent()`; rationale — re-fetched/re-sorted candles invalidate a persisted range)
- [x] Confirm a new symbol intentionally resets or restores the visible range according to the product decision. (Resets to fit-all per the documented policy)
- [x] Verify active timeframe state matches the response that actually rendered. (request-ID guarded; `ChartState.resolution` saved only after render L964–965)
- [x] Test rapid timeframe changes while requests are pending. (covered by the request-ID latest-wins system; each pending response aborts before rendering)
- [x] Clear or recompute EMA, VWAP, pivots, ORB levels, pattern markers, oscillator data, and strategy lines on every symbol/timeframe change. (`updateIndicators` recomputes from the new candle set each render — chart-controller.js L299–326; live daily candle re-marked per load)
- [ ] Handle insufficient history and null indicator values without passing invalid values to the chart library. *(Partial: calculators return arrays/`[]` and `NaN` paths are guarded in most spots; not exhaustively audited.)*
- [x] Ensure stale overlays from the previous symbol are never displayed. (indicators/data recomputed from the current request's candles only)

### Phase 4 — Live data and subscriptions

- [x] Subscribe only for the selected chart symbol and remove or ignore prior subscriptions on symbol change. (`chartWsSymbols.clear()` + re-add on symbol set L1137–1138; `refreshLiveSubscriptions()` rebuilds)
- [x] Prevent delayed ticks from a previous symbol or stale batch from updating the current chart or header. (tick timestamp check `<2s` via `getLiveQuoteTimestamp` L6019; per-symbol guards L1169–1170)
- [x] Verify live ticks update the active candle, price line, and price labels without duplicate or out-of-order points. (`applyLiveDomQuotes` + live daily upsert replaces today's bar in place)
- [x] Define behavior for market-closed periods: show last close and a truthful market status rather than indefinite “Loading”. (`getMarketStatus()` gate L1179–1180; market-status banner L4707)
- [x] Display honest states for connecting, live, delayed, stale, disconnected, market closed, and feed error. (`setChartWsStatus` states + freshness display L5905–5926)
- [x] Show data freshness timestamp and source where available. (`updateChartFreshness` L5905, called after load L924)
- [x] Verify reconnect behavior after network interruption and ensure it does not create duplicate subscriptions. (WS client uses exponential backoff + REST fallback; subscription sets are rebuilt, not duplicated)

### Phase 5 — Chart controls and saved state

- [ ] Test symbol search, keyboard navigation, empty/no-match states, Enter, Escape, and explicit selection. *(Implemented in code: ArrowUp/ArrowDown cycle a `search-item-active` highlight, Escape closes the dropdown, Enter picks the highlighted result or raw input, click-outside closes; needs manual UI verification.)*
- [ ] Test all timeframe controls, chart reset, fit-content, auto-scale, fullscreen, and zoom controls. *(Pending manual verification.)*
- [x] Validate missing, malformed, or outdated local storage state and storage-disabled behavior. (`chart-state.js load()` whitelist-restores typed fields — symbol regex, resolution/chart-type whitelists, boolean indicators/crosshair flags, object drawings — and `clear()`s the storage entry on malformed JSON or a non-object payload; all `localStorage` access stays inside try/catch)
- [x] Restore symbol, interval, visible range, indicators, drawings, and theme without overriding an explicit symbol selection from another app area. (saved state applies only on direct Chart-tab navigation L1954–1960; explicit `openChart` calls always win)
- [x] Define whether drawings persist per symbol, per layout, or across symbols; implement and test that choice. *(Decision: drawings are not persisted — explicitly out of scope for the reliability fix; future feature.)*
- [ ] Confirm persisted chart state remains valid after a refresh and app version changes. *(Pending manual verification.)*

### Phase 6 — Regression scenarios

*(All pending manual verification — these are hands-on UI scenarios.)*

- [ ] Portfolio → Chart for several valid holdings.
- [ ] Portfolio → Chart for an invalid, delisted, or unsupported holding.
- [ ] Portfolio → another tab → Chart.
- [ ] Open Chart from search, watchlist, dashboard, alerts, Sentinel, and feature tables.
- [ ] Open Chart through the main navigation with no selected symbol.
- [ ] Rapidly select multiple symbols and confirm the final selection wins.
- [ ] Change symbol and timeframe rapidly while requests are pending.
- [ ] Navigate away during a request and return to Chart.
- [ ] Refresh with Chart as the last selected tab.
- [ ] Resize after loading; test narrow desktop, tablet, and mobile widths.
- [ ] Test slow network, offline mode, empty history, HTTP errors, and provider timeout.
- [ ] Confirm no uncaught console exceptions, duplicate chart initialization, or stale subscriptions.

## Review of `CHART_UX_DESIGN_RECOMMENDATIONS.md`

The document is a strong product-design direction. It covers symbol discovery, chart analysis, trader context, live-state honesty, mobile behavior, accessibility, and future chart capabilities. It correctly calls out several current gaps, including symbol search, crosshair information, trend drawings, and live/stale status.

Before using it as an implementation checklist, make these adjustments:

1. **Put reliability and data correctness first.** Add an initial phase for chart entry-point consistency, initialization order, request lifecycle, API error handling, data validation, and live update correctness.
2. **Separate current defects from future features.** Label recommendations as bug fixes, usability improvements, or later feature work. Replay, Fibonacci tools, cloud layouts, multi-chart views, and event markers are valuable roadmap items, but are not prerequisites for fixing the current reliability issue.
3. **Make acceptance criteria verifiable.** Define scenarios and pass conditions for statements such as “under 10 seconds” and “reconnects cleanly.” Include the entry points and failure cases in the regression checklist above.
4. **Define context preservation by action.** The design says symbol and interval changes should preserve trader context, while the current implementation calls `fitContent()` after data load. Specify whether symbol changes, interval changes, and layout restores preserve or reset drawings, visible range, and indicator state.
5. **Treat the entry-point layer as part of chart UX.** Include Portfolio, navigation, search, watchlist, alerts, Sentinel, and generated feature-table controls in the plan, with one consistent open-chart behavior.

## Recommended delivery order

1. Fix and consolidate chart entry points; guarantee initialization before loading.
2. Fix request ordering, stale-response handling, and error cleanup.
3. Validate history data and timeframe semantics.
4. Verify overlays and WebSocket lifecycle across symbol changes.
5. Run the regression scenarios above and record results.
6. Then implement the UX roadmap in the plan's Immediate, Next, and Later groups.

## Acceptance gate for the reliability work

*(Pending manual verification — opens only after the Phase 6 scenarios above.)*

- [ ] Every chart entry point opens the requested symbol exactly once and displays matching labels, candles, price, and live status.
- [ ] The chart loads correctly on first navigation from Portfolio and after navigating away and back.
- [ ] The newest symbol/timeframe selection wins when requests overlap.
- [ ] Empty history and failed requests show a recoverable error and leave controls usable.
- [ ] No old-symbol candles, overlays, prices, or live ticks appear under a new symbol.
- [ ] Direct navigation restores or loads the documented default symbol.
- [ ] Chart sizing, controls, and essential interactions work on desktop and mobile layouts.

## Verified-in-code summary (2026-11-14)

| Phase | Status |
|---|---|
| 0 — entry points | ✅ Implemented (`openChart` single entry, idempotent init, request IDs, symbol normalization, delegated `data-chart-symbol` handler) |
| 1 — request lifecycle | ✅ Implemented (latest-wins, error states, cleanup, HTML-escaped overlays) |
| 2 — sizing & validation | ✅ Implemented (candle validation, dimension polling, live-daily upsert, stored + disconnected ResizeObserver) |
| 3 — timeframes & overlays | ✅ Implemented (mappings + visible-range policy documented; always `fitContent()`) |
| 4 — live data | ✅ Implemented (per-symbol subs, tick freshness, market status) |
| 5 — saved state | ✅ Code-complete (whitelist-validated restore, keyboard nav for search; manual UI checks remain) |
| 6 — regression scenarios | ⬜ Open — manual UI verification |
| Acceptance gate | ⬜ Open — after Phase 6 |
