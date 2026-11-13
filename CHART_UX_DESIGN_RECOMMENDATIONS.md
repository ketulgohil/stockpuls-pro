# Chart User Experience Design Recommendations

## Purpose

This document captures design ideas inspired by TradingView's chart workflow and recommendations specific to StockPulse Pro.

The goal is to create a chart that feels familiar to experienced traders while remaining simpler, faster, and more useful for Indian market analysis.

The design should support four common actions:

1. Find a symbol quickly.
2. Read the current market structure accurately.
3. Mark a trade idea with indicators, drawings, and levels.
4. Monitor the idea and act through alerts or paper trading.

## Design Principles

### 1. Chart first

The chart canvas should receive most of the available space. Controls should be compact, grouped by task, and hidden when they are not needed.

### 2. Progressive disclosure

Show the essential controls first. Put advanced options inside searchable menus, settings panels, and context menus so the interface does not become a wall of buttons.

### 3. Every visual action should have a state

Users should always know whether a tool is active, whether data is live, whether an alert is saved, and whether a drawing has been persisted.

### 4. Preserve trader context

Changing a symbol or interval should not unexpectedly remove drawings, reset the visible range, or lose the user's selected indicators.

### 5. Indian market clarity

The platform should make NSE/BSE exchange, IST time, market session, circuit limits, gaps, and delayed or live data status clear.

## Current Design Observations

The current dedicated chart already has a good foundation:

- Watchlist sidebar: [static/index.html](static/index.html:637)
- Symbol header and live status: [static/index.html](static/index.html:677)
- Timeframe controls: [static/index.html](static/index.html:712)
- Strategy badges: [static/index.html](static/index.html:727)
- Drawing toolbar: [static/index.html](static/index.html:775)
- Fullscreen action: [static/index.html](static/index.html:763)
- Lightweight Charts rendering: [static/js/app.js](static/js/app.js:461)

The main design problems are hierarchy, density, and incomplete interaction behavior. The current layout labels itself TradingView-style, but several controls are still dashboard controls rather than a cohesive chart workspace. The trend-line tool is also only an approximation and the chart does not yet present a full crosshair legend, configurable indicator system, or saved workspace model.

## Recommended Chart Shell

```text
┌───────────────────────────────────────────────────────────────────────────┐
│ Symbol search  Exchange  Live status  Interval  Chart type  Indicators    │
│                                                   Alert  Layout  Settings  │
├───────┬───────────────────────────────────────────────────────────┬───────┤
│       │ Symbol · interval · OHLCV crosshair legend                │       │
│ Draw  │                                                           │Watch  │
│ tools │                         Price chart                       │list   │
│       │                                                           │       │
│       │                                                           │Details│
│       │                                                           │News   │
├───────┴───────────────────────────────────────────────────────────┴───────┤
│ Volume                                                                  │
│ RSI / MACD / selected indicator panes                                    │
├───────────────────────────────────────────────────────────────────────────┤
│ Replay  Scroll  Zoom  Auto scale  Market session  Data timestamp        │
└───────────────────────────────────────────────────────────────────────────┘
```

### Desktop behavior

- Keep the watchlist and context panel collapsible.
- Keep drawing tools in a narrow vertical rail.
- Keep the top toolbar one row where possible.
- Put indicator panes below price, with draggable separators.
- Keep the bottom navigation/status bar visible but quiet.

### Mobile behavior

- Convert the watchlist to a slide-in drawer.
- Convert the drawing rail to a bottom sheet.
- Keep symbol, price, interval, and fullscreen controls pinned at the top.
- Make the crosshair available through long press.
- Use horizontal scrolling for intervals and indicator chips.
- Make bottom indicator panes vertically scrollable.

## TradingView-Inspired Design Points to Implement

### 1. Top toolbar with task groups

TradingView's chart workflow groups symbol search, resolutions, indicators, layouts, and chart tools in the top toolbar. StockPulse Pro should use the same mental model.

Recommended order:

1. Symbol search
2. Exchange and session label
3. Interval selector
4. Chart type
5. Indicators
6. Compare
7. Alert
8. Replay
9. Layouts
10. Settings
11. Fullscreen

Design details:

