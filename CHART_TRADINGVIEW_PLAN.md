# TradingView Style Chart Upgrade Plan

## Goal

Upgrade the StockPulse Pro chart from a styled candlestick dashboard into a dependable TradingView-style analysis workspace.

The target experience should make the chart fast to use for symbol discovery, timeframe changes, technical analysis, drawing, alerts, and saved workspaces while preserving the application's Indian market focus, Upstox data, ORB levels, and existing strategy overlays.

This document is a planning artifact. It does not change the implementation.

## Current Chart Assessment

### Existing implementation

The current application uses Lightweight Charts 4.1.3 from the browser:

- [static/index.html](static/index.html:11)
- [static/js/app.js](static/js/app.js:237)
- [static/js/app.js](static/js/app.js:461)

The dedicated chart view already includes:

- Candlestick chart
- Volume histogram
- EMA 9, 21, 50, and 200 overlays
- VWAP and VWAP bands for intraday views
- Camarilla pivot price lines for non-intraday views
- ORB high, stop loss, and target levels
- Live price line from the WebSocket feed
- Symbol input and stock search
- Watchlist sidebar
- Timeframe buttons
- Fullscreen mode
- Basic horizontal line, trend, and price alert controls
- Bar close countdown for intraday timeframes

Relevant UI: [static/index.html](static/index.html:634)

### Current limitations

#### 1. Two chart implementations are maintained

The code has both the original dashboard chart and the dedicated chart:

- `initChart()` with `chart`, `candleSeries`, and `volumeSeries`
- `initChartChart()` with `chartChart`, `candleSeriesChart`, and `volumeSeriesChart`

This duplicates indicator, drawing, resizing, strategy-line, and timer logic. Future features can easily be implemented in one chart and forgotten in the other.

#### 2. Timeframes are mostly fixed presets

The current timeframe mapping is:

| UI label | Historical period | Candle interval |
|---|---:|---:|
| 1D | 1 year | 1 day |
| 5D | 1 year | 1 day |
| 1M | 2 years | 1 month |
| 3M | 2 years | 1 month |
| 6M | 2 years | 1 month |
| 1Y | 5 years | 1 month |
| 5M | 1 day | 5 minutes |
| 15M | 1 day | 15 minutes |
| 30M | 1 day | 30 minutes |
| 1H | 1 day | 1 hour |

This means labels such as `1D` and `5D` do not currently represent visible ranges in the same way a TradingView user expects. There is also no 2H, 4H, weekly, quarterly, or custom range selection.

Relevant code: [static/js/app.js](static/js/app.js:568)

#### 3. Drawing support is only a visual approximation

Horizontal lines use price lines correctly. The trend line implementation records two points but draws only a horizontal price line at the second point. It does not represent a line between two time and price coordinates.

Price alert drawings also create a visual line but do not create or persist a server-side alert rule.

Relevant code: [static/js/app.js](static/js/app.js:989)

#### 4. Indicators are fixed rather than user configurable

EMA and VWAP series are created in code and are not managed through an indicator picker. Users cannot add, remove, reorder, or configure periods from the chart interface. RSI and MACD are displayed as telemetry values, but the dedicated chart does not present a full configurable oscillator pane comparable to TradingView.

Relevant code: [static/js/app.js](static/js/app.js:516), [static/index.html](static/index.html:747)

#### 5. Chart interaction and context are incomplete

The chart is missing or only partially supports:

- OHLC and change legend tied to the crosshair position
- Crosshair tooltip with exact time, OHLC, and volume
- Right-click context menu
- Pan and zoom controls with predictable reset behavior
- Chart type selection
- Compare-symbol overlays
- Session and extended-hours controls
- Saved indicator templates
- Saved drawings and layouts
- Bar Replay
- Alerts created from chart conditions
- Visible loading and stale-data state tied to the data timestamp

#### 6. The current drawing toolbar is placed below the telemetry row

TradingView users generally expect the main chart toolbar to be immediately adjacent to the chart canvas, with drawing tools in a dedicated vertical or compact toolbar. The current layout presents the tools as a horizontal strip and exposes only four actions: H-Line, Trend, Alert, and Clear.