- Use icon plus text for the most important actions.
- Use icon-only buttons only for familiar actions such as fullscreen, settings, and undo.
- Keep the active interval visible even when the interval menu is closed.
- Show a small dot or badge for unsaved workspace changes.
- Use separators between symbol controls, analysis controls, and workspace controls.

### 2. Searchable symbol picker

Replace the current text input and Load button with a command-like symbol picker.

Include:

- Symbol and company name
- Exchange: NSE, BSE, NFO, MCX where supported
- Instrument type
- Recent symbols
- Watchlist membership
- Live or delayed status
- Keyboard navigation
- Clear empty state and no-match state

Useful shortcuts:

- `/` or `Ctrl/Cmd + K`: open search
- Enter: load selected symbol
- Escape: close search
- Arrow keys: move through results

Avoid loading a symbol until the user selects a valid search result or explicitly confirms a valid ticker.

### 3. Crosshair data legend

The chart should show a compact legend at the top left of the canvas:

```text
RELIANCE · 5m
O 1,320.00  H 1,326.00  L 1,318.00  C 1,325.50  +5.50 (+0.42%)
VOL 151K  EMA20 1,319.20  VWAP 1,321.45
```

When the crosshair moves:

- Show the selected candle's time in IST.
- Show OHLC, change, percentage, and volume.
- Show values for visible indicators.
- Keep the legend stable while values change to prevent layout jumps.
- Show `Live` values only when the crosshair is on the last candle.

This is one of the highest value improvements because it turns the chart from a picture into an analysis instrument.

### 4. Proper price scale controls

Add controls directly on or beside the price scale:

- Auto scale
- Reset scale
- Log scale
- Percent scale
- Indexed to 100 for comparison
- Move scale left/right if the layout supports it
- Lock scale

Default to auto scale. Make manual scale changes explicit and reversible.

### 5. Clear chart type menu

Start with a focused set:

- Candles
- Bars
- Line
- Area
- Heikin Ashi

Each chart type should have a short tooltip explaining when it is useful. More advanced price-based types can be added later if the data model supports them.

### 6. Indicator picker with search and templates

Use a searchable modal or popover instead of permanently exposing indicators in the header.

Categories:

- Trend: SMA, EMA, Supertrend, Ichimoku
- Momentum: RSI, MACD, Stochastic, MFI
- Volatility: Bollinger Bands, ATR, Keltner Channels
- Volume: Volume, VWAP, OBV, volume average
- StockPulse: ORB, Camarilla pivots, signal levels, risk levels

Each indicator should expose:

- Period and source inputs
- Color and line style
- Visibility toggle
- Pane or overlay placement
- Remove action
- Reset to defaults

Add templates:

- Minimal
- Trend follower
- Intraday ORB
- Swing trading
- Risk management

### 7. Strong indicator legend interactions

Every visible indicator should appear in a chart legend with:

- Name and current value
- Color swatch
- Visibility toggle
- Settings button
- Remove button

Clicking an indicator line should select it. Double-clicking the legend item should open settings. This gives users direct control without forcing them into a large settings page.

### 8. Real drawing toolbar

The current horizontal drawing strip should become a compact tool rail.

Recommended first set:

- Cursor
- Crosshair
- Horizontal line
- Trend line
- Ray
- Parallel channel
- Rectangle
- Fibonacci retracement
- Text note
- Measure
- Price alert
- Delete selected
- Lock all
- Hide all

Use grouped flyout menus for advanced tools. Do not display twenty separate buttons at once.

Every drawing should support:

- Selection handles
- Move
- Edit style
- Duplicate
- Lock
- Hide
- Delete
- Undo and redo

The current trend tool should be corrected before adding more tools. A two-point trend line needs both time and price coordinates; drawing a second horizontal price line is confusing.

### 9. Context menu on the chart

Right-click or long press should open a context menu with actions relevant to the selected point:

- Add price alert at this level
- Add horizontal line
- Add vertical line at this time
- Copy price
- Copy timestamp
- Add note
- Add to watchlist
- Open symbol details
- Reset chart view

The menu should be positioned so it does not cover the selected candle.

### 10. Better watchlist rows

The watchlist should behave like a compact market monitor, not just a list of links.

Each row should show:

- Symbol
- Short company name
- Last price
- Absolute change
- Percentage change
- Session state
- Optional volume or alert badge

Interactions:

- Single click selects the symbol.
- Double click opens the chart and focuses the price area.
- Right-click opens row actions.
- Dragging reorders the list.
- Header click sorts by a selected column.
- A small alert icon shows whether the symbol has active alerts.

Add watchlist groups such as `Portfolio`, `Intraday`, `Swing`, and custom groups.

### 11. Make live state honest

The live badge should communicate the actual data condition:

- `Live`
- `Connecting`
- `Delayed`
- `Stale · 12s`
- `Market closed`
- `Feed error`

Show the last data timestamp and source in a tooltip or status drawer. Avoid using a green live badge when the chart is only displaying cached historical data.

### 12. Visible session context

For Indian markets, show:

- `NSE · Regular session`
- `09:15–15:30 IST`
- Pre-open, open, closing, or closed state
- Gap from previous close
- Whether the current candle is partial
- Market holiday or weekend state

Add a session shading option for pre-open, regular, and post-market periods where data exists.

### 13. Chart-linked alerts

The alert action should be a complete workflow:

1. User clicks Alert or right-clicks the chart.
2. A modal opens with symbol, price, interval, condition, trigger frequency, expiry, and delivery options.
3. The user saves the alert.
4. The chart displays a confirmed alert marker and price line.
5. The watchlist shows an alert badge.
6. Triggered alerts show their status and timestamp.

Conditions to support:

- Crosses above
- Crosses below
- Enters range
- Exits range
- Indicator crosses threshold
- Moving-average crossover
- ORB breakout

Do not show a chart line as an active alert until the server confirms that the alert exists.

### 14. Layouts and autosave

TradingView treats a layout as a saved workspace containing symbol, interval, chart type, indicators, drawings, colors, and settings. StockPulse Pro should adopt this concept.

Start with browser-local layouts:

- `Intraday ORB`
- `Swing Analysis`
- `Portfolio Review`
- `Minimal Price`

Include:

- Save
- Save as
- Rename
- Duplicate
- Delete
- Reset to default
- Autosave toggle
- Unsaved-changes indicator

Add server-side persistence only after authentication and user ownership are in place.

### 15. Quick search and command palette

Add a searchable command palette for advanced users.

Commands may include:

- Open symbol
- Change interval
- Add indicator
- Remove indicator
- Add drawing
- Toggle volume
- Toggle grid
- Toggle strategy overlays
- Save layout
- Reset chart
- Toggle fullscreen
- Open alerts

Use `Ctrl/Cmd + K` or `/` and show keyboard shortcuts in the empty state.

### 16. Replay mode

Bar Replay is valuable for testing ORB and intraday strategies. It should be a separate mode with a clear status banner.

Controls:

- Select historical start point
- Play
- Pause
- Step one candle
- Speed control
- Jump to timestamp
- Return to live

During replay:

- Stop the live candle update for the active chart.
- Keep the user informed that current prices are historical.
- Prevent new real-time alerts from being mistaken for replay events.
- Allow drawings and indicators to remain active.

### 17. Trade and risk visualization

StockPulse Pro can differentiate itself by making risk visible.

Add optional chart overlays for:

- Entry price
- Stop loss
- Target
- Position size
- Risk amount
- Reward amount
- Risk/reward ratio
- Break-even level
- Trailing stop

Add a long-position and short-position drawing tool that calculates risk and reward from two or three points. Keep it paper-trading aware and clearly label simulated orders.

### 18. News and fundamentals without leaving the chart

Add optional event markers along the time axis for:

- Earnings
- Dividends
- Splits
- Corporate announcements
- Block deals
- Major news
- FII/DII activity where date-aligned data exists

Clicking a marker should open a small detail popover, not navigate away from the chart.

### 19. Accessibility and keyboard quality

Trading tools are often used for long sessions, so keyboard and focus behavior matter.

- Every icon has a tooltip and accessible label.
- Active drawing tools use `aria-pressed="true"`.
- Focus is visible against the dark theme.
- Escape cancels the active drawing.
- Delete removes the selected drawing after a clear selection state.
- Tab order follows the visual workflow.
- Do not rely on color alone for positive, negative, live, or alert states.
- Provide a high-contrast mode.
- Use a minimum 44px touch target on mobile.

### 20. Performance and trust details