Relevant UI: [static/index.html](static/index.html:775)

#### 7. Live updates do not update the current candle

The WebSocket handler updates the header price and draws a live price line. The current candle series is not clearly updated with the incoming tick, so the chart can show a static last candle while the price label moves.

Relevant code: [static/js/app.js](static/js/app.js:935)

#### 8. State is not organized as a chart workspace

The chart stores a few values in global variables and `localStorage`, but there is no single persisted workspace model for:

- Symbol
- Timeframe
- Chart type
- Visible indicators and settings
- Drawing objects
- Alert rules
- Panel heights
- Theme
- Watchlist selection

This will make later persistence and synchronization work harder unless the state model is consolidated first.

## TradingView Comparison

The comparison below uses TradingView's current Supercharts interaction model as the reference point. The goal is to reproduce the useful workflow and information hierarchy, not to copy proprietary visual assets or branding.

| Area | Current StockPulse Pro | TradingView reference behavior | Upgrade direction |
|---|---|---|---|
| Symbol search | Text input and Load button | Search integrated into chart header with autocomplete and exchange context | Build a symbol search popover with recent symbols, exchange, name, and keyboard navigation |
| Timeframes | Fixed buttons with limited resolution mapping | Interval selector with broad resolutions and custom intervals | Add resolution registry, interval menu, favorites, and custom range handling |
| Chart types | Candlestick only in the dedicated chart | Candles, bars, line, area, baseline, Heikin Ashi, and other types | Deliver candles, line, area, and Heikin Ashi first |
| Crosshair | Library crosshair is enabled | Crosshair shows synchronized time and exact values in a legend | Add an OHLCV legend and crosshair state model |
| Indicators | Fixed EMA, VWAP, pivots, and strategy lines | Searchable indicator library with settings and templates | Add indicator registry, picker, settings dialogs, and pane/overlay placement |
| Drawing tools | Horizontal line, approximate trend line, alert line | Trend lines, channels, Fibonacci, shapes, text, measurement, magnet, lock, hide, delete | Implement a small reliable core first, then expand tool categories |
| Watchlist | Sidebar with add/remove and live values | Watchlist with symbol details, sorting, context actions, and alerts | Add sortable rows, selected-row state, context menu, and quick chart actions |
| Alerts | Separate alert systems exist elsewhere in the application; chart line is visual | Alerts can be created from a symbol, price, indicator, or drawing condition | Connect chart actions to the existing alert API and show lifecycle state |
| Replay | Not available | Bar Replay selects a historical starting bar and plays forward | Add replay after historical data and chart state are stable |
| Layouts | No chart workspace save model | Layouts preserve chart setup and can support multiple panes/charts | Add local saved layouts first, then optional server persistence |
| Multi-chart | Separate multi-chart feature exists | Multiple charts can be synchronized by symbol, interval, crosshair, and time | Add a chart grid only after the single-chart model is complete |
| Toolbar structure | Top header plus horizontal drawing row | Top toolbar, left drawing toolbar, right product/watchlist rail, bottom panel | Reorganize around a compact chart shell with clear tool zones |
| Data behavior | REST history plus WebSocket header/live price line | Historical and real-time data form one continuous chart | Update the active candle from ticks and reconcile with periodic REST refresh |

TradingView's official Supercharts guide describes the top toolbar for symbols, intervals, chart types, indicators, layouts, and tools; the left toolbar for drawing tools; and the right toolbar for watchlists, news, and alerts. Its chart type documentation also covers classic, price-based, and volume-oriented chart modes. These are the main interaction patterns used in this plan.

References:

- [Getting started with Supercharts](https://www.tradingview.com/support/solutions/43000746464-getting-started-with-supercharts/)
- [Chart types available on TradingView](https://www.tradingview.com/support/solutions/43000703407-chart-types-available-on-tradingview/)
- [TradingView indicators documentation](https://www.tradingview.com/charting-library-docs/latest/ui_elements/indicators/)
- [TradingView watchlist alerts](https://www.tradingview.com/support/solutions/43000739708-watchlist-alerts-your-trading-edge/)
- [TradingView Bar Replay](https://www.tradingview.com/support/solutions/43000474069-bar-replay/)

## Product Direction

### Recommended target layout

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Symbol · exchange · interval · chart type · indicators · alert      │
├───────┬─────────────────────────────────────────────────────┬───────┤
│ Draw  │ Chart canvas                                       │ Data  │
│ tools │                                                     │watch  │
│       │                                                     │news   │
├───────┴─────────────────────────────────────────────────────┴───────┤
│ Volume / RSI / MACD / other indicator panes                         │
├─────────────────────────────────────────────────────────────────────┤
│ Replay · scroll · range · status · data timestamp                    │
└─────────────────────────────────────────────────────────────────────┘
```

On smaller screens, the left and right rails should collapse into drawers and the bottom indicator panes should become vertically scrollable.

## Implementation Plan

### Phase 0: Stabilize and consolidate the chart foundation

Objective: create one chart engine before adding more features.

- [x] Decide whether the dashboard chart and dedicated chart should share one reusable chart component.
- [x] Create a chart state object instead of relying on duplicated globals.
- [x] Create a `ChartController` or equivalent module responsible for initialization, loading, resizing, cleanup, and subscriptions.
- [x] Create a data adapter that normalizes all historical candles to one shape: `time`, `open`, `high`, `low`, `close`, `volume`.
- [x] Create a live update adapter that normalizes WebSocket ticks and updates the active candle.
- [x] Remove duplicated EMA, VWAP, pivot, strategy-line, and timer implementations after parity is confirmed.
- [x] Add explicit cleanup for chart instances, ResizeObservers, timers, WebSocket subscriptions, and series.
- [x] Define error, empty, loading, stale, and disconnected states.

Suggested files:

- `static/js/chart/chart-controller.js`
- `static/js/chart/chart-state.js`
- `static/js/chart/data-adapter.js`
- `static/js/chart/chart-renderer.js`
- `static/js/chart/indicator-registry.js`
- `static/js/chart/drawing-manager.js`

### Phase 1: Rebuild the chart shell and toolbar

Objective: match the information hierarchy and navigation pattern users expect from a professional chart.

- [x] Replace the current symbol input and Load button with a symbol-search popover.
- [x] Show symbol, company name, exchange, market status, currency, and data source in the chart header.
- [x] Add recent symbols and keyboard navigation with Enter, Escape, and arrow keys.
- [x] Add an interval selector with grouped choices: seconds where available, minutes, hours, days, weeks, and months.
- [x] Mark favorite intervals and persist them per user/browser.
- [x] Add chart type selector.
- [x] Add buttons for Indicators, Alerts, Replay, Layouts, Settings, and Fullscreen.
- [x] Move drawing tools to a compact vertical rail on desktop.
- [x] Add a right-side panel toggle for Watchlist, Details, News, and Alerts.
- [x] Add a compact bottom status bar showing exchange session, live/stale state, candle interval, and last update time.
- [x] Keep the existing ORB, target, and stop-loss levels visible as a strategy overlay toggle.

### Phase 2: Correct historical and real-time data behavior

Objective: make timeframe selection predictable and make the live chart continuous.

- [x] Define a backend resolution contract instead of using the current UI label as both range and interval.
- [x] Separate `resolution` from `visibleRange`.
- [x] Add API support for daily, weekly, monthly, 1-minute, 3-minute, 5-minute, 15-minute, 30-minute, 1-hour, 2-hour, and 4-hour candles where the provider supports them.
- [x] Use the correct historical range for each resolution.
- [x] Add pagination or chunking for larger history requests.
- [x] Normalize timestamps to a documented timezone convention, retaining exchange-local display formatting.
- [x] Update the active candle from WebSocket ticks using an interval bucket.
- [x] Reconcile live candles with REST data after reconnect and on interval changes.
- [x] Show a stale-data banner when the last quote exceeds a threshold.
- [x] Prevent out-of-order responses from replacing a newer symbol or timeframe selection.
- [x] Add server-side rate limiting and cache keys based on symbol, resolution, and range.

Potential backend locations:

- `api/stocks.py`
- `core/data_fetcher.py`
- `core/upstox/client.py`
- `core/upstox/stream.py`

### Phase 3: Crosshair, legend, navigation, and chart controls

Objective: make reading the chart precise and fast.

- [x] Subscribe to crosshair movement.
- [x] Display OHLC, absolute change, percentage change, and volume for the selected candle.
- [x] Display indicator values at the selected candle.
- [x] Add a symbol legend with visibility toggles for each overlay.
- [x] Add reset chart view and fit-content actions.
- [x] Add zoom in, zoom out, auto-scale, and lock-scale controls.
- [x] Support mouse wheel zoom, drag-to-pan, touch pinch zoom, and long-press crosshair.
- [x] Add keyboard shortcuts for symbol search, interval selection, reset, fullscreen, and drawing cancellation.
- [x] Preserve the last visible logical range when switching between compatible resolutions.
- [x] Add a visible current-price marker and a configurable price line.

### Phase 4: Indicators and panes

Objective: move from fixed overlays to a configurable analysis system.

- [x] Create an indicator registry with metadata: name, category, inputs, output type, colors, pane, and default visibility.
- [x] Add an indicator picker with search and categories.
- [x] Support overlay indicators and separate oscillator panes.
- [x] Add settings forms for EMA, SMA, RSI, MACD, Bollinger Bands, VWAP, ATR, ADX, and volume.
- [x] Allow indicators to be hidden, removed, reordered, and reset to defaults.
- [x] Add per-indicator color, line width, and style settings.
- [x] Add indicator value labels to the crosshair legend.
- [x] Save indicator configurations in the chart workspace.
- [x] Add indicator templates such as `Trend`, `Intraday`, `ORB`, and `Minimal`.
- [x] Keep ORB and Indian-market strategy overlays in a separate `StockPulse` category.

### Phase 5: Reliable drawing tools

Objective: make drawings useful for actual chart analysis.

- [ ] Replace the approximate trend-line implementation with a coordinate-aware drawing model.
- [ ] Store drawings as objects with `id`, `type`, `symbol`, `resolution`, `points`, `style`, `locked`, `visible`, and timestamps.
- [ ] Implement horizontal line.
- [ ] Implement true trend line.
- [ ] Implement parallel channel.
- [ ] Implement rectangle and ellipse.
- [ ] Implement Fibonacci retracement.
- [ ] Implement vertical line and date marker.
- [ ] Implement text annotation.
- [ ] Implement measure tool showing bars, time, price change, percentage change, and approximate risk/reward.
- [ ] Add magnet mode to snap points to OHLC values.
- [ ] Add lock, hide, duplicate, edit, and delete actions.
- [ ] Add undo and redo for drawings.
- [ ] Add `Clear drawings` with a confirmation step.
- [ ] Persist drawings locally first and optionally server-side after authentication is available.
- [ ] Ensure drawings survive symbol reload, timeframe changes, page refresh, and fullscreen changes.

Implementation note: Lightweight Charts 4.x does not provide the full TradingView drawing object system. Drawing overlays should therefore be implemented as a separate plugin layer using primitives or synchronized HTML/canvas overlays, with chart coordinate conversions kept in one manager.

### Phase 6: Chart alerts

Objective: turn chart markings into reliable alert workflows.

- [ ] Reuse the existing alert service instead of creating a second unrelated alert model.
- [ ] Create price alerts from the chart context menu and alert line.
- [ ] Support crossing above, crossing below, entering a range, and leaving a range.
- [ ] Support indicator conditions such as RSI threshold and moving-average crossover.
- [ ] Add alert frequency, session, expiry, and notification preferences.
- [ ] Show active alert markers on the chart.
- [ ] Show alert state in the right panel: active, triggered, paused, expired, and failed.
- [ ] Add browser notifications and connect Telegram only through the authenticated server path.
- [ ] Avoid treating a visual price line as an active alert until the server confirms creation.
- [ ] Add audit events for alert creation, update, trigger, and deletion.

Relevant existing areas to integrate:

- `api/alerts.py`
- `api/advanced.py`
- `static/js/app.js` alert functions

### Phase 7: Watchlist and right-side context panel

Objective: make the chart workspace useful without leaving the chart.

- [ ] Add sortable watchlist columns for last price, change, percentage, volume, and market state.
- [ ] Add selected-symbol highlighting.
- [ ] Add row actions for open chart, add alert, remove, and open details.
- [ ] Add watchlist groups such as `My Watchlist`, `Intraday`, `Portfolio`, and custom groups.
- [ ] Add context panel tabs for Details, News, Fundamentals, and Alerts.
- [ ] Keep the active symbol, watchlist selection, and chart URL state synchronized.
- [ ] Add loading and stale states per row.
- [ ] Replace inline `onclick` string construction with event delegation and DOM-created elements.

### Phase 8: Layouts, persistence, and replay

Objective: support repeatable analysis workflows.

- [ ] Define a versioned workspace schema.
- [ ] Save symbol, resolution, chart type, visible range, indicators, drawings, pane heights, theme, and sidebar state.
- [ ] Add named layouts with create, rename, duplicate, and delete actions.
- [ ] Start with `localStorage` for a single-user local workflow.
- [ ] Add authenticated server persistence after the application has user identity and authorization.
- [ ] Add multiple chart panes only after the single-chart workspace is stable.
- [ ] Add synchronized crosshair and time range for multi-chart layouts.
- [ ] Add Bar Replay using historical candles, with play, pause, step, speed, jump-to-time, and return-to-live.
- [ ] Disable or clearly label real-time-only features during replay.

### Phase 9: Visual polish and accessibility

Objective: make the professional layout usable across desktop and mobile.

- [ ] Use a restrained toolbar hierarchy with consistent icon buttons and tooltips.
- [ ] Make active tool, active interval, and live state visually distinct.
- [ ] Add keyboard focus states to every chart control.
- [ ] Add accessible labels and `aria-pressed` state updates for tool buttons.
- [ ] Ensure the chart does not resize to zero when switching tabs.
- [ ] Test fullscreen, browser zoom, window resize, and device rotation.
- [ ] Collapse side panels into drawers below tablet width.
- [ ] Preserve chart usability at 1280px, 1024px, 768px, and narrow mobile widths.
- [ ] Use DOM APIs or a safe escaping helper for all external and server-provided values.

## Recommended Delivery Sequence

### MVP: professional single chart

- [ ] Consolidate chart state and remove duplicate chart logic.
- [ ] Fix resolution and visible-range semantics.
- [ ] Update the active candle from live ticks.
- [ ] Add crosshair OHLCV legend.
- [ ] Add chart type selection for candles, line, and area.
- [ ] Add indicator picker for EMA, SMA, VWAP, RSI, MACD, Bollinger Bands, and volume.
- [ ] Implement true horizontal and trend lines with persistence.
- [ ] Add chart-linked price alerts.
- [ ] Add workspace persistence in local storage.

### V2: advanced analysis workspace

- [ ] Add Fibonacci, channels, rectangles, text, and measure tools.
- [ ] Add indicator templates and per-indicator settings.
- [ ] Add watchlist sorting, groups, and context panels.
- [ ] Add saved named layouts.
- [ ] Add browser and Telegram alert delivery.
- [ ] Add compare-symbol overlays.
- [ ] Add synchronized multi-chart layout.

### V3: replay and trading workflow

- [ ] Add Bar Replay.
- [ ] Add strategy annotations and trade markers.
- [ ] Add paper-trading order markers and position lines.
- [ ] Add risk/reward measurement tied to paper positions.
- [ ] Add authenticated server-side workspace persistence.
- [ ] Add audit history for alerts, drawings, layouts, and trading actions.

## Data and API Changes

### Historical candle endpoint

Recommended request shape:

```text
GET /api/stocks/{symbol}/history
    ?resolution=5m
    &from=2026-11-01T09:15:00+05:30
    &to=2026-11-09T15:30:00+05:30
    &limit=5000
```

Recommended response shape:

```json
{
  "symbol": "RELIANCE",
  "exchange": "NSE",
  "resolution": "5m",
  "timezone": "Asia/Kolkata",
  "data_as_of": "2026-11-09T12:30:00+05:30",
  "candles": [
    {
      "time": "2026-11-09T09:15:00+05:30",
      "open": 1320.0,
      "high": 1325.0,
      "low": 1318.0,
      "close": 1323.0,
      "volume": 120000
    }
  ]
}
```

### Live candle event

```json
{
  "type": "candle_update",
  "symbol": "RELIANCE",
  "resolution": "5m",
  "candle": {
    "time": "2026-11-09T12:30:00+05:30",
    "open": 1320.0,
    "high": 1326.0,
    "low": 1318.0,
    "close": 1325.5,
    "volume": 151000
  },
  "quote": {
    "last_price": 1325.5,
    "change": 5.5,
    "change_percent": 0.42
  },
  "data_as_of": "2026-11-09T12:34:18+05:30"
}
```

### Workspace schema

```json
{
  "version": 1,
  "symbol": "RELIANCE.NS",
  "resolution": "5m",
  "chart_type": "candles",
  "visible_range": { "from": 0, "to": 200 },
  "indicators": [],
  "drawings": [],
  "panels": { "volume": 0.18, "oscillator": 0.22 },
  "sidebar": { "watchlist": true, "context": false },
  "theme": "dark"
}
```

## Acceptance Criteria

- [ ] Switching symbol does not display stale candles from the previous symbol.
- [ ] Switching resolution requests the matching candle interval and visible range.
- [ ] Live ticks update the current candle and price marker without rebuilding the full chart.
- [ ] Crosshair shows the correct candle time, OHLC, volume, and active indicator values.
- [ ] Users can add, configure, hide, reorder, and remove indicators.
- [ ] Trend lines use both selected time and price points.
- [ ] Drawings survive a refresh when the workspace is saved.
- [ ] Chart price alerts create a real alert and show confirmation or failure.
- [ ] Watchlist rows update live without losing the selected symbol.
- [ ] Fullscreen and resize preserve chart dimensions and controls.
- [ ] The chart remains usable at desktop, tablet, and mobile widths.
- [ ] External data is escaped before insertion into the DOM.
- [ ] No new chart feature creates a second independent data subscription for the same symbol.
- [ ] Historical and live timestamps remain consistent with Indian market sessions.

## Risks and Decisions

### Lightweight Charts versus TradingView Charting Library

Lightweight Charts is already integrated and is appropriate for a custom, open chart surface. It will require custom work for drawings, indicator management, panes, layouts, and replay.

TradingView's Advanced Charts or Trading Platform libraries would provide more built-in chart interactions, but they introduce licensing, integration, datafeed, and product constraints. This decision should be made before implementing a large drawing system.

Recommended decision for the first release: continue with Lightweight Charts and build a small, well-defined chart plugin layer. Re-evaluate the library only if drawing, replay, or multi-pane requirements exceed the maintenance budget.

### Real-time data quality

The chart experience depends on reliable candle aggregation. Tick volume semantics, exchange sessions, reconnects, missing ticks, corporate actions, and market holidays should be handled by the data adapter rather than by individual UI features.

### Existing strategy overlays

ORB, target, stop-loss, VWAP, and pivot overlays are valuable differentiators. They should remain available, but they should be grouped under a clearly labeled StockPulse overlay section so they do not clutter the standard TradingView-style indicator workflow.

## Suggested First Implementation Slice

The first coding slice should be small enough to review visually and functionally:

1. Consolidate the dedicated chart into a single chart controller.
2. Add a resolution registry and correct the current timeframe labels.
3. Add crosshair OHLCV legend and active candle updates.
4. Replace the approximate trend line with a real two-point overlay.
5. Add a simple indicator picker for EMA, SMA, VWAP, RSI, and MACD.
6. Save symbol, resolution, indicators, and drawings in a versioned local workspace.
7. Add a chart-linked price alert confirmation flow.

This slice establishes the core architecture and delivers the most noticeable improvement in daily chart usability before adding replay, multi-chart layouts, or advanced drawing categories.