- Update the active candle instead of rebuilding all series on every tick.
- Keep only the visible or required history in memory.
- Debounce symbol search and interval changes.
- Cancel stale requests when the user changes symbols quickly.
- Avoid creating duplicate WebSocket subscriptions.
- Show a clear loading state without hiding the last valid chart unnecessarily.
- Show stale data instead of silently displaying old values as current.
- Preserve the visible range after a live update unless the user is at the right edge.
- Use a lightweight render path for watchlist updates.

## Visual Design Recommendations

### Color system

Keep the dark foundation, but reduce the number of competing accent colors.

Suggested semantic colors:

- Blue: interactive controls and selected state
- Green: positive change, target, confirmed live data
- Red: negative change, stop loss, error
- Amber: alerts, warnings, partial or stale state
- Purple: user drawings or custom annotations
- Gray: inactive controls and secondary labels

Use lower-opacity fills for overlays so candles remain readable.

### Typography

- Use a compact sans-serif for interface labels.
- Use a monospaced face only for prices, percentages, timestamps, and numeric values.
- Keep numeric columns right aligned.
- Use tabular numerals so values do not jump horizontally.
- Avoid using all caps for every chart control; reserve it for short status labels.

### Spacing

- Use 8px spacing inside controls.
- Use 12px between control groups.
- Use 16px between chart shell sections.
- Avoid large card padding around the chart canvas.
- Preserve at least 8px around the price scale and time scale.

### Motion

Use motion to communicate state, not decoration:

- Brief flash when price changes.
- Subtle slide when a panel opens.
- Short confirmation when an alert or drawing saves.
- No continuous animation except the live status indicator.
- Respect `prefers-reduced-motion`.

## StockPulse-Specific Ideas

These features would give the platform a distinct identity instead of becoming a TradingView clone.

### Intraday setup card

A collapsible card beside the chart can summarize:

- ORB high and low
- Current price versus ORB range
- Breakout status
- Stop loss
- Target
- Risk/reward ratio
- Signal confidence
- Data freshness

The card should be a compact decision aid and should never cover the candles by default.

### Indian session navigator

Add quick navigation buttons for:

- Pre-open
- First 15 minutes
- Morning session
- Lunch session
- Last hour
- Full day

This is especially useful for intraday users analyzing ORB, VWAP, and volume behavior.

### Strategy overlay presets

Allow users to turn on a complete setup with one click:

- ORB: candles, volume, VWAP, ORB high/low, target, stop
- Trend: EMA 20/50/200, volume, pivots
- Momentum: RSI, MACD, volume
- Risk: entry, stop, target, position sizing

### Replay journal

When replay ends, let the user save:

- Symbol and interval
- Replay date
- Screenshot or chart state
- Setup notes
- Trade direction
- Entry, stop, and target
- Result

This can become a practical learning and strategy review feature.

## Recommended Priority

### Immediate

- [ ] Consolidate the chart into one state model.
- [ ] Add crosshair OHLCV legend.
- [ ] Fix live candle updates.
- [ ] Replace the approximate trend line.
- [ ] Improve live, stale, delayed, and closed status states.
- [ ] Improve the symbol search experience.
- [ ] Add chart reset, auto-scale, and fit-content controls.

### Next

- [ ] Add chart type selector.
- [ ] Add indicator picker and indicator legend.
- [ ] Add chart-linked alert creation.
- [ ] Add drawing selection, editing, locking, deleting, undo, and redo.
- [ ] Add saved local layouts.
- [ ] Add sortable watchlist rows and context actions.

### Later

- [ ] Add Fibonacci, channels, shapes, notes, and measure tools.
- [ ] Add compare-symbol mode.
- [ ] Add news and corporate event markers.
- [ ] Add replay mode.
- [ ] Add risk/reward position drawing.
- [ ] Add multi-chart layouts.
- [ ] Add authenticated cloud persistence.

## Acceptance Checklist

- [ ] A new user can search for a stock and open its chart without guessing symbol format.
- [ ] An experienced user can change interval, add an indicator, and create a price alert in under 10 seconds.
- [ ] The chart always shows whether data is live, delayed, stale, or historical.
- [ ] Crosshair movement provides enough information to analyze a candle without opening another panel.
- [ ] A drawing can be selected, edited, hidden, locked, deleted, undone, and restored.
- [ ] Switching symbols preserves the workspace and does not show stale data.
- [ ] The active candle moves with live data and reconnects cleanly after a network interruption.
- [ ] The watchlist supports fast symbol switching without losing the selected row.
- [ ] The same chart remains usable on desktop, tablet, and mobile.
- [ ] Keyboard users can access all important chart actions.
- [ ] The interface does not rely on color alone to communicate trading state.
- [ ] User drawings, alerts, and layouts have clear saved or unsaved state.
- [ ] StockPulse-specific ORB and risk tools are easy to find without overwhelming standard chart controls.

## Reference Material

- [TradingView Supercharts toolbar overview](https://www.tradingview.com/charting-library-docs/latest/ui_elements/Toolbars/)
- [Getting started with Supercharts](https://www.tradingview.com/support/solutions/43000746464-getting-started-with-supercharts/)
- [TradingView chart settings](https://www.tradingview.com/support/solutions/43000547759-how-to-use-chart-settings/)
- [TradingView autoscale](https://www.tradingview.com/support/solutions/43000762826-how-to-enable-autoscale/)
- [TradingView alert configuration](https://www.tradingview.com/support/solutions/43000763312-learn-how-to-configure-alerts/)
- [TradingView layouts](https://www.tradingview.com/support/solutions/43000746975-tradingview-layouts-a-quick-guide/)
- [TradingView quick search](https://www.tradingview.com/support/solutions/43000659671-quick-search-on-tradingview-find-anything-super-fast/)

## Final Recommendation

The most valuable first change is to make the chart feel precise and trustworthy before adding a large number of tools. Implement the crosshair legend, live candle updates, clean symbol search, reliable drawing selection, clear data status, and chart-linked alerts first.

Once those foundations work well, add configurable indicators, layouts, replay, and advanced drawings. Keep ORB, Indian session context, and risk visualization as the platform's distinctive layer.



I want you to add an end-to-end stock recommendation and performance-tracking feature to this existing app. First inspect the repository and identify how its current portfolio, signals, data providers, charts, database, background jobs, and frontend work. Do not assume prior documentation is accurate if the code differs.

The app is an Indian stock-market analytics platform. The repository has used FastAPI/Python, a JavaScript frontend, Upstox market data, and portfolio data stored in local files. Relevant areas may include:
- core/signals.py and api/signals.py for technical BUY/SELL signals
- core/intraday/signals.py and api/upstox_trading.py for intraday confluence signals
- core/ai_analysis.py for combined analysis and news sentiment
- api/portfolio.py and core/portfolio.py for holdings
- static/js/app.js and static/index.html for portfolio UI
- db/ and core/trader_core/storage/ for persistence

Verify which of these are currently used before choosing an implementation. Reuse the app’s existing data and signal sources where appropriate. Do not replace the existing stack or create a second recommendation system without explaining why.

## Product goal

For every stock currently in the user’s portfolio, show an app-generated recommendation:
- BUY
- SELL
- HOLD
- NO_DATA / NOT_ENOUGH_DATA when the app cannot support a recommendation

Recommendations should be based on the app’s existing analysis tools and relevant portfolio context. At minimum, consider available technical signals, trend, timeframe, and current holding information such as average buy price and quantity. If a reliable recommendation cannot be customized with the available information, say so in the UI rather than inventing user preferences or data.

Clearly distinguish:
- A daily/swing recommendation based on historical technical data
- An intraday signal based on live intraday data

Do not mix these into one unlabeled recommendation. Show the recommendation’s timeframe, generated timestamp, data timestamp/source, and a concise explanation of the signals that contributed to it. Show the contributing signals even when they conflict.

## Recommendation rules and trust

- Inspect and document the current signal logic before implementing aggregation.
- Define a transparent, deterministic method for combining signals into BUY/SELL/HOLD. Explain how conflicting signals, neutral results, insufficient history, stale prices, and provider failures are handled.
- Do not label a signal “AI” unless an actual AI model generated it.
- Never display BUY/SELL/HOLD as guaranteed, certain, or personalized financial advice.
- Do not place live broker orders. Recommendations are informational and must not change portfolio quantities or cash.
- Keep user-authored notes or labels separate from generated recommendations.

## Daily scans

Scan every current portfolio holding once per NSE trading day, after the regular market session, using Asia/Kolkata time. Verify whether the project already has a scheduler and use it if suitable. The scan must:
- Include every holding present at scan time.
- Run outside request handling so opening the portfolio does not wait for a full scan.
- Recover safely after an app restart and avoid running the same completed scan repeatedly that day.
- Record scan completion, failures, and per-symbol data availability.
- Avoid overwriting concurrent portfolio changes.
- Show the latest available recommendation and its age if today’s scan has not completed.
- Handle weekends and market holidays sensibly; if holiday data is unavailable, state the limitation rather than pretending the scan ran on a trading day.
- Offer an explicit manual rescan only if it can be rate-limited and made safe.

## Track whether recommendations worked

Persist an immutable record for each generated recommendation. Do not overwrite the original recommendation when later scans produce a new one. Include enough information to reproduce and evaluate it, such as:
- Symbol and exchange
- Recommendation and horizon/timeframe
- Generated time and market-data “as of” time
- Entry/reference price at generation
- Signal scores, reasons, and strategy/version
- Relevant holding context at generation, where available
- Evaluation status and evaluation timestamps

Define “worked” before implementing it. Evaluate recommendations over explicit horizons suitable for the recommendation type, for example the next trading session, 5 trading sessions, and 20 trading sessions for daily recommendations. Define objective outcomes such as:
- Forward return after estimated fees/slippage
- Whether price moved in the recommended direction
- Maximum favorable/adverse movement, if the required data is available
- Whether an explicit target or stop was reached, only if the strategy defines those levels

For HOLD, define a meaningful outcome, such as avoided downside or remaining within a specified neutral range. Do not count a HOLD as a success merely because no BUY/SELL target exists.

Prevent look-ahead bias:
- Use only data available at recommendation time.
- Do not evaluate against a price that predates the recommendation timestamp.
- Handle market closures, missing candles, splits, bonuses, dividends, and delisted/unavailable symbols.
- Record estimated transaction costs and slippage, or clearly label results as gross returns if costs cannot be modeled.
- Mark incomplete horizons as pending, not as failures.

## Performance dashboard

Add a portfolio recommendation-performance view with:
- Total recommendations and counts by BUY/SELL/HOLD/NO_DATA
- Success rate with the exact success definition visible
- Average and median forward return by recommendation, horizon, and strategy
- Benchmark comparison, preferably an appropriate Indian market index when reliable data is available
- Pending, failed-to-evaluate, and stale-data counts
- Filters by date range, symbol, recommendation type, horizon, and strategy version

Show sample size and uncertainty. Do not present a success rate without its denominator, evaluation horizon, or success definition. Avoid claiming predictive power from a small sample.

## Engineering requirements

1. Map the existing code flow and data ownership before changing files.
2. Propose a short implementation plan based on what is actually present.
3. Implement the backend recommendation service, persistence, daily scan, outcome evaluator, and authenticated API endpoints using the project’s existing patterns.
4. Implement the portfolio recommendation column and performance view in the existing frontend.
5. Add database migrations if required. Prefer durable shared storage for production; do not treat ephemeral local files or an in-memory cache as durable history.
6. Use Asia/Kolkata consistently for market-day boundaries and timestamps.
7. Make provider timeouts, rate limits, missing data, retries, and duplicate scans explicit.
8. Keep request handlers responsive and avoid fetching history once per holding every time the portfolio page opens.
9. Add tests for aggregation rules, time boundaries, duplicate scheduling, persistence, concurrent portfolio changes, no-data handling, evaluation horizons, look-ahead prevention, and performance calculations.
10. Run the relevant tests and report their results. Do not claim success if tests were not run.

## Acceptance criteria

- Every portfolio holding displays the latest generated recommendation, its horizon, timestamp, and concise rationale—or an honest NO_DATA state.
- A daily scan covers all current holdings and persists a result that survives reloads/restarts.
- A new recommendation creates a new immutable history record instead of overwriting prior results.
- Outcomes remain pending until their defined evaluation horizon is complete.
- Performance statistics can be traced to stored records and their visible definitions.
- Recommendations never execute trades or mutate holding quantities.
- Missing, stale, conflicting, or incomplete data is visible and cannot silently become a confident BUY or SELL.
- The existing chart, portfolio, signals, and live-data flows continue to work.

At completion, summarize:
- What existing tools and data sources you reused
- The recommendation and success definitions
- Files changed and any migration steps
- Scheduler behavior and operational assumptions
- Tests run and their outcomes
- Known limitations and any data source required for production reliability