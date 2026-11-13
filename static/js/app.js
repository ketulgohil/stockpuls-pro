let chart = null;
let candleSeries = null;
let volumeSeries = null;
let currentSymbol = 'RELIANCE';
let currentTimeframe = '1d';
let liveInterval = null;

// Chart indicator series (from Indian Day Trader)
let emaSeries = {};      // ema9, ema21, ema50, ema200
let vwapSeries = {};     // vwap, upper1, lower1, upper2, lower2
let oscChart = null;
let oscSeries = { rsi: null, macd: null, signal: null, hist: null };
let pivotLines = [];
let patternMarkers = [];

// Strategy level price lines (ORB / Target / Stop)
let lineBreakout = null;
let lineTarget = null;
let lineStopLoss = null;
let orbLevels = null;
let barTimerInterval = null;

// Active indicators state
const activeIndicators = { ema: true, vwap: true, pivots: true, patterns: true, oscillator: false };

// Price formatter - rounds to 2 decimals to avoid floating point issues
function fmtPrice(val) {
    if (val == null || isNaN(val)) return '-';
    return '₹' + Number(val).toFixed(2);
}
function fmtPct(val) {
    if (val == null || isNaN(val)) return '-';
    return Number(val).toFixed(2) + '%';
}
function fmtChg(val) {
    if (val == null || isNaN(val)) return '-';
    return (val >= 0 ? '+' : '') + Number(val).toFixed(2);
}

// Symbol normalization - users can type RELIANCE, reliance, or RELIANCE.NS
// Backend strips .NS before calling Upstox, so we normalize internally
// Symbol alias map for renamed companies (e.g., ZOMATO → ETERNAL.NS)
const SYMBOL_ALIAS_MAP = {
    'ZOMATO': 'ETERNAL.NS',
    'ZOMATO.NS': 'ETERNAL.NS',
};
function normalizeSymbol(sym) {
    const s = (sym || '').trim().toUpperCase();
    if (!s) return s;
    // Check alias map first
    if (SYMBOL_ALIAS_MAP[s]) return SYMBOL_ALIAS_MAP[s];
    if (s.includes('.') || s.startsWith('^')) return s;
    return s + '.NS';
}
function displaySymbol(sym) {
    return (sym || '').replace('.NS', '').replace('.BO', '');
}

// API Helper - sends API key from localStorage on every request
async function api(url, options = {}) {
    const apiKey = localStorage.getItem('app_api_key') || '';
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
    };
    if (apiKey) {
        headers['X-API-Key'] = apiKey;
    }
    try {
        const res = await fetch(url, {
            headers,
            ...options
        });
        // Handle authentication required
        if (res.status === 401) {
            const data = await res.json().catch(() => ({}));
            showAuthRequired(data.detail || 'Authentication required');
            return { error: 'auth_required', status: 401, detail: data.detail };
        }
        return await res.json();
    } catch (err) {
        console.error('API Error:', err);
        return { error: err.message };
    }
}

// Show/Hide Loading
function showLoading() {
    document.getElementById('loading').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading').classList.add('hidden');
}

// Show authentication required toast
function showAuthRequired(message) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast toast-error';
    toast.innerHTML = `
        <strong>🔐 Authentication Required</strong><br>
        ${message}<br>
        <button class="btn-sm" onclick="openAuthModal()" style="margin-top:8px;">Enter API Key</button>
    `;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 8000);
}

// Open the API key settings modal
function openAuthModal() {
    const modal = document.getElementById('authModal');
    if (modal) {
        modal.style.display = 'flex';
        document.getElementById('authApiKey').value = localStorage.getItem('app_api_key') || '';
    }
}

// Close the API key settings modal
function closeAuthModal() {
    const modal = document.getElementById('authModal');
    if (modal) modal.style.display = 'none';
}

// Save the API key
function saveAuthApiKey() {
    const key = document.getElementById('authApiKey').value.trim();
    if (!key) {
        showAuthRequired('API key cannot be empty');
        return;
    }
    localStorage.setItem('app_api_key', key);
    closeAuthModal();
    // Show confirmation toast
    const container = document.getElementById('toastContainer');
    if (container) {
        const toast = document.createElement('div');
        toast.className = 'toast toast-success';
        toast.textContent = 'API key saved. Protected endpoints will now work.';
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }
}

// Check auth status on load and show setup prompt if needed
async function checkAuthStatus() {
    const indicator = document.getElementById('authIndicator');
    try {
        const res = await fetch('/api/auth/status');
        const data = await res.json();
        if (indicator) {
            if (data.configured) {
                indicator.textContent = '🔐 Key Configured';
                indicator.className = 'auth-indicator has-key';
            } else {
                indicator.textContent = '🔑 Setup Required';
                indicator.className = 'auth-indicator no-key';
                indicator.onclick = openAuthModal;
            }
        }
        if (!data.configured) {
            return;
        }
        // Key is configured server-side; if client has no key, show prompt
        if (!localStorage.getItem('app_api_key')) {
            const container = document.getElementById('toastContainer');
            if (container) {
                const toast = document.createElement('div');
                toast.className = 'toast toast-info';
                toast.innerHTML = `
                    <strong>🔐 API Key Required</strong><br>
                    Some protected endpoints need an API key.<br>
                    <button class="btn-sm" onclick="openAuthModal()" style="margin-top:8px;">Enter Key</button>
                `;
                container.appendChild(toast);
                setTimeout(() => toast.remove(), 8000);
            }
        } else if (indicator) {
            indicator.textContent = '🔐 Key Set';
            indicator.className = 'auth-indicator has-key';
            indicator.onclick = openAuthModal;
        }
    } catch (e) {
        if (indicator) {
            indicator.textContent = '🔐 Auth';
            indicator.className = 'auth-indicator no-key';
            indicator.onclick = openAuthModal;
        }
        // Ignore - auth endpoint may not exist yet
    }
}

// Tab Navigation
function showTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

    const targetTab = document.getElementById(tabName) || (tabName === 'sentinel' ? document.getElementById('sentinel-tab') : null) || (tabName === 'sentinel-tab' ? document.getElementById('sentinel') : null);
    if (targetTab) {
        targetTab.classList.add('active');
    }
    const navItem = document.querySelector(`.nav-item[data-tab="${tabName}"]`) || (tabName === 'sentinel-tab' ? document.querySelector(`.nav-item[data-tab="sentinel"]`) : null);
    if (navItem) {
        navItem.classList.add('active');
    }

    localStorage.setItem('lastTab', tabName);

    // Load data for specific tabs
    switch(tabName) {
        case 'dashboard': loadChart(); loadDashboardGainersLosers(); break;
        case 'market': loadMarket(); break;
        case 'signals': loadSignals(); break;
        case 'sector': loadSectors(); break;
        case 'news': loadNews(); break;
        case 'ai': loadAiTab(); break;
        case 'sentinel':
        case 'sentinel-tab': loadSentinelFeed(); loadSentinelDigests(); break;
        case 'heatmap': loadHeatmap(); break;
        case 'global': loadGlobalMarkets(); break;
        case 'ipo': loadIPOs(); loadMarketStatus(); break;
        case 'calculators': break;
        case 'features': loadFeaturesTab(); break;
        case 'gold': loadGoldPrices(); break;
        case 'mutualfunds': loadMutualFunds(); break;
        case 'currency': loadQuickRates(); break;
        case 'results': loadUpcomingResults(); break;
        case 'invest': loadSuperinvestors(); break;
        case 'portfolio': loadPortfolio(); loadPortfolioAnalytics(); loadBenchmark(); break;
        case 'watchlist': loadWatchlist(); break;
        case 'analysis': loadAlerts(); break;
        case 'traderdesk': initTraderDesk(); break;
    }
}

// Chart Functions
function initChart() {
    const container = document.getElementById('chartContainer');
    if (!container) {
        // The legacy dashboard chart was replaced by the pro chart
        // (#chartContainerChart). Initialise that one instead so the chart tab
        // and the topbar Refresh button keep working.
        if (typeof initChartChart === 'function' && typeof LightweightCharts !== 'undefined' && !chartChart) {
            initChartChart();
        }
        return;
    }

    chart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 400,
        layout: {
            background: { color: getChartBg() },
            textColor: '#8888a0'
        },
        grid: {
            vertLines: { color: 'rgba(255,255,255,0.04)' },
            horzLines: { color: 'rgba(255,255,255,0.04)' }
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal
        },
        rightPriceScale: {
            borderColor: 'rgba(255,255,255,0.06)'
        },
        timeScale: {
            borderColor: 'rgba(255,255,255,0.06)',
            timeVisible: true
        }
    });

    candleSeries = chart.addCandlestickSeries({
        upColor: '#10b981',
        downColor: '#ef4444',
        borderDownColor: '#ef4444',
        borderUpColor: '#10b981',
        wickDownColor: '#ef4444',
        wickUpColor: '#10b981',
        lastValueVisible: false,
        priceLineVisible: false
    });

    volumeSeries = chart.addHistogramSeries({
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume',
        lastValueVisible: false,
        priceLineVisible: false
    });

    chart.priceScale('volume').applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 }
    });

    // EMA ribbon series (9, 21, 50, 200)
    const emaConfigs = [
        { key: 'ema9', length: 9, color: '#38bdf8', width: 1 },
        { key: 'ema21', length: 21, color: '#3b82f6', width: 2 },
        { key: 'ema50', length: 50, color: '#f59e0b', width: 2 },
        { key: 'ema200', length: 200, color: '#a855f7', width: 2 }
    ];
    emaConfigs.forEach(({ key, color, width }) => {
        emaSeries[key] = chart.addLineSeries({
            color: color,
            lineWidth: width,
            title: '',
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false
        });
    });

    // VWAP series with bands
    const vwapConfigs = [
        { key: 'vwap', color: '#eab308', width: 2, style: 0 },
        { key: 'upper1', color: 'rgba(234,179,8,0.45)', width: 1, style: 1 },
        { key: 'lower1', color: 'rgba(234,179,8,0.45)', width: 1, style: 1 },
        { key: 'upper2', color: 'rgba(239,68,68,0.35)', width: 1, style: 2 },
        { key: 'lower2', color: 'rgba(16,185,129,0.35)', width: 1, style: 2 }
    ];
    vwapConfigs.forEach(({ key, color, width, style }) => {
        vwapSeries[key] = chart.addLineSeries({
            color: color,
            lineWidth: width,
            lineStyle: style,
            title: '',
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false
        });
    });

    new ResizeObserver(() => {
        chart.applyOptions({ width: container.clientWidth });
    }).observe(container);
}

async function loadChart() {
    // Legacy chart container is gone; the Live Chart tab uses loadChartChart().
    if (!document.getElementById('chartContainer')) {
        if (typeof loadChartChart === 'function') {
            return loadChartChart();
        }
        return;
    }
    showLoading();
    try {
        const data = await api(`/api/stocks/${currentSymbol}/history?period=${currentTimeframe}`);
        
        if (data.error) {
            console.error(data.error);
            return;
        }

        document.getElementById('chartStockName').textContent = currentSymbol.replace('.NS', '');
        
        // Get current price from info
        const info = await api(`/api/stocks/${currentSymbol}`);
        const price = info.currentPrice || info.price || (data.history && data.history.length > 0 ? data.history[data.history.length - 1].close : '-');
        document.getElementById('chartPrice').textContent = fmtPrice(price);
        document.getElementById('livePrice').textContent = fmtPrice(price);
        
        if (info.indicators) {
            document.getElementById('chartRsi').textContent = info.indicators.rsi?.toFixed(2) || '-';
            document.getElementById('chartMacd').textContent = info.indicators.macd?.toFixed(2) || '-';
            document.getElementById('chartSma20').textContent = fmtPrice(info.indicators.sma20);
            document.getElementById('chartSma50').textContent = fmtPrice(info.indicators.sma50);
            document.getElementById('chartAtr').textContent = info.indicators.atr?.toFixed(2) || '-';
        }

        const isIntraday = ['5m', '15m', '30m', '1h'].includes(currentTimeframe);

        // Show/hide strategy badges for intraday
        const stratBadge = document.getElementById('chartStrategyBadges');
        const barTimer = document.getElementById('chartBarTimer');
        if (stratBadge) stratBadge.style.display = isIntraday ? 'flex' : 'none';
        if (barTimer) {
            barTimer.parentElement.style.display = isIntraday ? 'flex' : 'none';
        }

        if (data.data && data.data.length > 0) {
            const candles = data.data.map(d => ({
                time: d.date,
                open: d.open,
                high: d.high,
                low: d.low,
                close: d.close,
                volume: d.volume || 0
            }));

            const volumes = data.data.map(d => ({
                time: d.date,
                value: d.volume || 0,
                color: d.close >= d.open ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'
            }));

            candleSeries.setData(candles);
            volumeSeries.setData(volumes);
            chart.timeScale().fitContent();

            // --- Indian Day Trader chart enhancements ---

            // 1. ORB Levels (opening range breakout) for intraday
            if (isIntraday) {
                orbLevels = computeOrbLevels(candles);
                drawStrategyLines(orbLevels);
                updateOrbBadge(orbLevels);
                startBarTimer(currentTimeframe);
            } else {
                clearStrategyLines();
                stopBarTimer();
            }

            // 2. EMA ribbon
            if (activeIndicators.ema) {
                updateEmaSeries(candles);
            }

            // 3. VWAP with bands (intraday only)
            if (activeIndicators.vwap && isIntraday) {
                updateVwapSeries(candles);
            }

            // 4. Camarilla pivots (daily+)
            if (activeIndicators.pivots && !isIntraday) {
                updatePivotLines(candles);
            }

            // 5. Candlestick pattern markers
            if (activeIndicators.patterns) {
                updatePatternMarkers(candles);
            }

            // 6. Oscillator sub-pane (RSI/MACD) - client-side computed
            if (activeIndicators.oscillator) {
                initOscillatorChart();
                renderOscillatorData(candles);
            }
        }
    } catch (err) {
        console.error('Chart error:', err);
    }
    hideLoading();
}

function changeTimeframe(tf, btn) {
    currentTimeframe = tf;
    document.querySelectorAll('.timeframe-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    loadChart();
}

// ============================================================================
// DEDICATED LIVE CHART VIEW (TradingView-style)
// ============================================================================

// Dedicated chart variables
let chartChart = null;
let candleSeriesChart = null;
let volumeSeriesChart = null;
let chartLoadingLock = false;
let emaSeriesChart = {};
let vwapSeriesChart = {};
let oscChartChart = null;
let oscSeriesChart = {};
let pivotLinesChart = [];
let lineBreakoutChart = null;
let lineTargetChart = null;
let lineStopLossChart = null;
let orbLevelsChart = null;
let barTimerIntervalChart = null;
let drawingToolChart = null; // 'horizontal', 'trend', 'pricealert', or null
let drawingStartPointChart = null;
let drawingLinesChart = [];
let chartWsSymbols = new Set();

// Initialize dedicated chart
function initChartChart() {
    const container = document.getElementById('chartContainerChart');
    if (!container) return;

    // Use the new unified ChartController
    window.chartController = new ChartController('chartContainerChart');
    window.chartController.init();

    // Expose chart and series for backward compatibility
    chartChart = window.chartController.chart;
    candleSeriesChart = window.chartController.candleSeries;
    volumeSeriesChart = window.chartController.volumeSeries;
    emaSeriesChart = window.chartController.emaSeries;
    vwapSeriesChart = window.chartController.vwapSeries;

    // Initialize drawing event handlers
    initChartDrawingEvents();
}

// Overlay for loading failures. Kept separate from the chart canvas so a
// failed load does not detach the chart and blank it permanently.
function showChartOverlayChart(html) {
    const container = document.getElementById('chartContainerChart');
    if (!container) return;
    let overlay = container.querySelector('.chart-state-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'chart-state-overlay';
        overlay.style.cssText = 'position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; z-index:20; padding:16px; background:rgba(10,10,15,0.9); text-align:center;';
        container.appendChild(overlay);
    }
    overlay.innerHTML = html;
}

function clearChartOverlayChart() {
    const container = document.getElementById('chartContainerChart');
    const overlay = container && container.querySelector('.chart-state-overlay');
    if (overlay) overlay.remove();
}

// Load chart data for dedicated view
// Timeframe → period/interval mapping
// period = how much historical data to fetch, interval = candle granularity
const TIMEFRAME_CONFIG = {
    '1d':   { period: '1y', interval: '1d' },   // 1 year of daily candles
    '5d':   { period: '1y', interval: '1d' },   // 1 year of daily candles
    '1mo':  { period: '2y', interval: '1mo' },  // 2 years of monthly candles
    '3mo':  { period: '2y', interval: '1mo' },  // 2 years of monthly candles
    '6mo':  { period: '2y', interval: '1mo' },  // 2 years of monthly candles
    '1y':   { period: '5y', interval: '1mo' },  // 5 years of monthly candles
    '5m':   { period: '1d', interval: '5m' },   // 1 day of 5-min candles
    '15m':  { period: '1d', interval: '15m' },  // 1 day of 15-min candles
    '30m':  { period: '1d', interval: '30m' },  // 1 day of 30-min candles
    '1h':   { period: '1d', interval: '1h' },   // 1 day of 1-hour candles
};

async function loadChartChart() {
    console.log('[loadChartChart] START', { chartLoadingLock });
    // Prevent concurrent chart loads
    if (chartLoadingLock) {
        console.log('[loadChartChart] BLOCKED - lock held');
        return;
    }
    chartLoadingLock = true;
    console.log('[loadChartChart] LOCK acquired');

    const loadBtn = document.querySelector('button[onclick="loadChartSymbolFromInput()"]');
    if (loadBtn) {
        loadBtn.disabled = true;
        loadBtn.textContent = 'Loading…';
    }

    const rawSymbol = document.getElementById('chartSymbolInput')?.value?.trim()?.toUpperCase();
    console.log('[loadChartChart] rawSymbol:', rawSymbol);
    if (!rawSymbol) {
        console.log('[loadChartChart] EMPTY symbol, releasing lock');
        chartLoadingLock = false;
        return;
    }

    const symbol = normalizeSymbol(rawSymbol);
    const dispSym = displaySymbol(symbol);
    const symInput = document.getElementById('chartSymbolInput');
    if (symInput) symInput.value = symbol;

    // Keep the global/topbar selection in sync with the loaded chart
    currentSymbol = symbol;
    localStorage.setItem('lastStock', symbol);
    const topbarNameEl = document.getElementById('currentStockName');
    if (topbarNameEl) topbarNameEl.textContent = dispSym;

    const stockNameEl = document.getElementById('chartStockName');
    if (stockNameEl) stockNameEl.textContent = dispSym;

    const badgeEl = document.getElementById('chartSymbolBadge');
    if (badgeEl) badgeEl.textContent = dispSym;
    setChartWsStatus('connecting');

    // Clear the previous symbol's LTP/price line while the new data loads
    const chartPriceEl = document.getElementById('chartPrice');
    if (chartPriceEl) chartPriceEl.textContent = 'Loading...';
    if (chartLivePriceLineChart) {
        try { candleSeriesChart.removePriceLine(chartLivePriceLineChart); } catch(e) {}
        chartLivePriceLineChart = null;
    }

    // Show loading state
    const loadingEl = document.getElementById('chartLoadingChart');
    const containerEl = document.getElementById('chartContainerChart');
    console.log('[loadChartChart] loadingEl:', loadingEl, 'containerEl:', containerEl);
    if (loadingEl) loadingEl.style.display = 'flex';
    if (containerEl) containerEl.style.display = 'block';

    const tf = document.querySelector('#chart .tf-btn.active')?.dataset.tf || '1d';
    const tfConfig = TIMEFRAME_CONFIG[tf] || TIMEFRAME_CONFIG['1d'];
    console.log('[loadChartChart] timeframe:', tf, 'config:', tfConfig);

    try {
        const url = `/api/stocks/${symbol}/history?period=${tfConfig.period}&interval=${tfConfig.interval}`;
        console.log('[loadChartChart] fetching:', url);
        const data = await api(url);
        console.log('[loadChartChart] response:', data);

        if (data.error || !data.data || data.data.length === 0) {
            if (loadingEl) loadingEl.style.display = 'none';
            const msg = data.error ? data.error : 'No data available for ' + symbol;
            let suggestion = '';
            // If symbol not found, suggest search
            if (data.error && data.error.includes('not found')) {
                suggestion = '<p class="placeholder" style="font-size:11px; margin-top:4px;">Try searching for the stock in the search box or try a different symbol.</p>';
            }
            showChartOverlayChart('<p class="placeholder">' + msg + '</p>' + suggestion);
            return;
        }

        const candles = data.data.map(d => ({
            time: d.date,
            open: d.open,
            high: d.high,
            low: d.low,
            close: d.close,
            volume: d.volume || 0
        }));

        // Fetch stock info and price using clean un-namespaced ticker if needed
        try {
            const rawTick = displaySymbol(symbol);
            const info = await api(`/api/stocks/${rawTick}`);
            const price = info.currentPrice || info.price || (candles.length > 0 ? candles[candles.length - 1].close : '-');
            const priceEl = document.getElementById('chartPrice');
            if (priceEl) priceEl.textContent = fmtPrice(price);
        } catch(e) {
            if (candles.length > 0) {
                const priceEl = document.getElementById('chartPrice');
                if (priceEl) priceEl.textContent = fmtPrice(candles[candles.length - 1].close);
            }
        }

        const volumes = data.data.map(d => ({
            time: d.date,
            value: d.volume || 0,
            color: d.close >= d.open ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'
        }));

        // Use the new ChartController's setData method which also updates crosshair legend
        if (window.chartController) {
            window.chartController.setData(candles, volumes);
        } else {
            candleSeriesChart.setData(candles);
            volumeSeriesChart.setData(volumes);
            chartChart.timeScale().fitContent();
        }
        clearChartOverlayChart();

        // Draw ORB levels for intraday
        const isIntraday = ['5m', '15m', '30m', '1h'].includes(tf);
        if (isIntraday) {
            orbLevelsChart = computeOrbLevels(candles);
            drawStrategyLinesChart(orbLevelsChart);
            updateOrbBadgeChart(orbLevelsChart);
            startBarTimerChart(tf);
        } else {
            clearStrategyLinesChart();
            stopBarTimerChart();
        }

        // Indicators
        updateEmaSeriesChart(candles);
        if (isIntraday) updateVwapSeriesChart(candles);
        else updatePivotLinesChart(candles);
        updatePatternMarkersChart(candles);

        // Subscribe to WebSocket for live updates
        subscribeToChartSymbol(symbol);

        // Hide loading state
        if (loadingEl) loadingEl.style.display = 'none';

    } catch (err) {
        console.error('[loadChartChart] ERROR:', err);
        if (loadingEl) loadingEl.style.display = 'none';
        showChartOverlayChart('<p class="placeholder">Error loading chart: ' + err.message + '</p>');
    } finally {
        console.log('[loadChartChart] FINALLY - releasing lock');
        chartLoadingLock = false;
        const loadBtn = document.querySelector('button[onclick="loadChartSymbolFromInput()"]');
        if (loadBtn) {
            loadBtn.disabled = false;
            loadBtn.textContent = 'Load';
        }
    }
}

// Live price line for the dedicated chart (handler lives below)
let chartLivePriceLineChart = null;

function setChartTimeframe(tf, btn) {
    document.querySelectorAll('#chart .tf-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    // Save current visible range before loading new timeframe
    if (window.chartController) {
        window.chartController.saveVisibleRange();
    }

    loadChartChart();

    // Restore visible range after loading (with a small delay to let data load)
    setTimeout(() => {
        if (window.chartController) {
            window.chartController.restoreVisibleRange();
        }
    }, 100);
}

function drawStrategyLinesChart(levels) {
    if (!candleSeriesChart) return;
    clearStrategyLinesChart();

    if (!levels) return;

    lineBreakoutChart = candleSeriesChart.createPriceLine({
        price: levels.breakout,
        color: '#3b82f6',
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: true,
        title: 'ORB HIGH'
    });

    lineTargetChart = candleSeriesChart.createPriceLine({
        price: levels.target,
        color: '#10b981',
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: false,
        title: 'TARGET (1.5R)'
    });

    lineStopLossChart = candleSeriesChart.createPriceLine({
        price: levels.stopLoss,
        color: '#ef4444',
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: true,
        title: 'STOP LOSS'
    });
}

function clearStrategyLinesChart() {
    if (lineBreakoutChart) { try { candleSeriesChart.removePriceLine(lineBreakoutChart); } catch(e) {} lineBreakoutChart = null; }
    if (lineTargetChart) { try { candleSeriesChart.removePriceLine(lineTargetChart); } catch(e) {} lineTargetChart = null; }
    if (lineStopLossChart) { try { candleSeriesChart.removePriceLine(lineStopLossChart); } catch(e) {} lineStopLossChart = null; }
}

function updateOrbBadgeChart(levels) {
    if (!levels) return;
    document.getElementById('stratBreakoutValChart').textContent = '₹' + levels.breakout.toFixed(2);
    document.getElementById('stratStopValChart').textContent = '₹' + levels.stopLoss.toFixed(2);
    document.getElementById('stratTargetValChart').textContent = '₹' + levels.target.toFixed(2);
}

function startBarTimerChart(timeframe) {
    stopBarTimerChart();
    const stepSec = { '1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600 }[timeframe] || 300;
    const el = document.getElementById('chartBarTimerChart');
    if (!el) return;

    function update() {
        const now = new Date();
        const istTime = new Date(now.getTime() + (now.getTimezoneOffset() * 60000) + (5.5 * 3600000));
        const totalSecToday = istTime.getHours() * 3600 + istTime.getMinutes() * 60 + istTime.getSeconds();
        const sessionOpen = 9 * 3600 + 15 * 60;
        let elapsed = totalSecToday - sessionOpen;
        if (elapsed < 0) elapsed = 0;
        const secsIntoCandle = elapsed % stepSec;
        const secsRemaining = stepSec - secsIntoCandle;
        const remM = Math.floor(secsRemaining / 60);
        const remS = secsRemaining % 60;
        el.textContent = String(remM).padStart(2, '0') + ':' + String(remS).padStart(2, '0');
    }
    update();
    barTimerIntervalChart = setInterval(update, 1000);
}

function stopBarTimerChart() {
    if (barTimerIntervalChart) {
        clearInterval(barTimerIntervalChart);
        barTimerIntervalChart = null;
    }
    const el = document.getElementById('chartBarTimerChart');
    if (el) el.textContent = '--:--';
}

function updateEmaSeriesChart(candles) {
    if (!window.Indicators || !window.Indicators.computeEma) return;
    const emaConfigsChart = [
        { key: 'ema9', length: 9 },
        { key: 'ema21', length: 21 },
        { key: 'ema50', length: 50 },
        { key: 'ema200', length: 200 }
    ];
    emaConfigsChart.forEach(({ key, length }) => {
        const emaData = window.Indicators.computeEma(candles, length);
        if (emaSeriesChart[key]) {
            emaSeriesChart[key].setData(emaData || []);
        }
    });
}

function updateVwapSeriesChart(candles) {
    if (!window.Indicators || !window.Indicators.computeVwap) return;
    const result = window.Indicators.computeVwap(candles);
    if (!result) return;
    const keys = ['vwap', 'upper1', 'lower1', 'upper2', 'lower2'];
    keys.forEach(k => {
        if (vwapSeriesChart[k]) vwapSeriesChart[k].setData(result[k] || []);
    });
}

function updatePivotLinesChart(candles) {
    if (!candleSeriesChart) return;
    pivotLinesChart.forEach(l => { try { candleSeriesChart.removePriceLine(l); } catch(e) {} });
    pivotLinesChart = [];

    if (!window.Indicators || !window.Indicators.computePivots) return;

    const toIstDateKey = (isoString) => {
        const d = new Date(isoString + 'T00:00:00+05:30');
        return d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0') + '-' + String(d.getUTCDate()).padStart(2, '0');
    };
    const datesMap = new Map();
    candles.forEach(b => {
        const k = toIstDateKey(b.time);
        if (!datesMap.has(k)) datesMap.set(k, []);
        datesMap.get(k).push(b);
    });
    const sortedDates = Array.from(datesMap.keys()).sort();
    if (sortedDates.length < 2) return;
    const prevKey = sortedDates[sortedDates.length - 2];
    const prevBars = datesMap.get(prevKey);
    if (!prevBars || !prevBars.length) return;

    let prevHigh = -Infinity, prevLow = Infinity;
    prevBars.forEach(b => { if (b.high > prevHigh) prevHigh = b.high; if (b.low < prevLow) prevLow = b.low; });
    const prevClose = prevBars[prevBars.length - 1].close;

    const pivots = window.Indicators.computePivots({ high: prevHigh, low: prevLow, close: prevClose });
    if (!pivots) return;

    const levels = [
        { price: pivots.r4, color: '#f43f5e', title: 'CAM R4' },
        { price: pivots.r3, color: '#fb923c', title: 'CAM R3' },
        { price: pivots.s3, color: '#34d399', title: 'CAM S3' },
        { price: pivots.s4, color: '#38bdf8', title: 'CAM S4' }
    ];
    levels.forEach(({ price, color, title }) => {
        try {
            const line = candleSeriesChart.createPriceLine({
                price: price,
                color: color,
                lineWidth: 1,
                lineStyle: 2,
                axisLabelVisible: false,
                title: title + ' ₹' + price.toFixed(2)
            });
            pivotLinesChart.push(line);
        } catch(e) {}
    });
}

function updatePatternMarkersChart(candles) {
    // Keep chart clean and professional without marker clutter
    try { candleSeriesChart.setMarkers([]); } catch(e) {}
}

// --- WebSocket for dedicated chart ---
function subscribeToChartSymbol(symbol) {
    const normalized = normalizeSymbol(symbol);
    if (!normalized) return;

    // The chart displays one symbol at a time, so replace the previous
    // subscription instead of accumulating stale tickers.
    chartWsSymbols.clear();
    chartWsSymbols.add(normalized);

    if (sendWsSubscription()) {
        setChartWsStatus('connecting');
    } else if (!ws || ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING) {
        connectWebSocket();
        setChartWsStatus('connecting');
    }
    // If the socket is still CONNECTING, onopen sends the current symbol list.
}

function setChartWsStatus(status) {
    const statusEl = document.getElementById('chartWsStatus');
    const dotEl = document.getElementById('chartWsDot');
    const labels = {
        live: 'Live',
        connecting: 'Connecting...',
        offline: 'Offline',
        error: 'Feed Error'
    };
    if (statusEl) statusEl.textContent = labels[status] || 'Offline';
    if (dotEl) dotEl.className = 'ws-dot' + (status === 'live' ? ' live' : '');
}

// Update chart with live price from WebSocket
function updateChartLivePrice(symbol, price, change, changePercent) {
    if (!candleSeriesChart) return;

    const symbolInput = document.getElementById('chartSymbolInput');
    if (!symbolInput) return; // Chart tab not initialized yet

    const activeSymbol = normalizeSymbol(symbolInput.value.trim());
    if (normalizeSymbol(symbol) !== activeSymbol) return;

    const ltp = Number(price);
    if (!Number.isFinite(ltp)) return;

    const changeNum = Number(change) || 0;
    const changePctNum = Number(changePercent) || 0;

    setChartWsStatus('live');

    // Update the LTP ticker in the chart header
    const priceEl = document.getElementById('chartPrice');
    if (priceEl) {
        const oldPrice = parseFloat((priceEl.textContent || '').replace(/[₹,%]/g, '').trim());
        priceEl.textContent = fmtPrice(ltp);
        if (Number.isFinite(oldPrice) && oldPrice > 0 && ltp !== oldPrice) {
            flashElement(priceEl, ltp > oldPrice ? 'flash-green' : 'flash-red');
        }
    }

    // Update badge with price - preserve badge classes
    const badge = document.getElementById('chartSymbolBadge');
    if (badge) {
        badge.textContent = displaySymbol(symbol) + ' ₹' + ltp.toFixed(2);
        badge.className = 'badge symbol-badge ' + (changeNum >= 0 ? 'positive' : 'negative');
        badge.setAttribute('aria-label', 'Current symbol: ' + displaySymbol(symbol) + ' at ₹' + ltp.toFixed(2));
    }

    // Update or create live price line
    if (chartLivePriceLineChart) {
        try { candleSeriesChart.removePriceLine(chartLivePriceLineChart); } catch(e) {}
        chartLivePriceLineChart = null;
    }

    try {
        chartLivePriceLineChart = candleSeriesChart.createPriceLine({
            price: ltp,
            color: changeNum >= 0 ? '#10b981' : '#ef4444',
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: true,
            title: 'Live: ₹' + ltp.toFixed(2) + ' (' + (changeNum >= 0 ? '+' : '') + changeNum.toFixed(2) + ', ' + (changePctNum >= 0 ? '+' : '') + changePctNum.toFixed(2) + '%)'
        });
    } catch(e) {}
}

// --- Drawing Tools ---
function activateDrawingTool(tool) {
    drawingToolChart = tool;
    document.querySelectorAll('#chart .tool-btn').forEach(b => b.classList.remove('active-tool'));
    if (tool) {
        event.target.classList.add('active-tool');
    }
    document.getElementById('drawingToolIndicator').textContent = tool ? tool.charAt(0).toUpperCase() + tool.slice(1) : 'None';
    drawingStartPointChart = null;
}

function clearDrawingTools() {
    drawingLinesChart.forEach(l => {
        try { candleSeriesChart.removePriceLine(l); } catch(e) {}
    });
    drawingLinesChart = [];
    drawingToolChart = null;
    drawingStartPointChart = null;
    document.getElementById('drawingToolIndicator').textContent = 'None';
    document.querySelectorAll('#chart .tool-btn').forEach(b => b.classList.remove('active-tool'));
}

// --- Drawing Interaction Handlers ---
function initChartDrawingEvents() {
    const container = document.getElementById('chartContainerChart');
    if (!container || container.dataset.drawingInit) return;
    container.dataset.drawingInit = 'true';

    let trendStartPoint = null; // { time, price } for trend line drawing

    container.addEventListener('mousedown', (e) => {
        if (!candleSeriesChart || !chartChart) return;
        if (!drawingToolChart) return;
        if (e.target.closest('.tool-btn')) return;

        const timeScale = chartChart.timeScale();
        const priceScale = candleSeriesChart.priceScale();

        const logicalTime = timeScale.coordinateToLogic(e.offsetX);
        const priceValue = priceScale.coordinateToPrice(e.offsetY);

        if (priceValue === null || priceValue === undefined) return;

        const price = Number(priceValue.toFixed(2));

        if (drawingToolChart === 'horizontal' || drawingToolChart === 'pricealert') {
            // Horizontal line - single click
            const color = drawingToolChart === 'pricealert' ? '#f59e0b' : '#3b82f6';
            const line = candleSeriesChart.createPriceLine({
                price: price,
                color: color,
                lineWidth: 2,
                lineStyle: 2,
                axisLabelVisible: true,
                title: drawingToolChart === 'pricealert' ? 'Alert: ₹' + price.toFixed(2) : 'H-Line: ₹' + price.toFixed(2)
            });
            drawingLinesChart.push(line);
            showToast(drawingToolChart === 'pricealert' ? 'Price alert line added' : 'Horizontal line added', 'success');
            activateDrawingTool(null);
        } else if (drawingToolChart === 'trend') {
            // Trend line - two clicks using horizontal lines at each point
            // (LightweightCharts v4 does not have a native trend line API on series)
            if (!trendStartPoint) {
                trendStartPoint = { time: logicalTime, price: price };
                showToast('Click second point for trend line', 'info');
            } else {
                // Draw a horizontal line at the second point (trend line approximation)
                const line = candleSeriesChart.createPriceLine({
                    price: price,
                    color: '#3b82f6',
                    lineWidth: 2,
                    lineStyle: 0,
                    axisLabelVisible: false,
                    title: 'Trend line end: ₹' + price.toFixed(2)
                });
                drawingLinesChart.push(line);
                trendStartPoint = null;
                showToast('Trend line point added', 'success');
                activateDrawingTool(null);
            }
        }
    }, { passive: false });
}

// --- Fullscreen ---
function toggleChartFullscreen() {
    const container = document.getElementById('chart');
    if (!document.fullscreenElement) {
        container.requestFullscreen().catch(() => {});
    } else {
        document.exitFullscreen();
    }
}



// --- ORB Levels (Opening Range Breakout) ---
function computeOrbLevels(candles) {
    if (!candles || candles.length === 0) return null;

    // Candle times are 'YYYY-MM-DD' for daily bars and 'YYYY-MM-DD HH:mm'
    // (IST) for intraday bars. Parse both without corrupting the timestamp.
    const parseIst = (t) => {
        if (typeof t === 'number') return new Date(t * 1000);
        const s = String(t).trim();
        return new Date(s.length > 10 ? s.replace(' ', 'T') + '+05:30' : s + 'T00:00:00+05:30');
    };
    const toIstDateKey = (t) => {
        const d = parseIst(t);
        if (isNaN(d.getTime())) return '';
        const y = d.getUTCFullYear();
        const m = String(d.getUTCMonth() + 1).padStart(2, '0');
        const day = String(d.getUTCDate()).padStart(2, '0');
        return `${y}-${m}-${day}`;
    };

    const latestDayKey = toIstDateKey(candles[candles.length - 1].time);
    const todayCandles = candles.filter(c => toIstDateKey(c.time) === latestDayKey);

    // ORB window: 09:15 to 09:30 IST
    const orbBars = todayCandles.filter(c => {
        const d = parseIst(c.time);
        if (isNaN(d.getTime())) return false;
        const totalMin = d.getUTCHours() * 60 + d.getUTCMinutes();
        return totalMin >= (3 * 60 + 45) && totalMin < (4 * 60);
    });

    if (orbBars.length === 0) return null;

    const minBars = currentTimeframe === '1m' ? 10 : 3;
    if (orbBars.length < minBars) return null;

    const orbHigh = Math.max(...orbBars.map(b => b.high));
    const orbLow = Math.min(...orbBars.map(b => b.low));
    const risk = orbHigh - orbLow;
    const target = orbHigh + (risk * 1.5);

    return {
        breakout: parseFloat(orbHigh.toFixed(2)),
        stopLoss: parseFloat(orbLow.toFixed(2)),
        target: parseFloat(target.toFixed(2))
    };
}

function drawStrategyLines(levels) {
    if (!candleSeries) return;

    clearStrategyLines();

    if (!levels) return;

    lineBreakout = candleSeries.createPriceLine({
        price: levels.breakout,
        color: '#3b82f6',
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: true,
        title: 'ORB HIGH'
    });

    lineTarget = candleSeries.createPriceLine({
        price: levels.target,
        color: '#10b981',
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: false,
        title: 'TARGET (1.5R)'
    });

    lineStopLoss = candleSeries.createPriceLine({
        price: levels.stopLoss,
        color: '#ef4444',
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: true,
        title: 'STOP LOSS'
    });
}

function clearStrategyLines() {
    if (lineBreakout) {
        try { candleSeries.removePriceLine(lineBreakout); } catch (e) {}
        lineBreakout = null;
    }
    if (lineTarget) {
        try { candleSeries.removePriceLine(lineTarget); } catch (e) {}
        lineTarget = null;
    }
    if (lineStopLoss) {
        try { candleSeries.removePriceLine(lineStopLoss); } catch (e) {}
        lineStopLoss = null;
    }
}

function updateOrbBadge(levels) {
    if (!levels) return;
    const elBreakout = document.getElementById('stratBreakoutVal');
    const elStop = document.getElementById('stratStopVal');
    const elTarget = document.getElementById('stratTargetVal');
    if (elBreakout) elBreakout.textContent = '₹' + levels.breakout.toFixed(2);
    if (elStop) elStop.textContent = '₹' + levels.stopLoss.toFixed(2);
    if (elTarget) elTarget.textContent = '₹' + levels.target.toFixed(2);
}

// --- Bar Close Timer (intraday) ---
function startBarTimer(timeframe) {
    stopBarTimer();
    const stepSec = { '1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600 }[timeframe] || 300;
    const el = document.getElementById('chartBarTimer');
    if (!el) return;

    function update() {
        const now = new Date();
        const istTime = new Date(now.getTime() + (now.getTimezoneOffset() * 60000) + (5.5 * 3600000));
        const totalSecToday = istTime.getHours() * 3600 + istTime.getMinutes() * 60 + istTime.getSeconds();
        const sessionOpen = 9 * 3600 + 15 * 60; // 09:15 IST
        let elapsed = totalSecToday - sessionOpen;
        if (elapsed < 0) elapsed = 0;
        const secsIntoCandle = elapsed % stepSec;
        const secsRemaining = stepSec - secsIntoCandle;
        const remM = Math.floor(secsRemaining / 60);
        const remS = secsRemaining % 60;
        el.textContent = String(remM).padStart(2, '0') + ':' + String(remS).padStart(2, '0');
    }
    update();
    barTimerInterval = setInterval(update, 1000);
}

function stopBarTimer() {
    if (barTimerInterval) {
        clearInterval(barTimerInterval);
        barTimerInterval = null;
    }
    const el = document.getElementById('chartBarTimer');
    if (el) el.textContent = '--:--';
}

// --- EMA Ribbon ---
function updateEmaSeries(candles) {
    if (!window.Indicators || !window.Indicators.computeEma) return;
    const emaConfigs = [
        { key: 'ema9', length: 9 },
        { key: 'ema21', length: 21 },
        { key: 'ema50', length: 50 },
        { key: 'ema200', length: 200 }
    ];
    emaConfigs.forEach(({ key, length }) => {
        const emaData = window.Indicators.computeEma(candles, length);
        if (emaSeries[key]) {
            emaSeries[key].setData(emaData || []);
        }
    });
}

// --- VWAP with bands ---
function updateVwapSeries(candles) {
    if (!window.Indicators || !window.Indicators.computeVwap) return;
    const result = window.Indicators.computeVwap(candles);
    if (!result) return;
    const keys = ['vwap', 'upper1', 'lower1', 'upper2', 'lower2'];
    keys.forEach(k => {
        if (vwapSeries[k]) vwapSeries[k].setData(result[k] || []);
    });
}

// --- Camarilla Pivots ---
function updatePivotLines(candles) {
    if (!candleSeries) return;
    // Clear existing
    pivotLines.forEach(l => {
        try { candleSeries.removePriceLine(l); } catch (e) {}
    });
    pivotLines = [];

    if (!window.Indicators || !window.Indicators.computePivots) return;

    // Group by date, find previous day
    const toIstDateKey = (isoString) => {
        const d = new Date(isoString + 'T00:00:00+05:30');
        return d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0') + '-' + String(d.getUTCDate()).padStart(2, '0');
    };
    const datesMap = new Map();
    candles.forEach(b => {
        const k = toIstDateKey(b.time);
        if (!datesMap.has(k)) datesMap.set(k, []);
        datesMap.get(k).push(b);
    });
    const sortedDates = Array.from(datesMap.keys()).sort();
    if (sortedDates.length < 2) return;
    const prevKey = sortedDates[sortedDates.length - 2];
    const prevBars = datesMap.get(prevKey);
    if (!prevBars || !prevBars.length) return;

    let prevHigh = -Infinity, prevLow = Infinity;
    prevBars.forEach(b => {
        if (b.high > prevHigh) prevHigh = b.high;
        if (b.low < prevLow) prevLow = b.low;
    });
    const prevClose = prevBars[prevBars.length - 1].close;

    const pivots = window.Indicators.computePivots({ high: prevHigh, low: prevLow, close: prevClose });
    if (!pivots) return;

    const levels = [
        { price: pivots.r4, color: '#f43f5e', title: 'CAM R4' },
        { price: pivots.r3, color: '#fb923c', title: 'CAM R3' },
        { price: pivots.s3, color: '#34d399', title: 'CAM S3' },
        { price: pivots.s4, color: '#38bdf8', title: 'CAM S4' }
    ];
    levels.forEach(({ price, color, title }) => {
        try {
            const line = candleSeries.createPriceLine({
                price: price,
                color: color,
                lineWidth: 1,
                lineStyle: 2,
                axisLabelVisible: false,
                title: title + ' ₹' + price.toFixed(2)
            });
            pivotLines.push(line);
        } catch (e) {}
    });
}

// --- Candlestick Pattern Markers ---
function updatePatternMarkers(candles) {
    if (!candleSeries || !window.Indicators || !window.Indicators.detectCandlestickPatterns) return;
    const markers = window.Indicators.detectCandlestickPatterns(candles);
    try {
        candleSeries.setMarkers(markers || []);
    } catch (e) {}
}

// --- Oscillator Sub-Chart (RSI / MACD) ---
function initOscillatorChart() {
    if (oscChart) return;
    const container = document.getElementById('oscillator-container');
    if (!container || typeof LightweightCharts === 'undefined') return;

    oscChart = LightweightCharts.createChart(container, {
        width: container.clientWidth || 800,
        height: 120,
        layout: { background: { color: '#0a0d14' }, textColor: '#94a3b8', fontSize: 10 },
        grid: { vertLines: { color: '#161c2d' }, horzLines: { color: '#161c2d' } },
        crosshair: { mode: 1, vertLine: { color: '#3b82f6', width: 1, style: 2 }, horzLine: { color: '#3b82f6', width: 1, style: 2 } },
        rightPriceScale: { borderColor: '#1e2638', scaleMargins: { top: 0.1, bottom: 0.1 } },
        timeScale: { borderColor: '#1e2638', timeVisible: true, secondsVisible: false }
    });

    oscSeries.rsi = oscChart.addLineSeries({ color: '#a855f7', lineWidth: 1, title: 'RSI' });
    oscSeries.macd = oscChart.addLineSeries({ color: '#3b82f6', lineWidth: 1, title: 'MACD' });
    oscSeries.signal = oscChart.addLineSeries({ color: '#f59e0b', lineWidth: 1, title: 'Signal' });
    oscSeries.hist = oscChart.addHistogramSeries({ color: '#10b981', priceFormat: { type: 'volume' }, priceScaleId: 'volume', lastValueVisible: false, priceLineVisible: false });
}

function renderOscillatorData(candles) {
    if (!window.Indicators) return;
    const rsiData = window.Indicators.computeRsi(candles, 14);
    const macdResult = window.Indicators.computeMacd(candles, 12, 26, 9);

    if (oscSeries.rsi) oscSeries.rsi.setData(rsiData || []);
    if (oscSeries.macd && macdResult) oscSeries.macd.setData(macdResult.macd || []);
    if (oscSeries.signal && macdResult) oscSeries.signal.setData(macdResult.signal || []);
    if (oscSeries.hist && macdResult) {
        const histData = (macdResult.histogram || []).map(h => ({ time: h.time, value: h.value, color: h.value >= 0 ? 'rgba(16,185,129,0.5)' : 'rgba(239,68,68,0.5)' }));
        oscSeries.hist.setData(histData);
    }
}

// Dashboard Gainers/Losers
async function loadDashboardGainersLosers() {
    try {
        const gainersData = await api('/api/market/top-gainers');
        const losersData = await api('/api/market/top-losers');
        
        const gainersContainer = document.getElementById('topGainers');
        const losersContainer = document.getElementById('topLosers');
        
        if (!gainersContainer || !losersContainer) return;
        
        if (gainersData.gainers) {
            gainersContainer.innerHTML = `
                <table>
                    <thead><tr><th>Stock</th><th>Price</th><th>Change</th></tr></thead>
                    <tbody>
                        ${gainersData.gainers.map(s => `
                            <tr data-live-symbol="${s.symbol}" onclick="selectStock('${s.symbol}')" style="cursor:pointer">
                                <td><strong>${s.name}</strong></td>
                                <td data-live-price>${fmtPrice(s.price)}</td>
                                <td class="positive" data-live-change-pct>+${fmtPct(s.changePercent)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }
        
        if (losersData.losers) {
            losersContainer.innerHTML = `
                <table>
                    <thead><tr><th>Stock</th><th>Price</th><th>Change</th></tr></thead>
                    <tbody>
                        ${losersData.losers.map(s => `
                            <tr data-live-symbol="${s.symbol}" onclick="selectStock('${s.symbol}')" style="cursor:pointer">
                                <td><strong>${s.name}</strong></td>
                                <td data-live-price>${fmtPrice(s.price)}</td>
                                <td class="negative" data-live-change-pct>${fmtPct(s.changePercent)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }

        refreshLiveSubscriptions();
        applyLiveDomQuotes();
    } catch (err) {
        console.error('Dashboard gainers/losers error:', err);
    }
}

// Stock Selection - opens the dedicated chart view
function selectStock(symbol) {
    console.log('[selectStock] called with:', symbol);
    const sym = normalizeSymbol(symbol);
    currentSymbol = sym;
    const disp = displaySymbol(sym);

    // Update all stock name / badge elements across UI
    document.querySelectorAll('#chartStockName, #currentStockName, #chartSymbolBadge').forEach(el => {
        if (el) el.textContent = disp;
    });

    localStorage.setItem('lastStock', sym);

    // Subscribe to WebSocket for live price updates on this symbol
    subscribeToChartSymbol(sym);

    // Set the chart symbol input
    const chartInput = document.getElementById('chartSymbolInput');
    if (chartInput) chartInput.value = sym;

    // Show loading price
    const priceEl = document.getElementById('chartPrice');
    if (priceEl) priceEl.textContent = 'Loading...';

    console.log('[selectStock] calling showTab(chart) and loadChartChart');
    showTab('chart');
    loadChartChart();
}

// Open any stock directly in the chart view
function openStockChart(symbol) {
    selectStock(symbol);
}

// ===== CHART WATCHLIST =====

// Load watchlist into chart sidebar
async function refreshChartWatchlist() {
    loadChartWatchlist();
}

async function loadChartWatchlist() {
    const container = document.getElementById('chartWatchlistContainer');
    if (!container) return;

    try {
        const data = await api('/api/watchlist');

        if (data.watchlist && data.watchlist.length > 0) {
            container.innerHTML = data.watchlist.map(w => {
                const sym = w.symbol;
                const changePct = w.changePercent || 0;
                const isPositive = changePct >= 0;
                return `
                    <div class="watchlist-item-pro" data-live-symbol="${sym}" onclick="selectStockFromChartWatchlist('${sym}')" role="button" tabindex="0" aria-label="Select ${displaySymbol(sym)}">
                        <div class="watchlist-item-info">
                            <div class="symbol">${displaySymbol(sym)}</div>
                            <div class="price" data-live-price>${fmtPrice(w.price)}</div>
                        </div>
                        <div style="display:flex; align-items:center; gap:10px;">
                            <div class="watchlist-item-change ${isPositive ? 'positive' : 'negative'}" data-live-change-pct>
                                ${isPositive ? '+' : ''}${fmtPct(changePct)}
                            </div>
                            <button class="watchlist-delete-btn" onclick="event.stopPropagation(); removeFromChartWatchlist('${sym}')" title="Remove from watchlist" aria-label="Remove ${displaySymbol(sym)} from watchlist">
                                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                    <polyline points="3 6 5 6 21 6"></polyline>
                                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                </svg>
                            </button>
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            container.innerHTML = `
                <div class="empty-state" style="text-align:center; padding:32px 16px;">
                    <p class="empty-text" style="font-size:13px; color:var(--text-secondary);">No stocks in watchlist</p>
                    <p class="empty-hint" style="font-size:11px; color:var(--text-muted); margin-top:4px;">Add symbols above to track them instantly</p>
                </div>
            `;
        }

        refreshLiveSubscriptions();
        applyLiveDomQuotes();
    } catch (err) {
        console.error('Chart watchlist error:', err);
        container.innerHTML = '<p class="placeholder" style="text-align:center; font-size:12px;">Error loading watchlist</p>';
    }
}

// Select stock from chart watchlist
function selectStockFromChartWatchlist(symbol) {
    console.log('[selectStockFromChartWatchlist] called with:', symbol);
    selectStock(symbol);
}

// Add stock to chart watchlist
async function addToChartWatchlist() {
    const input = document.getElementById('chartWatchlistSearch');
    if (!input || !input.value.trim()) return;
    
    const sym = normalizeSymbol(input.value.trim());
    
    try {
        await api('/api/watchlist', {
            method: 'POST',
            body: JSON.stringify({ symbol: sym })
        });
        input.value = '';
        document.getElementById('chartWatchlistSuggestions').innerHTML = '';
        document.getElementById('chartWatchlistSuggestions').classList.remove('active');
        loadChartWatchlist();
        showToast('Added to watchlist', 'success');
    } catch (err) {
        console.error('Add to watchlist error:', err);
        showToast('Failed to add to watchlist', 'error');
    }
}

// Remove stock from chart watchlist
async function removeFromChartWatchlist(symbol) {
    try {
        await api(`/api/watchlist/${symbol}`, { method: 'DELETE' });
        loadChartWatchlist();
        showToast('Removed from watchlist', 'info');
    } catch (err) {
        console.error('Remove from watchlist error:', err);
    }
}

// Search stocks for chart watchlist
let chartWatchlistSearchTimeout = null;
async function searchStockForChartWatchlist(query) {
    const container = document.getElementById('chartWatchlistSuggestions');
    if (!container) return;
    
    if (query.length < 1) {
        container.innerHTML = '';
        container.classList.remove('active');
        return;
    }
    
    clearTimeout(chartWatchlistSearchTimeout);
    chartWatchlistSearchTimeout = setTimeout(async () => {
        const data = await api(`/api/stocks/search?query=${query}`);
        if (data && data.length > 0) {
            container.innerHTML = data.slice(0, 8).map(s => `
                <div class="search-item" onclick="event.stopPropagation(); addSymbolToChartWatchlist('${s.symbol}')" style="cursor:pointer; padding:6px 8px; border-bottom:1px solid var(--border);">
                    <strong>${displaySymbol(s.symbol)}</strong>
                    <small style="color:var(--text-muted); font-size:10px; display:block;">${s.name || ''}</small>
                </div>
            `).join('');
            container.classList.add('active');
        } else {
            container.innerHTML = '<div style="padding:6px 8px; font-size:11px; color:var(--text-muted);">No results</div>';
            container.classList.add('active');
        }
    }, 200);
}

function addSymbolToChartWatchlist(symbol) {
    const input = document.getElementById('chartWatchlistSearch');
    if (input) input.value = displaySymbol(symbol);
    document.getElementById('chartWatchlistSuggestions').innerHTML = '';
    document.getElementById('chartWatchlistSuggestions').classList.remove('active');
    addToChartWatchlist();
}

// Load chart from symbol input (Enter key or button)
function loadChartSymbolFromInput() {
    loadChartChart();
}

// Enter key on chart symbol input
document.getElementById('chartSymbolInput')?.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        loadChartChart();
    }
});

// Chart symbol search with clickable results
let chartSymbolSearchTimeout = null;
document.getElementById('chartSymbolInput')?.addEventListener('input', async (e) => {
    const q = e.target.value.trim();
    const container = document.getElementById('chartSearchResults');
    if (!container) return;
    
    if (q.length < 2) {
        container.innerHTML = '';
        container.classList.remove('active');
        return;
    }
    
    clearTimeout(chartSymbolSearchTimeout);
    chartSymbolSearchTimeout = setTimeout(async () => {
        const data = await api(`/api/stocks/search?query=${encodeURIComponent(q)}`);
        if (data && data.length > 0) {
            container.innerHTML = data.slice(0, 8).map(s => `
                <div class="search-item" onclick="event.stopPropagation(); selectStockFromSearch('${s.symbol}')" style="cursor:pointer; padding:6px 8px; border-bottom:1px solid var(--border);">
                    <strong>${displaySymbol(s.symbol)}</strong>
                    <small style="color:var(--text-muted); font-size:10px; display:block;">${s.name || ''}</small>
                </div>
            `).join('');
            container.classList.add('active');
        } else {
            container.innerHTML = '<div style="padding:6px 8px; font-size:11px; color:var(--text-muted);">No results</div>';
            container.classList.add('active');
        }
    }, 200);
});

function selectStockFromSearch(symbol) {
    const input = document.getElementById('chartSymbolInput');
    if (input) input.value = symbol;
    document.getElementById('chartSearchResults').innerHTML = '';
    document.getElementById('chartSearchResults').classList.remove('active');
    loadChartChart();
}

// Enter key on chart watchlist search
document.getElementById('chartWatchlistSearch')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        addToChartWatchlist();
    }
});

// Initialize chart watchlist when tab opens
const _originalShowTabChart2 = window.showTab;
window.showTab = function(tabName) {
    console.log('[showTab] called with:', tabName);
    _originalShowTabChart2(tabName);
    if (tabName === 'chart') {
        console.log('[showTab] chart tab activated');
        if (!chartChart) {
            console.log('[showTab] initializing chartChart');
            initChartChart();
        }
        console.log('[showTab] calling loadChartChart');
        loadChartChart();
        loadChartWatchlist();
    }
    if (tabName === 'upstox-intraday') {
        initUpstoxDesk();
    }
};

// Search - input listener
// Main search input - type as we go with debouncing
let searchInputTimeout = null;
document.getElementById('searchInput')?.addEventListener('input', async (e) => {
    const q = e.target.value.trim();
    if (q.length < 2) {
        document.getElementById('searchResults').classList.remove('active');
        return;
    }
    
    clearTimeout(searchInputTimeout);
    searchInputTimeout = setTimeout(async () => {
        const data = await api(`/api/stocks/search?query=${encodeURIComponent(q)}`);
        const container = document.getElementById('searchResults');
        
        if (data && data.length > 0) {
            container.innerHTML = data.slice(0, 10).map(r => `
                <div class="search-item" style="display:flex; justify-content:space-between; align-items:center;">
                    <div onclick="selectStock('${r.symbol}')" style="cursor:pointer; flex:1;">
                        <strong>${r.symbol.replace('.NS', '')}</strong>
                        <small style="color: var(--text-muted); margin-left: 8px; display:block;">${r.name || ''}</small>
                    </div>
                    <button class="btn-sm icon-btn" onclick="event.stopPropagation(); openStockChart('${r.symbol}')" title="Open Chart" aria-label="Open chart for ${r.symbol}">
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <rect x="1" y="3" width="18" height="18" rx="2" ry="2"></rect>
                            <line x1="1" y1="12" x2="7" y2="12"></line>
                            <line x1="1" y1="19" x2="7" y2="19"></line>
                            <line x1="7" y1="3" x2="19" y2="3"></line>
                            <line x1="14" y1="3" x2="14" y2="21"></line>
                        </svg>
                    </button>
                </div>
            `).join('');
            container.classList.add('active');
        } else {
            container.classList.remove('active');
        }
    }, 200);
});

// Enter key on search input opens first result in chart
document.getElementById('searchInput')?.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        const q = e.target.value.trim();
        if (q.length < 2) return;
        const data = await api(`/api/stocks/search?query=${encodeURIComponent(q)}`);
        if (data && data.length > 0) {
            selectStock(data[0].symbol);
            document.getElementById('searchResults').classList.remove('active');
            document.getElementById('searchInput').value = '';
        }
    }
});

// Market
async function loadMarket() {
    const data = await api('/api/market');
    const container = document.getElementById('marketData');
    
    if (data.indices) {
        container.innerHTML = data.indices.map(idx => `
            <div class="index-card" data-live-symbol="${idx.symbol}">
                <div class="name">${idx.name}</div>
                <div class="value" data-live-price>${fmtPrice(idx.price)}</div>
                <div class="change ${idx.change >= 0 ? 'positive' : 'negative'}" data-live-change>
                    ${fmtChg(idx.change)} (${fmtPct(idx.changePercent)})
                </div>
            </div>
        `).join('');
    }
    
    // Load gainers/losers
    const gainersData = await api('/api/market/top-gainers');
    const losersData = await api('/api/market/top-losers');
    
    if (gainersData.gainers) {
        document.getElementById('marketGainers').innerHTML = `
            <table>
                <thead><tr><th>Stock</th><th>Price</th><th>Change</th></tr></thead>
                <tbody>
                    ${gainersData.gainers.map(s => `
                        <tr data-live-symbol="${s.symbol}" onclick="selectStock('${s.symbol}'); showTab('chart')" style="cursor:pointer">
                            <td><strong>${s.name}</strong></td>
                            <td data-live-price>${fmtPrice(s.price)}</td>
                            <td class="positive" data-live-change-pct>+${fmtPct(s.changePercent)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }
    
    if (losersData.losers) {
        document.getElementById('marketLosers').innerHTML = `
            <table>
                <thead><tr><th>Stock</th><th>Price</th><th>Change</th></tr></thead>
                <tbody>
                    ${losersData.losers.map(s => `
                        <tr data-live-symbol="${s.symbol}" onclick="selectStock('${s.symbol}'); showTab('chart')" style="cursor:pointer">
                            <td><strong>${s.name}</strong></td>
                            <td data-live-price>${fmtPrice(s.price)}</td>
                            <td class="negative" data-live-change-pct>${fmtPct(s.changePercent)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    refreshLiveSubscriptions();
    applyLiveDomQuotes();
}

// Signals
async function loadSignals() {
    const data = await api('/api/signals');
    const container = document.getElementById('signalsContent');
    
    if (data.signals && data.signals.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Stock</th><th>Signal</th><th>Indicator</th><th>Strength</th><th>Price</th><th>Action</th></tr></thead>
                <tbody>
                    ${data.signals.map(s => `
                        <tr data-live-symbol="${s.symbol}">
                            <td><strong>${s.name || s.symbol.replace('.NS', '')}</strong></td>
                            <td><span class="badge ${s.type === 'BUY' ? 'positive' : s.type === 'SELL' ? 'negative' : ''}">${s.type}</span></td>
                            <td>${s.indicator || '-'}</td>
                            <td>${s.strength || '-'}</td>
                            <td data-live-price>${fmtPrice(s.price)}</td>
                            <td><button class="btn-primary" onclick="selectStock('${s.symbol}'); showTab('chart')">View</button></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    refreshLiveSubscriptions();
    applyLiveDomQuotes();
}

// Sectors
async function loadSectors() {
    const data = await api('/api/sector');
    const container = document.getElementById('sectorContent');
    
    if (data.sectors) {
        container.innerHTML = data.sectors.map(s => `
            <div class="sector-card">
                <h4>${s.name}</h4>
                <div class="sector-change ${s.change >= 0 ? 'positive' : 'negative'}">
                    ${fmtChg(s.change)}%
                </div>
                <div style="font-size:12px; color:var(--text-secondary); margin-top:8px;">
                    ${s.stocks?.length || 0} stocks
                </div>
            </div>
        `).join('');
    }
}

// Screener
async function quickScreen(preset) {
    showLoading();
    let params = {};
    
    switch(preset) {
        case 'oversold': params.rsi_below = 30; break;
        case 'overbought': params.rsi_above = 70; break;
        case 'macd_cross': params.macd_cross_up = true; break;
        case 'golden_cross': params.price_above_sma = 20; break;
        case 'volume_spike': params.volume_above_avg = 2; break;
        case 'strong_trend': params.adx_above = 25; break;
    }
    
    const queryString = new URLSearchParams(params).toString();
    const data = await api(`/api/screen?${queryString}`);
    displayScreenerResults(data);
    hideLoading();
}

async function runScreener() {
    showLoading();
    const params = new URLSearchParams();
    
    const rsiBelow = document.getElementById('rsiBelow').value;
    const rsiAbove = document.getElementById('rsiAbove').value;
    const goldenCross = document.getElementById('goldenCross').value;
    const volumeSpike = document.getElementById('volumeSpike').value;
    const adxAbove = document.getElementById('adxAbove').value;
    const macdSignal = document.getElementById('macdSignal').value;
    
    if (rsiBelow) params.append('rsi_below', rsiBelow);
    if (rsiAbove) params.append('rsi_above', rsiAbove);
    if (goldenCross) params.append('price_above_sma', '20');
    if (volumeSpike) params.append('volume_above_avg', volumeSpike);
    if (macdSignal === 'bullish') params.append('macd_cross_up', 'true');
    
    const data = await api(`/api/screen?${params.toString()}`);
    displayScreenerResults(data);
    hideLoading();
}

function displayScreenerResults(data) {
    const container = document.getElementById('screenerResults');
    
    if (data.results && data.results.length > 0) {
        container.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3>Found ${data.results.length} stocks</h3>
                </div>
                <table>
                    <thead><tr><th>Stock</th><th>Price</th><th>Change</th><th>RSI</th><th>MACD</th><th>Action</th></tr></thead>
                    <tbody>
                        ${data.results.map(s => `
                            <tr data-live-symbol="${s.symbol}">
                                <td><strong>${s.name}</strong></td>
                            <td data-live-price>${fmtPrice(s.price)}</td>
                                <td class="${s.changePercent >= 0 ? 'positive' : 'negative'}" data-live-change-pct>${fmtPct(s.changePercent)}</td>
                                <td>${s.rsi?.toFixed(2) || '-'}</td>
                                <td>${s.macd?.toFixed(2) || '-'}</td>
                                <td><button class="btn-primary" onclick="selectStock('${s.symbol}'); showTab('chart')">View</button></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } else {
        container.innerHTML = '<div class="card"><p class="placeholder">No stocks match your criteria</p></div>';
    }

    refreshLiveSubscriptions();
    applyLiveDomQuotes();
}

// Compare
async function compareStocks() {
    const s1 = document.getElementById('compareSymbol1').value;
    const s2 = document.getElementById('compareSymbol2').value;
    const s3 = document.getElementById('compareSymbol3').value;
    
    const symbols = [s1, s2].filter(Boolean);
    if (s3) symbols.push(s3);
    
    const data = await api(`/api/compare?symbols=${symbols.join(',')}`);
    const container = document.getElementById('compareResults');
    
    if (data.comparison) {
        container.innerHTML = `
            <div class="card">
                <table>
                    <thead><tr><th>Metric</th>${data.comparison.map(s => `<th>${s.symbol.replace('.NS', '')}</th>`).join('')}</tr></thead>
                    <tbody>
                        <tr><td>Price</td>${data.comparison.map(s => `<td>${fmtPrice(s.price)}</td>`).join('')}</tr>
                        <tr><td>RSI</td>${data.comparison.map(s => `<td>${s.rsi?.toFixed(2) || '-'}</td>`).join('')}</tr>
                        <tr><td>MACD</td>${data.comparison.map(s => `<td>${s.macd?.toFixed(2) || '-'}</td>`).join('')}</tr>
                        <tr><td>P/E Ratio</td>${data.comparison.map(s => `<td>${s.pe || '-'}</td>`).join('')}</tr>
                        <tr><td>52W High</td>${data.comparison.map(s => `<td>${fmtPrice(s.high52)}</td>`).join('')}</tr>
                        <tr><td>52W Low</td>${data.comparison.map(s => `<td>${fmtPrice(s.low52)}</td>`).join('')}</tr>
                    </tbody>
                </table>
            </div>
        `;
    }
}

// Backtest
async function runBacktest() {
    showLoading();
    const symbol = document.getElementById('backtestSymbol').value;
    const strategy = document.getElementById('backtestStrategy').value;
    const period = document.getElementById('backtestPeriod').value;
    
    const data = await api('/api/backtest', {
        method: 'POST',
        body: JSON.stringify({ symbol, strategy, period })
    });
    
    const container = document.getElementById('backtestResults');
    
    if (data.trades) {
        container.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3>Backtest Results: ${data.strategy} on ${data.symbol}</h3>
                </div>
                <div class="strategy-result mb-2">
                    <div class="result-row">
                        <span>Initial Capital</span>
                        <span>₹${data.initialCapital?.toLocaleString() || '100,000'}</span>
                    </div>
                    <div class="result-row">
                        <span>Final Equity</span>
                        <span class="${data.totalReturn >= 0 ? 'positive' : 'negative'}">₹${data.finalEquity?.toLocaleString() || '-'}</span>
                    </div>
                    <div class="result-row">
                        <span>Total Return</span>
                        <span class="${data.totalReturn >= 0 ? 'positive' : 'negative'}">${data.totalReturn?.toFixed(2) || '-'}%</span>
                    </div>
                    <div class="result-row">
                        <span>Win Rate</span>
                        <span>${data.winRate?.toFixed(2) || '-'}%</span>
                    </div>
                    <div class="result-row">
                        <span>Total Trades</span>
                        <span>${data.totalTrades || '-'}</span>
                    </div>
                </div>
                ${data.trades.length > 0 ? `
                    <h4 style="margin-bottom:12px;">Recent Trades</h4>
                    <table>
                        <thead><tr><th>Date</th><th>Type</th><th>Price</th><th>P&L</th></tr></thead>
                        <tbody>
                            ${data.trades.slice(-10).map(t => `
                                <tr>
                                    <td>${t.date}</td>
                                    <td><span class="badge ${t.type === 'BUY' ? 'positive' : 'negative'}">${t.type}</span></td>
                                    <td>₹${t.price}</td>
                                    <td class="${(t.pnl || 0) >= 0 ? 'positive' : 'negative'}">${t.pnl ? '₹' + t.pnl.toFixed(2) : '-'}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                ` : ''}
            </div>
        `;
    }
    hideLoading();
}

// News
async function loadNews() {
    const data = await api('/api/news');
    const container = document.getElementById('marketNews');
    
    const news = data.news || data.items || [];
    if (news.length > 0) {
        container.innerHTML = news.map(n => `
            <div class="news-item">
                <h4>${n.title}</h4>
                <p>${n.summary || ''}</p>
                <div class="news-meta">${n.publisher || n.source || 'Unknown'} • ${n.published || n.publishedAt || n.time || ''}</div>
            </div>
        `).join('');
    } else {
        container.innerHTML = '<p class="placeholder">No market news available</p>';
    }
}

async function loadStockNews() {
    const raw = document.getElementById('newsSymbol').value;
    const symbol = normalizeSymbol(raw);
    document.getElementById('newsSymbol').value = symbol;
    const data = await api(`/api/news/${symbol}`);
    const container = document.getElementById('stockNews');
    
    const news = data.news || [];
    if (news.length > 0) {
        container.innerHTML = news.map(n => `
            <div class="news-item">
                <h4>${n.title}</h4>
                <p>${n.summary || ''}</p>
                <div class="news-meta">${n.publisher || 'Upstox'} • ${n.published || n.publishedAt || ''}</div>
            </div>
        `).join('');
    } else {
        container.innerHTML = '<p class="placeholder">No news available for this stock</p>';
    }
}

// Portfolio
async function loadPortfolio() {
    const data = await api('/api/portfolio');
    const container = document.getElementById('portfolioTable');
    portfolioHoldingsCache = data.holdings || [];
    
    if (data.holdings && data.holdings.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Symbol</th><th>Qty</th><th>Buy Price</th><th>LTP</th><th>Day P&L</th><th>P&L</th><th>Action</th></tr></thead>
                <tbody>
                    ${data.holdings.map(h => `
                        <tr data-live-symbol="${h.symbol}" data-live-qty="${h.quantity}" data-live-buy="${h.buyPrice}">
                            <td><strong>${h.symbol.replace('.NS', '')}</strong></td>
                            <td>${h.quantity}</td>
                            <td>₹${h.buyPrice}</td>
                            <td data-live-price>${fmtPrice(h.currentPrice || h.buyPrice)}</td>
                            <td class="${(h.dayChangePnl || 0) >= 0 ? 'positive' : 'negative'}" data-live-daypnl>${(h.dayChangePnl || 0) >= 0 ? '+' : '-'}₹${Math.abs(h.dayChangePnl || 0).toFixed(2)}</td>
                            <td class="${(h.pnl || 0) >= 0 ? 'positive' : 'negative'}" data-live-pnl>${(h.pnl || 0) >= 0 ? '+' : '-'}₹${Math.abs(h.pnl || 0).toFixed(2)} (${(h.pnlPercent || 0) >= 0 ? '+' : ''}${(h.pnlPercent || 0).toFixed(2)}%)</td>
                            <td>
                                <button class="btn-secondary" style="padding:4px 10px; font-size:12px;" onclick="toggleSellRow('${h.symbol}', ${h.quantity}, ${h.currentPrice || h.buyPrice})">Sell</button>
                                <button class="btn-danger" onclick="removePortfolio('${h.symbol}')">Remove</button>
                            </td>
                        </tr>
                        <tr class="portfolio-sell-row" id="sellRow-${h.symbol}" style="display:none">
                            <td colspan="7" style="padding:10px 12px;">
                                <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                                    <span style="font-weight:600;">Sell ${h.symbol.replace('.NS', '')}</span>
                                    <span style="font-size:12px; color:var(--text-secondary);">(you hold ${h.quantity})</span>
                                    <input type="number" id="sellQty-${h.symbol}" min="1" max="${h.quantity}" step="1" value="${h.quantity}" style="width:90px;" aria-label="Quantity to sell">
                                    <span style="font-size:12px;">@ ₹</span>
                                    <input type="number" id="sellPrice-${h.symbol}" min="0" step="0.05" value="${h.currentPrice || h.buyPrice}" style="width:110px;" aria-label="Sell price">
                                    <button class="btn-primary" style="padding:6px 14px;" onclick="confirmSellHolding('${h.symbol}')">Confirm Sell</button>
                                    <button class="btn-secondary" style="padding:6px 14px;" onclick="toggleSellRow('${h.symbol}')">Cancel</button>
                                    <span style="font-size:11px; color:var(--text-secondary);">Sell price optional — records realized P&L</span>
                                </div>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No holdings yet</p>';
    }

    refreshLiveSubscriptions();
    applyLiveDomQuotes();
    loadRealizedPnl();
    loadDividendData();
}

// ===== ALLOCATION DONUT (per-stock weights) =====
const DONUT_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#14b8a6', '#a855f7', '#eab308'];

function fmtCompactInr(v) {
    if (v >= 1e7) return '₹' + (v / 1e7).toFixed(2) + ' Cr';
    if (v >= 1e5) return '₹' + (v / 1e5).toFixed(2) + ' L';
    return '₹' + Math.round(v).toLocaleString();
}

// SVG donut of per-stock portfolio weights + legend. Re-rendered live.
function renderAllocationDonut(donutId, legendId, holdings) {
    const donutEl = document.getElementById(donutId);
    const legendEl = document.getElementById(legendId);
    if (!donutEl || !legendEl) return;

    const items = (holdings || [])
        .map(h => {
            const qty = Number(h.quantity) || 0;
            const quote = getLiveQuote(h.symbol);
            const price = quote ? quote.price : (Number(h.currentPrice) || Number(h.buyPrice) || 0);
            return { symbol: h.symbol, value: price * qty };
        })
        .filter(i => i.value > 0)
        .sort((a, b) => b.value - a.value);

    const total = items.reduce((s, i) => s + i.value, 0);
    if (!items.length || total <= 0) {
        donutEl.innerHTML = '<p class="placeholder">No allocation data</p>';
        legendEl.innerHTML = '';
        return;
    }

    const R = 15.9155; // circumference ≈ 100 units
    let acc = 0;
    const segs = items.map((it, idx) => {
        const pct = (it.value / total) * 100;
        const off = 25 - acc;
        acc += pct;
        const color = DONUT_COLORS[idx % DONUT_COLORS.length];
        return `<circle cx="21" cy="21" r="${R}" fill="none" stroke="${color}" stroke-width="5" stroke-dasharray="${pct.toFixed(2)} ${(100 - pct).toFixed(2)}" stroke-dashoffset="${off.toFixed(2)}"></circle>`;
    }).join('');

    donutEl.innerHTML = `
        <svg viewBox="0 0 42 42" width="150" height="150" role="img" aria-label="Stock allocation donut">
            <circle cx="21" cy="21" r="${R}" fill="none" stroke="var(--border, rgba(128,128,128,0.25))" stroke-width="5"></circle>
            ${segs}
            <text x="21" y="19.5" text-anchor="middle" style="font-size:4.5px; fill:var(--text-secondary); letter-spacing:0.5px;">TOTAL</text>
            <text x="21" y="25" text-anchor="middle" style="font-size:5px; font-weight:700; fill:var(--text-primary);">${fmtCompactInr(total)}</text>
        </svg>`;

    legendEl.innerHTML = items.map((it, idx) => {
        const pct = (it.value / total) * 100;
        const color = DONUT_COLORS[idx % DONUT_COLORS.length];
        return `<div style="display:flex; align-items:center; gap:8px; font-size:12px; margin-bottom:5px; min-width:220px;">
            <span style="width:10px; height:10px; border-radius:3px; background:${color}; display:inline-block; flex-shrink:0;"></span>
            <span style="font-weight:600;">${it.symbol.replace('.NS', '')}</span>
            <span style="color:var(--text-secondary);">${pct.toFixed(1)}%</span>
            <span style="margin-left:auto; color:var(--text-secondary);">${fmtCompactInr(it.value)}</span>
        </div>`;
    }).join('');
}

// ===== BENCHMARK: PORTFOLIO vs NIFTY 50 (#7) =====
let benchmarkPeriod = '1Y';
let benchmarkChartObj = null;

const BENCHMARK_PERIODS = ['1M', '3M', '6M', '1Y', 'ALL'];

// Two normalized (100 = start) line series: portfolio buy-and-hold vs NIFTY 50.
async function loadBenchmark(period) {
    const card = document.getElementById('benchmarkCard');
    if (!card) return;
    if (period) benchmarkPeriod = period;

    renderBenchmarkPeriodButtons();

    const summary = document.getElementById('benchmarkSummary');
    const chartDiv = document.getElementById('benchmarkChart');
    const res = await api(`/api/portfolio/benchmark?period=${encodeURIComponent(benchmarkPeriod)}`);
    const errMsg = res.error || res.detail;

    if (errMsg) {
        card.style.display = '';
        summary.innerHTML = `<span style="color:var(--text-muted);">${escapeHtml(errMsg)}</span>`;
        chartDiv.innerHTML = '';
        if (benchmarkChartObj) { benchmarkChartObj.remove(); benchmarkChartObj = null; }
        return;
    }

    card.style.display = '';

    const pRet = Number(res.portfolioReturn) || 0;
    const bRet = Number(res.benchmarkReturn) || 0;
    const diff = pRet - bRet;
    const fmtPct = v => `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
    summary.innerHTML =
        `<span style="margin-right:14px;">Portfolio: <span class="${pRet >= 0 ? 'positive' : 'negative'}" style="font-weight:700;">${fmtPct(pRet)}</span></span>` +
        `<span style="margin-right:14px;">NIFTY 50: <span class="${bRet >= 0 ? 'positive' : 'negative'}" style="font-weight:700;">${fmtPct(bRet)}</span></span>` +
        `<span>${diff >= 0 ? 'Outperforming' : 'Underperforming'} by <span class="${diff >= 0 ? 'positive' : 'negative'}" style="font-weight:700;">${fmtPct(diff)}</span></span>` +
        `<span style="color:var(--text-muted);"> · buy-and-hold, weighted by current market value, start = 100</span>`;

    if (!res.dates || res.dates.length < 2 || !chartDiv) return;
    chartDiv.innerHTML = '';

    if (benchmarkChartObj) { benchmarkChartObj.remove(); benchmarkChartObj = null; }
    const height = 300;
    benchmarkChartObj = LightweightCharts.createChart(chartDiv, {
        width: chartDiv.clientWidth || 800,
        height: height,
        layout: { background: { color: getChartBg() }, textColor: '#8888a0' },
        grid: { vertLines: { color: 'rgba(255,255,255,0.04)' }, horzLines: { color: 'rgba(255,255,255,0.04)' } },
        rightPriceScale: { borderColor: 'rgba(255,255,255,0.06)' },
        timeScale: { borderColor: 'rgba(255,255,255,0.06)' }
    });

    const portfolioSeries = benchmarkChartObj.addLineSeries({ color: '#6366f1', lineWidth: 2, title: 'Portfolio' });
    const benchSeries = benchmarkChartObj.addLineSeries({ color: '#f59e0b', lineWidth: 2, title: 'NIFTY 50' });
    portfolioSeries.setData(res.dates.map((d, i) => ({ time: d, value: res.portfolioSeries[i] })));
    benchSeries.setData(res.dates.map((d, i) => ({ time: d, value: res.benchmarkSeries[i] })));
    benchmarkChartObj.timeScale().fitContent();
}

function renderBenchmarkPeriodButtons() {
    const wrap = document.getElementById('benchmarkPeriods');
    if (!wrap) return;
    wrap.innerHTML = BENCHMARK_PERIODS.map(p =>
        `<button class="btn-secondary" style="padding:4px 10px; font-size:12px; ${p === benchmarkPeriod ? 'border-color:var(--accent); color:var(--accent);' : ''}" onclick="loadBenchmark('${p}')">${p}</button>`
    ).join('');
}

// ===== DIVIDENDS & CORPORATE ACTIONS =====
let portfolioHoldingsCache = [];
// #8b — auto-detected event suggestions, keyed by event id for form pre-fill.
let eventSuggestionsById = {};

async function loadDividendData() {
    const card = document.getElementById('dividendCard');
    if (!card) return;
    const data = await api('/api/portfolio/dividends');
    const dividends = data.dividends || [];
    const actions = data.corpActions || [];
    const holdings = portfolioHoldingsCache || [];
    const eventsData = await api('/api/portfolio/events');
    const suggestions = (eventsData && eventsData.suggestions) || [];
    eventSuggestionsById = {};
    suggestions.forEach(s => { eventSuggestionsById[s.id] = s; });

    if (!dividends.length && !actions.length && !holdings.length) {
        card.style.display = 'none';
        return;
    }
    card.style.display = '';

    const options = holdings.map(h =>
        `<option value="${h.symbol}">${h.symbol.replace('.NS', '')}</option>`).join('');
    const today = new Date().toISOString().slice(0, 10);

    const entries = [
        ...dividends.map(d => ({
            date: d.recordedAt || d.date, type: 'Dividend', symbol: d.symbol,
            detail: `₹${d.amount}${d.note ? ' — ' + escapeHtml(d.note) : ''}`, amount: d.amount
        })),
        ...actions.map(a => ({
            date: a.recordedAt || a.date,
            type: a.type === 'bonus' ? 'Bonus' : 'Split', symbol: a.symbol,
            detail: `${a.ratio}:1 — qty ${a.before?.quantity ?? '?'} → ${a.after?.quantity ?? '?'} · avg ₹${a.before?.avgPrice ?? '?'} → ₹${a.after?.avgPrice ?? '?'}`,
            amount: null
        }))
    ].sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0));

    const entryRows = entries.map(e => `
        <tr>
            <td>${e.date ? new Date(e.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' }) : '—'}</td>
            <td><span style="font-size:11px; padding:2px 8px; border-radius:6px; background:${e.type === 'Dividend' ? 'rgba(16,185,129,0.15)' : 'rgba(59,130,246,0.15)'}; color:${e.type === 'Dividend' ? '#10b981' : '#3b82f6'};">${e.type}</span></td>
            <td><strong>${e.symbol.replace('.NS', '')}</strong></td>
            <td style="font-size:12px;">${e.detail}</td>
        </tr>`).join('');

    // #8b — auto-detected suggestions (dividend / split / bonus) for holdings.
    const evMeta = {
        dividend: { label: 'Dividend', color: '#10b981', bg: 'rgba(16,185,129,0.15)' },
        split: { label: 'Split', color: '#3b82f6', bg: 'rgba(59,130,246,0.15)' },
        bonus: { label: 'Bonus', color: '#8b5cf6', bg: 'rgba(139,92,246,0.15)' }
    };
    const suggestionRows = suggestions.map(s => {
        const meta = evMeta[s.type] || evMeta.dividend;
        const short = s.subject && s.subject.length > 120 ? s.subject.slice(0, 120) + '…' : (s.subject || '');
        const detail = s.type === 'dividend'
            ? (s.suggestedAmount != null
                ? `₹${s.perShare}/share × ${s.quantity} → <strong>₹${s.suggestedAmount}</strong> suggested`
                : 'Amount not stated — enter manually')
            : (s.ratio
                ? `${s.ratio}:1 suggested — verify before applying`
                : 'Ratio not stated — enter manually');
        const date = s.publishedAt ? new Date(s.publishedAt).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '';
        return `
            <tr>
                <td><span style="font-size:11px; padding:2px 8px; border-radius:6px; background:${meta.bg}; color:${meta.color};">${meta.label}</span></td>
                <td><strong>${escapeHtml(s.symbol)}</strong></td>
                <td style="font-size:12px; max-width:380px;">${escapeHtml(short)}<br><span style="font-size:11px; color:var(--text-secondary);">${date}</span></td>
                <td style="font-size:12px;">${detail}</td>
                <td style="white-space:nowrap;">
                    <button class="btn-primary" style="padding:3px 10px; font-size:11px;" onclick="useEventInForm('${s.id}')">Use in form</button>
                    <button class="btn-secondary" style="padding:3px 10px; font-size:11px;" onclick="dismissEvent('${s.id}')">Dismiss</button>
                </td>
            </tr>`;
    }).join('');

    const suggestionsBlock = suggestions.length ? `
        <div style="border:1px solid rgba(245,158,11,0.35); border-radius:8px; padding:10px 12px; margin-bottom:14px;">
            <div style="font-size:12px; margin-bottom:6px;">
                <strong>Detected events</strong> — from NSE announcements
                <span style="color:var(--text-secondary);">· suggestions only, applying is always manual</span>
            </div>
            <table>
                <thead><tr><th>Type</th><th>Symbol</th><th>Announcement</th><th>Suggestion</th><th></th></tr></thead>
                <tbody>${suggestionRows}</tbody>
            </table>
        </div>` : '';

    document.getElementById('dividendBody').innerHTML = `
        <div style="font-size:13px; margin-bottom:12px;">
            Lifetime dividends: <span class="positive">+₹${(data.totalDividends || 0).toLocaleString()}</span>
            <span style="color:var(--text-secondary);">· ${dividends.length} dividend${dividends.length !== 1 ? 's' : ''} · ${actions.length} corporate action${actions.length !== 1 ? 's' : ''}</span>
        </div>

        ${suggestionsBlock}
        <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-bottom:8px;">
            <select id="divSymbol" style="width:150px;" aria-label="Stock for dividend">${options || '<option value="">— no holdings —</option>'}</select>
            <input type="number" id="divAmount" placeholder="Amount ₹" step="0.01" min="0" style="width:110px;">
            <input type="date" id="divDate" value="${today}" style="width:150px;">
            <input type="text" id="divNote" placeholder="Note (optional)" style="width:170px;">
            <button class="btn-primary" style="padding:6px 14px;" onclick="addDividend()">Add Dividend</button>
        </div>

        <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-bottom:14px;">
            <select id="caSymbol" style="width:150px;" aria-label="Stock for corporate action">${options || '<option value="">— no holdings —</option>'}</select>
            <select id="caType" style="width:140px;">
                <option value="split">Stock Split</option>
                <option value="bonus">Bonus Issue</option>
            </select>
            <input type="number" id="caRatio" placeholder="New per old (e.g. 2)" step="any" min="0" style="width:170px;">
            <button class="btn-secondary" style="padding:6px 14px;" onclick="applyCorpAction()">Apply Action</button>
            <span style="font-size:11px; color:var(--text-secondary);">2:1 → qty ×2, avg ÷2 · invested value preserved</span>
        </div>

        ${entries.length ? `
        <table>
            <thead><tr><th>Date</th><th>Type</th><th>Symbol</th><th>Detail</th></tr></thead>
            <tbody>${entryRows}</tbody>
        </table>` : '<p class="placeholder">No dividends or corporate actions recorded yet</p>'}
    `;
}

async function addDividend() {
    const symbol = document.getElementById('divSymbol')?.value;
    const amount = parseFloat(document.getElementById('divAmount')?.value);
    const date = document.getElementById('divDate')?.value;
    const note = document.getElementById('divNote')?.value || '';
    if (!symbol) return showToast('Select a stock', 'warning');
    if (!Number.isFinite(amount) || amount <= 0) return showToast('Enter a valid dividend amount', 'warning');

    const res = await api(`/api/portfolio/${symbol}/dividend`, {
        method: 'POST',
        body: JSON.stringify({ amount, date: date || undefined, note })
    });
    const errMsg = res.error || res.detail;
    if (errMsg) return showToast(errMsg, 'negative');
    showToast(res.message || 'Dividend recorded', 'success');
    loadPortfolio();
}

async function applyCorpAction() {
    const symbol = document.getElementById('caSymbol')?.value;
    const type = document.getElementById('caType')?.value || 'split';
    const ratio = parseFloat(document.getElementById('caRatio')?.value);
    if (!symbol) return showToast('Select a stock', 'warning');
    if (!Number.isFinite(ratio) || ratio <= 0) return showToast('Enter a valid ratio (e.g. 2 for 2:1)', 'warning');
    if (!confirm(`Apply ${ratio}:1 ${type === 'bonus' ? 'bonus issue' : 'stock split'} to ${symbol}? Qty will be ×${ratio}, avg price ÷${ratio}.`)) return;

    const res = await api(`/api/portfolio/${symbol}/corp-action`, {
        method: 'POST',
        body: JSON.stringify({ ratio, type })
    });
    const errMsg = res.error || res.detail;
    if (errMsg) return showToast(errMsg, 'negative');
    showToast(res.message || 'Corporate action applied', 'success');
    loadPortfolio();
    loadPortfolioAnalytics();
}

// #8b — pre-fill the matching form from a detected announcement. The user
// still submits it themselves; nothing is applied automatically.
function useEventInForm(id) {
    const s = eventSuggestionsById[id];
    if (!s) return;
    if (s.type === 'dividend') {
        if (document.getElementById('divSymbol')) document.getElementById('divSymbol').value = s.holdingSymbol;
        const amount = s.suggestedAmount != null ? s.suggestedAmount : (s.perShare || '');
        if (document.getElementById('divAmount')) document.getElementById('divAmount').value = amount;
        if (document.getElementById('divNote')) document.getElementById('divNote').value = (s.subject || '').slice(0, 80);
        if (document.getElementById('divAmount')) document.getElementById('divAmount').focus();
        showToast('Dividend form pre-filled — review and submit', 'info');
    } else {
        if (document.getElementById('caSymbol')) document.getElementById('caSymbol').value = s.holdingSymbol;
        if (document.getElementById('caType')) document.getElementById('caType').value = s.type;
        if (document.getElementById('caRatio')) document.getElementById('caRatio').value = s.ratio || '';
        if (document.getElementById('caRatio')) document.getElementById('caRatio').focus();
        showToast('Split/bonus form pre-filled — verify ratio, then Apply', 'info');
    }
}

// #8b — permanently hide a detected suggestion.
async function dismissEvent(id) {
    const res = await api(`/api/portfolio/events/${id}/dismiss`, { method: 'POST' });
    const errMsg = res.error || res.detail;
    if (errMsg) return showToast(errMsg, 'negative');
    showToast('Event dismissed', 'success');
    loadDividendData();
}

// Toggle the inline "sell portion of a holding" row for a holding.
function toggleSellRow(symbol, qty, price) {
    const row = document.getElementById('sellRow-' + symbol);
    if (!row) return;
    const show = row.style.display === 'none';
    document.querySelectorAll('.portfolio-sell-row').forEach(r => {
        if (r !== row) r.style.display = 'none';
    });
    row.style.display = show ? '' : 'none';
    if (show) {
        if (qty != null) {
            const qtyEl = document.getElementById('sellQty-' + symbol);
            if (qtyEl) { qtyEl.max = qty; qtyEl.value = qty; }
        }
        if (price != null) {
            const priceEl = document.getElementById('sellPrice-' + symbol);
            if (priceEl) priceEl.value = price;
        }
    }
}

// Sell part (or all) of a holding via POST /api/portfolio/{symbol}/sell.
async function confirmSellHolding(symbol) {
    const qty = parseFloat(document.getElementById('sellQty-' + symbol)?.value);
    const price = parseFloat(document.getElementById('sellPrice-' + symbol)?.value);
    if (!Number.isFinite(qty) || qty <= 0) return showToast('Enter a valid quantity to sell', 'warning');

    const body = { quantity: qty };
    if (Number.isFinite(price) && price > 0) body.price = price;

    const res = await api(`/api/portfolio/${symbol}/sell`, {
        method: 'POST',
        body: JSON.stringify(body)
    });

    const errMsg = res.error || res.detail;
    if (errMsg) return showToast(errMsg, 'negative');
    showToast(res.message || `Sold ${qty} of ${symbol}`, 'success');
    loadPortfolio();
    loadPortfolioAnalytics();
}

// Portfolio summary bar: Today's P&L (day change) · Unrealized · Realized.
// Today + Unrealized recompute from liveQuoteCache on every WS tick.
let portfolioRealizedTotal = null;

function updatePortfolioSummaryBar() {
    const el = document.getElementById('portfolioSummaryBar');
    if (!el) return;
    if (!analyticsLiveHoldings.length && portfolioRealizedTotal == null) {
        el.style.display = 'none';
        return;
    }

    let invested = 0;
    let current = 0;
    let dayPnl = 0;
    analyticsLiveHoldings.forEach(h => {
        const qty = Number(h.quantity) || 0;
        const buy = Number(h.buyPrice) || 0;
        invested += qty * buy;
        const quote = getLiveQuote(h.symbol);
        current += (quote ? quote.price : (Number(h.currentPrice) || buy)) * qty;
        dayPnl += quote ? (quote.change || 0) * qty : (Number(h.dayChangePnl) || 0);
    });

    const totalPnl = current - invested;
    const totalPct = invested > 0 ? (totalPnl / invested) * 100 : 0;
    const prevValue = current - dayPnl;
    const dayPct = prevValue > 0 ? (dayPnl / prevValue) * 100 : 0;

    const seg = (label, value, pct, showPct) =>
        `<span style="margin-right:8px;">${label}: <span class="${value >= 0 ? 'positive' : 'negative'}">${value >= 0 ? '+' : '-'}₹${Math.abs(Math.round(value * 100) / 100).toLocaleString()}${showPct && Number.isFinite(pct) && pct !== 0 ? ` (${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%)` : ''}</span></span>`;

    const parts = [
        seg('Today', dayPnl, dayPct, true),
        seg('Unrealized', totalPnl, totalPct, true)
    ];
    if (portfolioRealizedTotal != null) parts.push(seg('Realized', portfolioRealizedTotal, null, false));

    el.style.display = '';
    el.innerHTML = parts.join('<span style="color:var(--text-muted);">·</span> ');
}

// Lifetime realized P&L from recorded sell trades + trade history table.
async function loadRealizedPnl() {
    const data = await api('/api/portfolio/realized');
    portfolioRealizedTotal = data.totalRealizedPnl || 0;
    updatePortfolioSummaryBar();
    renderTradeHistory(data.trades || []);
}

// Render the sell-trade log (newest first). Hidden until the first trade.
function renderTradeHistory(trades) {
    const card = document.getElementById('tradeHistoryCard');
    const body = document.getElementById('tradeHistoryTable');
    if (!card || !body) return;
    if (!trades.length) {
        card.style.display = 'none';
        body.innerHTML = '';
        return;
    }
    card.style.display = '';

    const rows = [...trades].sort((a, b) => new Date(b.soldAt || 0) - new Date(a.soldAt || 0)).map(t => {
        const pnl = t.realizedPnl;
        const date = t.soldAt
            ? new Date(t.soldAt).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
            : '—';
        return `
            <tr>
                <td>${date}</td>
                <td><strong>${t.symbol.replace('.NS', '')}</strong></td>
                <td>${t.quantity}</td>
                <td>${t.price != null ? '₹' + t.price : '—'}</td>
                <td>₹${t.buyPrice}</td>
                <td class="${(pnl || 0) >= 0 ? 'positive' : 'negative'}">${pnl != null ? (pnl >= 0 ? '+' : '-') + '₹' + Math.abs(pnl).toLocaleString() : '—'}</td>
            </tr>`;
    }).join('');

    body.innerHTML = `
        <table>
            <thead><tr><th>Date</th><th>Symbol</th><th>Qty Sold</th><th>Sell Price</th><th>Avg Buy</th><th>Realized P&L</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
}

async function addPortfolio() {
    const symbol = document.getElementById('portfolioSymbol').value;
    const qty = parseInt(document.getElementById('portfolioQty').value);
    const price = parseFloat(document.getElementById('portfolioPrice').value);
    
    if (!symbol || !qty || !price) return showToast('Fill all fields', 'warning');
    
    await api('/api/portfolio', {
        method: 'POST',
        body: JSON.stringify({ symbol, quantity: qty, buy_price: price })
    });
    
    // Clear input fields
    document.getElementById('portfolioSymbol').value = '';
    document.getElementById('portfolioQty').value = '';
    document.getElementById('portfolioPrice').value = '';
    document.getElementById('portfolioSuggestions').innerHTML = '';
    
    loadPortfolio();
    loadPortfolioAnalytics();
}

async function removePortfolio(symbol) {
    await api(`/api/portfolio/${symbol}`, { method: 'DELETE' });
    loadPortfolio();
    loadPortfolioAnalytics();
}

// Watchlist
async function loadWatchlist() {
    const data = await api('/api/watchlist');
    const container = document.getElementById('watchlistTable');
    
    if (data.watchlist && data.watchlist.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Symbol</th><th>Price</th><th>Change</th><th>Action</th></tr></thead>
                <tbody>
                    ${data.watchlist.map(w => `
                        <tr data-live-symbol="${w.symbol}">
                            <td><strong>${w.symbol.replace('.NS', '')}</strong></td>
                            <td data-live-price>${fmtPrice(w.price)}</td>
                            <td class="${(w.changePercent || 0) >= 0 ? 'positive' : 'negative'}" data-live-change-pct>${fmtPct(w.changePercent || 0)}</td>
                            <td>
                                <button class="btn-primary" onclick="selectStock('${w.symbol}'); showTab('chart')">View</button>
                                <button class="btn-danger" onclick="removeWatchlist('${w.symbol}')">Remove</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No stocks in watchlist</p>';
    }

    refreshLiveSubscriptions();
    applyLiveDomQuotes();
}

async function addToWatchlist() {
    const symbol = document.getElementById('watchlistSymbol').value;
    if (!symbol) return;
    
    await api('/api/watchlist', {
        method: 'POST',
        body: JSON.stringify({ symbol })
    });
    
    document.getElementById('watchlistSymbol').value = '';
    document.getElementById('watchlistSuggestions').innerHTML = '';
    loadWatchlist();
}

// Stock search for watchlist
let watchlistSearchTimeout = null;
async function searchStockForWatchlist(query) {
    const container = document.getElementById('watchlistSuggestions');
    if (!container) return;
    
    if (query.length < 1) {
        container.innerHTML = '';
        container.style.display = 'none';
        return;
    }
    
    clearTimeout(watchlistSearchTimeout);
    watchlistSearchTimeout = setTimeout(async () => {
        const data = await api(`/api/stocks/search?query=${query}`);
        if (data && data.length > 0) {
            container.innerHTML = data.map(s => `
                <div class="suggestion-item" onclick="selectWatchlistStock('${s.symbol}', '${s.name}')">
                    <strong>${s.name}</strong>
                    <span>${s.symbol}</span>
                </div>
            `).join('');
            container.style.display = 'block';
        } else {
            container.innerHTML = '<div class="suggestion-item">No results</div>';
            container.style.display = 'block';
        }
    }, 200);
}

function selectWatchlistStock(symbol, name) {
    document.getElementById('watchlistSymbol').value = symbol;
    document.getElementById('watchlistSuggestions').innerHTML = '';
    document.getElementById('watchlistSuggestions').style.display = 'none';
}

// Stock search for portfolio
let portfolioSearchTimeout = null;
async function searchStockForPortfolio(query) {
    const container = document.getElementById('portfolioSuggestions');
    if (!container) return;
    
    if (query.length < 1) {
        container.innerHTML = '';
        container.style.display = 'none';
        return;
    }
    
    clearTimeout(portfolioSearchTimeout);
    portfolioSearchTimeout = setTimeout(async () => {
        const data = await api(`/api/stocks/search?query=${query}`);
        if (data && data.length > 0) {
            container.innerHTML = data.map(s => `
                <div class="suggestion-item" onclick="selectPortfolioStock('${s.symbol}', '${s.name}')">
                    <strong>${s.name}</strong>
                    <span>${s.symbol}</span>
                </div>
            `).join('');
            container.style.display = 'block';
        } else {
            container.innerHTML = '<div class="suggestion-item">No results</div>';
            container.style.display = 'block';
        }
    }, 200);
}

function selectPortfolioStock(symbol, name) {
    document.getElementById('portfolioSymbol').value = symbol;
    document.getElementById('portfolioSuggestions').innerHTML = '';
    document.getElementById('portfolioSuggestions').style.display = 'none';
}

// Close suggestions when clicking outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.watchlist-form') && !e.target.closest('.portfolio-form')) {
        document.querySelectorAll('.search-suggestions').forEach(el => {
            el.innerHTML = '';
            el.style.display = 'none';
        });
    }
});

async function removeWatchlist(symbol) {
    await api(`/api/watchlist/${symbol}`, { method: 'DELETE' });
    loadWatchlist();
}

// Analysis Functions
async function loadMultiTimeframe() {
    const symbol = document.getElementById('mtfSymbol').value;
    if (!symbol) return;
    
    showLoading();
    const data = await api(`/api/analysis/multi-timeframe/${symbol}`);
    const container = document.getElementById('mtfResults');
    
    if (data.error) {
        container.innerHTML = `<p class="placeholder">${data.error}</p>`;
    } else {
        container.innerHTML = `
            <div class="overall-signal ${data.overallSignal?.toLowerCase() || 'neutral'}">${data.overallSignal || 'NEUTRAL'}</div>
            ${data.timeframes ? `
                <table>
                    <thead><tr><th>Timeframe</th><th>Price</th><th>Trend</th><th>RSI</th><th>MACD</th><th>SMA20</th><th>SMA50</th></tr></thead>
                    <tbody>
                        ${Object.entries(data.timeframes).map(([tf, d]) => `
                            <tr>
                                <td><strong>${tf.toUpperCase()}</strong></td>
                                <td>₹${d.price}</td>
                                <td class="${d.trend === 'BULLISH' ? 'positive' : d.trend === 'BEARISH' ? 'negative' : ''}">${d.trend}</td>
                                <td>${d.rsi || '-'}</td>
                                <td>${d.macd || '-'}</td>
                                <td>₹${d.sma20 || '-'}</td>
                                <td>₹${d.sma50 || '-'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            ` : ''}
        `;
    }
    hideLoading();
}

async function runCustomStrategy() {
    showLoading();
    const symbol = document.getElementById('customSymbol').value;
    const rsiBuy = parseFloat(document.getElementById('customRsiBuy').value);
    const rsiSell = parseFloat(document.getElementById('customRsiSell').value);
    
    const data = await api('/api/analysis/custom-strategy', {
        method: 'POST',
        body: JSON.stringify({
            symbol,
            strategy_name: 'Custom RSI Strategy',
            buy_conditions: { RSI: { op: '<', value: rsiBuy } },
            sell_conditions: { RSI: { op: '>', value: rsiSell } }
        })
    });
    
    const container = document.getElementById('customResults');
    
    if (data.error) {
        container.innerHTML = `<p class="placeholder">${data.error}</p>`;
    } else {
        container.innerHTML = `
            <div class="card">
                <div class="strategy-result mb-2">
                    <div class="result-row">
                        <span>Return</span>
                        <span class="${data.total_return >= 0 ? 'positive' : 'negative'}">${data.total_return}%</span>
                    </div>
                    <div class="result-row">
                        <span>Win Rate</span>
                        <span>${data.win_rate}%</span>
                    </div>
                    <div class="result-row">
                        <span>Trades</span>
                        <span>${data.total_trades}</span>
                    </div>
                </div>
                ${data.trades ? `
                    <table>
                        <thead><tr><th>Date</th><th>Type</th><th>Price</th><th>P&L</th></tr></thead>
                        <tbody>
                            ${data.trades.slice(-10).map(t => `
                                <tr>
                                    <td>${t.date}</td>
                                    <td><span class="badge ${t.type === 'BUY' ? 'positive' : 'negative'}">${t.type}</span></td>
                                    <td>₹${t.price}</td>
                                    <td class="${(t.pnl || 0) >= 0 ? 'positive' : 'negative'}">${t.pnl ? '₹' + t.pnl : '-'}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                ` : ''}
            </div>
        `;
    }
    hideLoading();
}

async function loadCorrelation() {
    const symbols = document.getElementById('correlationSymbols').value;
    showLoading();
    const data = await api(`/api/correlation?symbols=${symbols}`);
    const container = document.getElementById('correlationResults');
    
    if (data.error) {
        container.innerHTML = `<p class="placeholder">${data.error}</p>`;
    } else if (data.symbols) {
        const syms = data.symbols;
        let html = '<div class="card"><table class="correlation-table"><thead><tr><th></th>';
        syms.forEach(s => html += `<th>${s}</th>`);
        html += '</tr></thead><tbody>';
        
        syms.forEach(s1 => {
            html += `<tr><td><strong>${s1}</strong></td>`;
            syms.forEach(s2 => {
                const val = data.correlation[s1][s2];
                const cls = val > 0.5 ? 'positive' : val < -0.5 ? 'negative' : '';
                html += `<td class="${cls}">${val}</td>`;
            });
            html += '</tr>';
        });
        
        html += '</tbody></table></div>';
        container.innerHTML = html;
    }
    hideLoading();
}

async function loadBreadth() {
    showLoading();
    const data = await api('/api/breadth');
    const container = document.getElementById('breadthData');
    
    container.innerHTML = `
        <div class="breadth-grid">
            <div class="breadth-stat">
                <div class="label">A/D Ratio</div>
                <div class="value ${data.breadthSignal === 'BULLISH' ? 'positive' : data.breadthSignal === 'BEARISH' ? 'negative' : ''}">${data.adRatio}</div>
            </div>
            <div class="breadth-stat">
                <div class="label">Signal</div>
                <div class="value ${data.breadthSignal === 'BULLISH' ? 'positive' : data.breadthSignal === 'BEARISH' ? 'negative' : ''}">${data.breadthSignal}</div>
            </div>
            <div class="breadth-stat">
                <div class="label">Advancing</div>
                <div class="value positive">${data.advancing} (${data.percentAdvancing}%)</div>
            </div>
            <div class="breadth-stat">
                <div class="label">Declining</div>
                <div class="value negative">${data.declining} (${data.percentDeclining}%)</div>
            </div>
            <div class="breadth-stat">
                <div class="label">Above SMA20</div>
                <div class="value">${data.aboveSma20} (${data.aboveSma20Percent}%)</div>
            </div>
            <div class="breadth-stat">
                <div class="label">Above SMA50</div>
                <div class="value">${data.aboveSma50} (${data.aboveSma50Percent}%)</div>
            </div>
        </div>
    `;
    hideLoading();
}

async function loadEarnings() {
    showLoading();
    const data = await api('/api/fundamentals/earnings');
    const container = document.getElementById('earningsData');
    
    if (data.earnings && data.earnings.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Stock</th><th>Next Earnings</th></tr></thead>
                <tbody>
                    ${data.earnings.map(e => `
                        <tr>
                            <td><strong>${e.name}</strong></td>
                            <td>${e.date}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No earnings data available</p>';
    }
    hideLoading();
}

async function loadDividends() {
    showLoading();
    const data = await api('/api/fundamentals/dividends');
    const container = document.getElementById('dividendData');
    
    if (data.stocks && data.stocks.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Stock</th><th>Yield</th><th>Rate</th><th>Sector</th></tr></thead>
                <tbody>
                    ${data.stocks.map(d => `
                        <tr>
                            <td><strong>${d.name}</strong></td>
                            <td class="positive">${d.dividendYield}%</td>
                            <td>₹${d.dividendRate || '-'}</td>
                            <td>${d.sector}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No dividend data available</p>';
    }
    hideLoading();
}

// Tools
function calculatePosition() {
    const account = parseFloat(document.getElementById('accountSize').value);
    const risk = parseFloat(document.getElementById('riskPercent').value);
    const entry = parseFloat(document.getElementById('entryPrice').value);
    const sl = parseFloat(document.getElementById('stopLoss').value);
    
    if (!account || !risk || !entry || !sl) return showToast('Fill all fields', 'warning');
    
    const riskAmount = account * (risk / 100);
    const riskPerShare = Math.abs(entry - sl);
    const shares = Math.floor(riskAmount / riskPerShare);
    const totalCost = shares * entry;
    
    document.getElementById('positionResult').innerHTML = `
        <div class="strategy-result">
            <div class="result-row">
                <span>Risk Amount</span>
                <span>₹${riskAmount.toFixed(2)}</span>
            </div>
            <div class="result-row">
                <span>Risk per Share</span>
                <span>₹${riskPerShare.toFixed(2)}</span>
            </div>
            <div class="result-row">
                <span>Position Size</span>
                <span><strong>${shares} shares</strong></span>
            </div>
            <div class="result-row">
                <span>Total Investment</span>
                <span>₹${totalCost.toLocaleString()}</span>
            </div>
        </div>
    `;
}

async function calculateFibonacci() {
    const symbol = document.getElementById('fibSymbol').value;
    if (!symbol) return showToast('Enter symbol', 'warning');
    
    showLoading();
    const data = await api(`/api/tools/fibonacci/${symbol}`);
    const container = document.getElementById('fibResult');
    
    if (data.levels) {
        container.innerHTML = `
            <div class="strategy-result">
                <div class="result-row">
                    <span>52W High</span>
                    <span>₹${data.high}</span>
                </div>
                <div class="result-row">
                    <span>52W Low</span>
                    <span>₹${data.low}</span>
                </div>
                ${Object.entries(data.levels).map(([level, val]) => `
                    <div class="result-row">
                        <span>${level}</span>
                        <span>₹${val.toFixed(2)}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }
    hideLoading();
}

// Alerts
async function loadAlerts() {
    const data = await api('/api/alerts');
    const container = document.getElementById('alertsList');
    
    if (data.alerts && data.alerts.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Symbol</th><th>Type</th><th>Target</th><th>Status</th><th>Action</th></tr></thead>
                <tbody>
                    ${data.alerts.map(a => `
                        <tr>
                            <td><strong>${a.symbol}</strong></td>
                            <td>${a.alert_type}</td>
                            <td>${a.target_price || '-'}</td>
                            <td><span class="badge ${a.active ? 'positive' : ''}">${a.active ? 'Active' : 'Inactive'}</span></td>
                            <td><button class="btn-danger" onclick="deleteAlert(${a.id})">Delete</button></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No alerts set</p>';
    }
}

async function createAlert() {
    const symbol = document.getElementById('alertSymbol').value;
    const alertType = document.getElementById('alertType').value;
    const price = document.getElementById('alertPrice').value;
    
    if (!symbol) return showToast('Enter symbol', 'warning');
    
    await api('/api/alerts', {
        method: 'POST',
        body: JSON.stringify({ symbol, alert_type: alertType, target_price: price ? parseFloat(price) : null })
    });
    
    loadAlerts();
}

async function deleteAlert(id) {
    await api(`/api/alerts/${id}`, { method: 'DELETE' });
    loadAlerts();
}

// Export
function exportScreenerCSV() {
    window.open('/api/export/csv', '_blank');
}

function exportPortfolioCSV() {
    window.open('/api/export/portfolio/csv', '_blank');
}

// AI Analysis Functions
async function loadAiTab() {
    checkGeminiStatus();
    // NO auto-loading - user must click buttons explicitly to save API calls
}

// Gemini Settings
async function checkGeminiStatus() {
    const data = await api('/api/gemini/config');
    const statusEl = document.getElementById('geminiStatus');
    
    if (data.configured) {
        statusEl.textContent = 'Configured';
        statusEl.className = 'badge positive';
        document.getElementById('geminiApiKey').value = '';
        document.getElementById('geminiApiKey').placeholder = `Key: ${data.api_key_masked}`;
    } else {
        statusEl.textContent = 'Not Configured';
        statusEl.className = 'badge negative';
    }
}

async function saveGeminiKey() {
    const key = document.getElementById('geminiApiKey').value.trim();
    if (!key) return showToast('Enter an API key', 'warning');
    
    const data = await api('/api/gemini/config', {
        method: 'POST',
        body: JSON.stringify({ api_key: key })
    });
    
    if (data.status === 'configured') {
        checkGeminiStatus();
        showToast('API key saved! You can now use Gemini AI features.', 'success');
    }
}

// Gemini Analysis
async function runGeminiAnalysis() {
    const symbol = document.getElementById('aiSymbol').value;
    if (!symbol) return showToast('Enter a stock symbol', 'warning');
    
    const container = document.getElementById('aiAnalysisResult');
    container.innerHTML = '<p class="placeholder">Analyzing with Gemini AI... This may take 10-15 seconds.</p>';
    
    const data = await api('/api/gemini/analyze', {
        method: 'POST',
        body: JSON.stringify({ symbol })
    });
    
    if (data.error) {
        container.innerHTML = `<p class="placeholder" style="color:var(--red);">${data.error}</p>`;
        return;
    }
    
    container.innerHTML = `
        <div class="ai-analysis-card">
            <div class="ai-header">
                <h3>${data.name || symbol}</h3>
                <span class="recommendation-badge ${(data.recommendation || 'hold').toLowerCase()}">${data.recommendation || 'HOLD'}</span>
            </div>
            
            <div class="ai-grid">
                <div class="ai-section">
                    <h4>Trading Setup</h4>
                    <div class="ai-data">
                        <div class="data-row"><span>Confidence:</span><span>${data.confidence || 'Medium'}</span></div>
                        <div class="data-row"><span>Target Price:</span><span class="positive">${data.target_price || 'N/A'}</span></div>
                        <div class="data-row"><span>Stop Loss:</span><span class="negative">${data.stop_loss || 'N/A'}</span></div>
                        <div class="data-row"><span>Risk Level:</span><span>${data.risk_level || 'Medium'}</span></div>
                        <div class="data-row"><span>Timeframe:</span><span>${data.timeframe || 'Medium'}</span></div>
                    </div>
                </div>
                
                <div class="ai-section">
                    <h4>Key Reasons</h4>
                    <div class="ai-data">
                        ${(data.reasons || []).map(r => `<div class="data-row">• ${r}</div>`).join('')}
                    </div>
                </div>
            </div>
            
            ${data.risks ? `
                <div class="ai-section mt-2">
                    <h4>Key Risks</h4>
                    <div class="ai-data">
                        ${data.risks.map(r => `<div class="data-row" style="color:var(--red);">⚠ ${r}</div>`).join('')}
                    </div>
                </div>
            ` : ''}
            
            ${data.news_impact ? `
                <div class="ai-section mt-2">
                    <h4>News Impact</h4>
                    <p style="font-size:13px; color:var(--text-secondary);">${data.news_impact}</p>
                </div>
            ` : ''}
            
            <div class="ai-reasoning mt-2">
                <h4>Summary</h4>
                <p>${data.summary || 'No summary available'}</p>
            </div>
            
            <div style="font-size:10px; color:var(--text-muted); margin-top:12px; text-align:right;">
                Powered by ${data.powered_by || 'AI'} • For educational purposes only
            </div>
        </div>
    `;
}

// AI Chat
async function sendChat() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message) return;
    
    const chatMessages = document.getElementById('chatMessages');
    
    chatMessages.innerHTML += `
        <div class="chat-message user">
            <div class="message-content">${message}</div>
        </div>
    `;
    
    input.value = '';
    
    chatMessages.innerHTML += `
        <div class="chat-message ai loading" id="chatLoading">
            <div class="message-content">Thinking...</div>
        </div>
    `;
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    const data = await api('/api/gemini/chat', {
        method: 'POST',
        body: JSON.stringify({ message })
    });
    
    const loadingEl = document.getElementById('chatLoading');
    if (loadingEl) loadingEl.remove();
    
    if (data.error) {
        chatMessages.innerHTML += `
            <div class="chat-message ai error">
                <div class="message-content">${data.error}</div>
            </div>
        `;
    } else {
        chatMessages.innerHTML += `
            <div class="chat-message ai">
                <div class="message-content">${(data.response || '').replace(/\n/g, '<br>')}</div>
            </div>
        `;
    }
    
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function loadMarketMood() {
    const container = document.getElementById('marketMood');
    container.innerHTML = '<p class="placeholder">Loading market mood...</p>';
    
    const data = await api('/api/ai/mood');
    
    if (data.error) {
        container.innerHTML = `<p class="placeholder">${data.error}</p>`;
        return;
    }
    
    container.innerHTML = `
        <div class="mood-display">
            <div class="mood-indicator ${data.mood.toLowerCase()}">
                <span class="mood-label">Market Mood</span>
                <span class="mood-value">${data.mood}</span>
            </div>
            <div class="mood-stats">
                <div class="mood-stat">
                    <span class="label">Bullish Stocks</span>
                    <span class="value positive">${data.trending_bullish}</span>
                </div>
                <div class="mood-stat">
                    <span class="label">Bearish Stocks</span>
                    <span class="value negative">${data.trending_bearish}</span>
                </div>
            </div>
        </div>
        ${data.trending_stocks ? `
            <div class="mt-2">
                <h4 style="font-size:13px; color:var(--text-secondary); margin-bottom:8px;">Top Trending</h4>
                <div class="trending-list">
                    ${data.trending_stocks.map(s => `
                        <div class="trending-item" onclick="selectStock('${s.symbol}'); showTab('chart')" style="cursor:pointer">
                            <strong>${s.name}</strong>
                            <span class="badge ${s.sentiment === 'BULLISH' ? 'positive' : s.sentiment === 'BEARISH' ? 'negative' : ''}">${s.sentiment}</span>
                            <span style="color:var(--text-muted); font-size:12px;">${s.news_count} news</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : ''}
    `;
}

async function loadTrendingStocks() {
    const container = document.getElementById('trendingStocks');
    container.innerHTML = '<p class="placeholder">Loading trending stocks from news...</p>';
    
    const data = await api('/api/ai/trending');
    
    if (data.error || !data.trending) {
        container.innerHTML = '<p class="placeholder">No trending data available</p>';
        return;
    }
    
    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Stock</th>
                    <th>News Count</th>
                    <th>Sentiment</th>
                    <th>Score</th>
                    <th>Top Headline</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                ${data.trending.map(s => `
                    <tr>
                        <td><strong>${s.name}</strong></td>
                        <td>${s.news_count}</td>
                        <td><span class="badge ${s.sentiment === 'BULLISH' ? 'positive' : s.sentiment === 'BEARISH' ? 'negative' : ''}">${s.sentiment}</span></td>
                        <td>${s.sentiment_score}</td>
                        <td style="max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; color:var(--text-secondary);">${s.headlines[0] || '-'}</td>
                        <td><button class="btn-primary" onclick="document.getElementById('aiSymbol').value='${s.symbol}'; runAiAnalysis()">Analyze</button></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

async function runAiAnalysis() {
    const symbol = document.getElementById('aiSymbol').value;
    if (!symbol) return showToast('Enter a stock symbol', 'warning');
    
    const container = document.getElementById('aiAnalysisResult');
    container.innerHTML = '<p class="placeholder">Running AI analysis...</p>';
    
    const data = await api(`/api/ai/analyze/${symbol}`);
    
    if (data.error) {
        container.innerHTML = `<p class="placeholder">${data.error}</p>`;
        return;
    }
    
    container.innerHTML = `
        <div class="ai-analysis-card">
            <div class="ai-header">
                <h3>${data.name}</h3>
                <span class="recommendation-badge ${data.recommendation.replace(' ', '_').toLowerCase()}">${data.recommendation}</span>
            </div>
            
            <div class="ai-score">
                <div class="score-circle">
                    <span class="score-value">${data.combined_score}</span>
                    <span class="score-label">AI Score</span>
                </div>
            </div>
            
            <div class="ai-grid">
                <div class="ai-section">
                    <h4>Technical Analysis</h4>
                    ${data.technical ? `
                        <div class="ai-data">
                            <div class="data-row"><span>Price:</span><span>₹${data.technical.price}</span></div>
                            <div class="data-row"><span>RSI:</span><span class="${data.technical.rsi < 30 ? 'positive' : data.technical.rsi > 70 ? 'negative' : ''}">${data.technical.rsi || '-'}</span></div>
                            <div class="data-row"><span>MACD:</span><span>${data.technical.macd || '-'}</span></div>
                            <div class="data-row"><span>SMA20:</span><span>₹${data.technical.sma20 || '-'}</span></div>
                            <div class="data-row"><span>SMA50:</span><span>₹${data.technical.sma50 || '-'}</span></div>
                            <div class="data-row"><span>Trend:</span><span class="${data.technical.trend === 'BULLISH' ? 'positive' : 'negative'}">${data.technical.trend}</span></div>
                        </div>
                    ` : '<p>No technical data</p>'}
                </div>
                
                <div class="ai-section">
                    <h4>News Sentiment</h4>
                    ${data.news_sentiment ? `
                        <div class="ai-data">
                            <div class="data-row"><span>Avg Score:</span><span>${data.news_sentiment.average_score}</span></div>
                            <div class="data-row"><span>Label:</span><span class="${data.news_sentiment.label === 'BULLISH' ? 'positive' : data.news_sentiment.label === 'BEARISH' ? 'negative' : ''}">${data.news_sentiment.label}</span></div>
                            <div class="data-row"><span>Positive:</span><span class="positive">${data.news_sentiment.positive_count}</span></div>
                            <div class="data-row"><span>Negative:</span><span class="negative">${data.news_sentiment.negative_count}</span></div>
                            <div class="data-row"><span>News Count:</span><span>${data.news_count}</span></div>
                        </div>
                    ` : '<p>No sentiment data</p>'}
                </div>
            </div>
            
            ${data.top_headlines && data.top_headlines.length > 0 ? `
                <div class="ai-headlines mt-2">
                    <h4>Top Headlines</h4>
                    ${data.top_headlines.map(h => `<div class="headline-item">• ${h}</div>`).join('')}
                </div>
            ` : ''}
            
            <div class="ai-reasoning mt-2">
                <h4>AI Reasoning</h4>
                <p><strong>News:</strong> ${data.reasoning?.news || '-'}</p>
                <p><strong>Technical:</strong> ${data.reasoning?.technical || '-'}</p>
            </div>
        </div>
    `;
}

async function runSentimentScan() {
    const symbol = document.getElementById('sentimentSymbol').value;
    if (!symbol) return showToast('Enter a stock symbol', 'warning');
    
    const container = document.getElementById('sentimentResult');
    container.innerHTML = '<p class="placeholder">Scanning news sentiment...</p>';
    
    const data = await api(`/api/ai/sentiment/${symbol}`);
    
    if (data.error) {
        container.innerHTML = `<p class="placeholder">${data.error}</p>`;
        return;
    }
    
    container.innerHTML = `
        <div class="sentiment-card">
            <div class="sentiment-header">
                <h3>${data.name}</h3>
                <span class="recommendation-badge ${data.recommendation.toLowerCase()}">${data.recommendation}</span>
            </div>
            
            ${data.sentiment ? `
                <div class="sentiment-summary">
                    <div class="sentiment-stat">
                        <span class="label">Overall Sentiment</span>
                        <span class="value ${data.sentiment.label === 'BULLISH' ? 'positive' : data.sentiment.label === 'BEARISH' ? 'negative' : ''}">${data.sentiment.label}</span>
                    </div>
                    <div class="sentiment-stat">
                        <span class="label">Average Score</span>
                        <span class="value">${data.sentiment.average_score}</span>
                    </div>
                    <div class="sentiment-stat">
                        <span class="label">Positive News</span>
                        <span class="value positive">${data.sentiment.positive_count}</span>
                    </div>
                    <div class="sentiment-stat">
                        <span class="label">Negative News</span>
                        <span class="value negative">${data.sentiment.negative_count}</span>
                    </div>
                </div>
            ` : '<p>No sentiment data available</p>'}
            
            ${data.news && data.news.length > 0 ? `
                <div class="news-sentiment-list mt-2">
                    <h4 style="font-size:13px; margin-bottom:8px;">News with Sentiment</h4>
                    ${data.news.map(n => `
                        <div class="news-sentiment-item">
                            <div class="news-title">${n.title}</div>
                            <div class="news-meta">
                                <span class="badge ${n.sentiment === 'BULLISH' ? 'positive' : n.sentiment === 'BEARISH' ? 'negative' : ''}" style="font-size:10px;">${n.sentiment}</span>
                                <span style="color:var(--text-muted); font-size:11px;">${n.publisher}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
            
            <div class="ai-reasoning mt-2">
                <p><strong>Reasoning:</strong> ${data.reasoning}</p>
            </div>
        </div>
    `;
}

// Live Updates - now driven by WebSocket instead of REST polling
function startLiveUpdates() {
    if (liveInterval) clearInterval(liveInterval);
    // WebSocket handles live prices; just ensure connection is active
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        connectWebSocket();
    }
    // Subscribe to the current symbol for live price updates
    if (currentSymbol) {
        subscribeToChartSymbol(currentSymbol);
    }
}

// Dashboard Gainers/Losers real-time refresh
// No longer polling every 60s via REST — the WebSocket liveQuoteCache
// pushes updates every ~3s, and applyLiveDomQuotes() reads from it.
function startAutoRefreshGainersLosers() {
    // Ensure the WS socket is connected and subscribed so that
    // liveQuoteCache gets populated with top-movers symbols.
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        connectWebSocket();
    }
    // No setInterval needed; WebSocket ticks every ~3s will
    // refresh the DOM quotes via the existing applyLiveDomQuotes() path.
    // The old 60s interval is removed — gainers/losers now update live
    // automatically through the shared liveQuoteCache.
}

// Keyboard Shortcuts
document.addEventListener('keydown', (e) => {
    // '/' focuses the search box
    if (e.key === '/' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'SELECT' && e.target.tagName !== 'TEXTAREA') {
        e.preventDefault();
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.focus();
            searchInput.value = '';
        }
        return;
    }
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
    
    switch(e.key) {
        case '1': showTab('dashboard'); break;
        case '2': showTab('market'); break;
        case '3': showTab('screener'); break;
        case '4': showTab('signals'); break;
        case '5': showTab('sector'); break;
        case '6': showTab('compare'); break;
        case '7': showTab('backtest'); break;
        case '8': showTab('news'); break;
        case '9': showTab('portfolio'); break;
        case '0': showTab('watchlist'); break;
        case 'r': case 'R': loadChart(); break;
        case '/': e.preventDefault(); document.getElementById('searchInput').focus(); break;
        case 'Escape':
            document.getElementById('searchResults').classList.remove('active');
            document.getElementById('searchInput').blur();
            break;
    }
});

// Close search on outside click
document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-box')) {
        document.getElementById('searchResults').classList.remove('active');
    }
});

// Heatmap
async function loadHeatmap() {
    const container = document.getElementById('heatmapContainer');
    container.innerHTML = '<p class="placeholder">Loading heatmap data...</p>';
    
    const data = await api('/api/advanced/heatmap');
    
    if (data.error || !data.sectors) {
        container.innerHTML = '<p class="placeholder">No heatmap data available</p>';
        return;
    }
    
    container.innerHTML = `
        <div class="heatmap-grid">
            ${data.sectors.map(sector => `
                <div class="heatmap-sector">
                    <div class="sector-header ${sector.avgChange >= 0 ? 'positive' : 'negative'}">
                        <strong>${sector.name}</strong>
                        <span>${sector.avgChange >= 0 ? '+' : ''}${sector.avgChange}%</span>
                    </div>
                    <div class="sector-stocks">
                        ${sector.stocks.map(stock => `
                            <div class="heatmap-stock ${stock.change >= 0 ? 'positive' : 'negative'}" 
                                 onclick="selectStock('${stock.symbol}'); showTab('chart')"
                                 style="opacity: ${Math.min(Math.abs(stock.change) / 3 + 0.4, 1)}">
                                <span class="stock-name">${stock.name}</span>
                                <span class="stock-change">${fmtChg(stock.change)}%</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

// Global Markets
async function loadGlobalMarkets() {
    const container = document.getElementById('globalMarketsContainer');
    container.innerHTML = '<p class="placeholder">Loading global markets...</p>';
    
    const data = await api('/api/advanced/global');
    
    if (data.error || !data.markets) {
        container.innerHTML = '<p class="placeholder">No global market data</p>';
        return;
    }
    
    const usMarkets = data.markets.filter(m => m.country === 'US');
    const asianMarkets = data.markets.filter(m => ['Japan', 'Hong Kong', 'China'].includes(m.country));
    const europeanMarkets = data.markets.filter(m => m.country === 'UK' || m.country === 'Germany');
    const indianMarkets = data.markets.filter(m => m.country === 'India');
    const commodities = data.markets.filter(m => m.country === 'Commodity');
    const currencies = data.markets.filter(m => m.country === 'Currency');
    
    function renderMarketList(markets) {
        return markets.map(m => `
            <div class="global-market-item">
                <span class="market-name">${m.name}</span>
                <span class="market-price">${m.country === 'Currency' || m.country === 'Commodity' ? m.price : '₹' + m.price.toLocaleString()}</span>
                <span class="market-change ${m.changePercent >= 0 ? 'positive' : 'negative'}">
                    ${fmtChg(m.changePercent)}%
                </span>
            </div>
        `).join('');
    }
    
    container.innerHTML = `
        <div class="global-markets-grid">
            <div class="market-section">
                <h4>🇺🇸 US Markets</h4>
                ${renderMarketList(usMarkets)}
            </div>
            <div class="market-section">
                <h4>🇮🇳 Indian Markets</h4>
                ${renderMarketList(indianMarkets)}
            </div>
            <div class="market-section">
                <h4>🌏 Asian Markets</h4>
                ${renderMarketList(asianMarkets)}
            </div>
            <div class="market-section">
                <h4>🇪🇺 European Markets</h4>
                ${renderMarketList(europeanMarkets)}
            </div>
            <div class="market-section">
                <h4>💰 Commodities</h4>
                ${renderMarketList(commodities)}
            </div>
            <div class="market-section">
                <h4>💱 Currencies</h4>
                ${renderMarketList(currencies)}
            </div>
        </div>
    `;
}

// Telegram
async function saveTelegramConfig() {
    const botToken = document.getElementById('telegramBotToken').value;
    const chatId = document.getElementById('telegramChatId').value;
    
    if (!botToken || !chatId) return showToast('Fill both fields', 'warning');
    
    const data = await api('/api/advanced/telegram/config', {
        method: 'POST',
        body: JSON.stringify({ bot_token: botToken, chat_id: chatId })
    });
    
    document.getElementById('telegramStatus').innerHTML = '<span class="positive">✓ Config saved</span>';
}

async function testTelegram() {
    const data = await api('/api/advanced/telegram/test', { method: 'POST' });
    
    if (data.error) {
        document.getElementById('telegramStatus').innerHTML = `<span class="negative">✗ ${data.error}</span>`;
    } else {
        document.getElementById('telegramStatus').innerHTML = '<span class="positive">✓ Test message sent</span>';
    }
}

// Promoter Data
async function loadPromoterData() {
    const symbol = document.getElementById('promoterSymbol').value;
    if (!symbol) return showToast('Enter a stock symbol', 'warning');
    
    const container = document.getElementById('promoterResult');
    container.innerHTML = '<p class="placeholder">Loading promoter data...</p>';
    
    const data = await api(`/api/advanced/promoter/${symbol}`);
    
    if (data.error) {
        container.innerHTML = `<p class="placeholder">${data.error}</p>`;
        return;
    }
    
    container.innerHTML = `
        <div class="promoter-data">
            <div class="data-row"><span>Promoter Holding:</span><span>${data.promoterHolding || 'N/A'}%</span></div>
            <div class="data-row"><span>Institutional Holding:</span><span>${data.institutionHolding || 'N/A'}%</span></div>
            <div class="data-row"><span>Mutual Fund Holding:</span><span>${data.mutualFundHolding || 'N/A'}%</span></div>
            <div class="data-row"><span>Short Ratio:</span><span>${data.shortRatio || 'N/A'}</span></div>
            <div class="data-row"><span>Short % of Float:</span><span>${data.shortPercentOfFloat ? (data.shortPercentOfFloat * 100).toFixed(2) + '%' : 'N/A'}</span></div>
        </div>
        <p style="font-size:11px; color:var(--text-muted); margin-top:8px;">${data.note || ''}</p>
    `;
}

// IPO
async function loadIPOs() {
    const container = document.getElementById('ipoContainer');
    container.innerHTML = '<p class="placeholder">Loading IPOs...</p>';
    
    const data = await api('/api/more/ipo');
    
    if (data.error || !data.ipos) {
        container.innerHTML = '<p class="placeholder">No IPO data available</p>';
        return;
    }
    
    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Company</th>
                    <th>Price Band</th>
                    <th>Date</th>
                    <th>GMP</th>
                    <th>GMP %</th>
                    <th>Est. Listing</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                ${data.ipos.map(ipo => `
                    <tr>
                        <td><strong>${ipo.name}</strong></td>
                        <td>${ipo.price_band}</td>
                        <td>${ipo.date}</td>
                        <td class="${ipo.gmp && ipo.gmp !== '-' ? 'positive' : ''}">${ipo.gmp}</td>
                        <td class="${ipo.gmp_pct && ipo.gmp_pct !== '-' ? 'positive' : ''}">${ipo.gmp_pct}</td>
                        <td>${ipo.est_listing}</td>
                        <td><span class="badge ${ipo.type === 'Upcoming' ? 'positive' : ipo.type === 'Open' ? '' : 'neutral'}">${ipo.type}</span></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
        ${data.ipos[0]?.last_updated ? `<p class="placeholder" style="margin-top:8px">Last updated: ${data.ipos[0].last_updated}</p>` : ''}
    `;
}

// Market Status
async function loadMarketStatus() {
    const container = document.getElementById('marketStatus');
    const data = await api('/api/more/market-status');
    
    const statusClass = data.status === 'OPEN' ? 'positive' : data.status === 'PRE_MARKET' ? '' : 'negative';
    
    container.innerHTML = `
        <div class="market-status-card">
            <div class="status-indicator ${statusClass}">
                <span class="status-dot"></span>
                <span class="status-text">${data.status}</span>
            </div>
            <div class="status-details">
                <span>${data.message}</span>
                <span class="status-time">${data.currentTime}</span>
            </div>
        </div>
    `;
}

// Financials
async function loadFinancials() {
    const symbol = document.getElementById('financialSymbol').value;
    if (!symbol) return showToast('Enter a stock symbol', 'warning');
    
    const container = document.getElementById('financialsData');
    container.innerHTML = '<p class="placeholder">Loading financials...</p>';
    
    const data = await api(`/api/more/financials/${symbol}`);
    
    if (data.error) {
        container.innerHTML = `<p class="placeholder">${data.error}</p>`;
        return;
    }
    
    function formatNumber(num) {
        if (!num) return 'N/A';
        if (Math.abs(num) >= 1e12) return '₹' + (num / 1e12).toFixed(2) + 'T';
        if (Math.abs(num) >= 1e9) return '₹' + (num / 1e9).toFixed(2) + 'B';
        if (Math.abs(num) >= 1e6) return '₹' + (num / 1e6).toFixed(2) + 'M';
        return '₹' + num.toFixed(2);
    }
    
    function formatPercent(num) {
        if (!num) return 'N/A';
        return (num * 100).toFixed(2) + '%';
    }
    
    container.innerHTML = `
        <div class="financials-grid">
            <div class="financial-section">
                <h4>Valuation</h4>
                <div class="data-row"><span>Market Cap:</span><span>${formatNumber(data.marketCap)}</span></div>
                <div class="data-row"><span>P/E (TTM):</span><span>${data.trailingPE?.toFixed(2) || 'N/A'}</span></div>
                <div class="data-row"><span>P/E (Forward):</span><span>${data.forwardPE?.toFixed(2) || 'N/A'}</span></div>
                <div class="data-row"><span>PEG Ratio:</span><span>${data.pegRatio?.toFixed(2) || 'N/A'}</span></div>
                <div class="data-row"><span>P/B:</span><span>${data.priceToBook?.toFixed(2) || 'N/A'}</span></div>
                <div class="data-row"><span>P/S:</span><span>${data.priceToSales?.toFixed(2) || 'N/A'}</span></div>
            </div>
            
            <div class="financial-section">
                <h4>Profitability</h4>
                <div class="data-row"><span>Profit Margin:</span><span>${formatPercent(data.profitMargins)}</span></div>
                <div class="data-row"><span>ROE:</span><span>${formatPercent(data.returnOnEquity)}</span></div>
                <div class="data-row"><span>ROA:</span><span>${formatPercent(data.returnOnAssets)}</span></div>
                <div class="data-row"><span>Revenue Growth:</span><span>${formatPercent(data.revenueGrowth)}</span></div>
                <div class="data-row"><span>Earnings Growth:</span><span>${formatPercent(data.earningsGrowth)}</span></div>
            </div>
            
            <div class="financial-section">
                <h4>Financial Health</h4>
                <div class="data-row"><span>Debt/Equity:</span><span>${data.debtToEquity?.toFixed(2) || 'N/A'}</span></div>
                <div class="data-row"><span>Current Ratio:</span><span>${data.currentRatio?.toFixed(2) || 'N/A'}</span></div>
                <div class="data-row"><span>Quick Ratio:</span><span>${data.quickRatio?.toFixed(2) || 'N/A'}</span></div>
                <div class="data-row"><span>Free Cashflow:</span><span>${formatNumber(data.freeCashflow)}</span></div>
                <div class="data-row"><span>Total Cash:</span><span>${formatNumber(data.totalCash)}</span></div>
                <div class="data-row"><span>Total Debt:</span><span>${formatNumber(data.totalDebt)}</span></div>
            </div>
            
            <div class="financial-section">
                <h4>Per Share</h4>
                <div class="data-row"><span>EPS:</span><span>₹${data.earningsPerShare?.toFixed(2) || 'N/A'}</span></div>
                <div class="data-row"><span>Book Value:</span><span>₹${data.bookValue?.toFixed(2) || 'N/A'}</span></div>
                <div class="data-row"><span>Revenue/Share:</span><span>₹${data.revenuePerShare?.toFixed(2) || 'N/A'}</span></div>
                <div class="data-row"><span>Dividend Yield:</span><span>${formatPercent(data.dividendYield)}</span></div>
            </div>
        </div>
    `;
}

// Dividend History
async function loadDividendHistory() {
    const symbol = document.getElementById('divHistorySymbol').value;
    if (!symbol) return showToast('Enter a stock symbol', 'warning');
    
    const container = document.getElementById('dividendHistory');
    container.innerHTML = '<p class="placeholder">Loading dividend history...</p>';
    
    const data = await api(`/api/more/dividends/${symbol}`);
    
    if (data.error) {
        container.innerHTML = `<p class="placeholder">${data.error}</p>`;
        return;
    }
    
    container.innerHTML = `
        <div class="dividend-info">
            <div class="data-row"><span>Dividend Yield:</span><span>${data.dividendYield ? (data.dividendYield * 100).toFixed(2) + '%' : 'N/A'}</span></div>
            <div class="data-row"><span>Dividend Rate:</span><span>₹${data.dividendRate || 'N/A'}</span></div>
            <div class="data-row"><span>Payout Ratio:</span><span>${data.payoutRatio ? (data.payoutRatio * 100).toFixed(2) + '%' : 'N/A'}</span></div>
        </div>
        ${data.history && data.history.length > 0 ? `
            <table class="mt-2">
                <thead><tr><th>Date</th><th>Dividend</th></tr></thead>
                <tbody>
                    ${data.history.map(d => `
                        <tr>
                            <td>${d.date}</td>
                            <td class="positive">₹${d.dividend}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        ` : '<p class="placeholder mt-2">No dividend history</p>'}
    `;
}

// Tax Calculator
async function calculateTax() {
    const sellPrice = parseFloat(document.getElementById('taxSellPrice').value);
    const buyPrice = parseFloat(document.getElementById('taxBuyPrice').value);
    const qty = parseInt(document.getElementById('taxQty').value);
    const holding = document.getElementById('taxHolding').value;
    
    if (!sellPrice || !buyPrice) return showToast('Enter prices', 'warning');
    
    const data = await api('/api/more/tax-calculator', {
        method: 'POST',
        body: JSON.stringify({ selling_price: sellPrice, buying_price: buyPrice, quantity: qty, holding_period: holding })
    });
    
    const container = document.getElementById('taxResult');
    container.innerHTML = `
        <div class="calculator-result">
            <div class="result-row"><span>Total Sale:</span><span>₹${data.total_sale.toLocaleString()}</span></div>
            <div class="result-row"><span>Total Cost:</span><span>₹${data.total_cost.toLocaleString()}</span></div>
            <div class="result-row"><span>Profit:</span><span class="${data.profit >= 0 ? 'positive' : 'negative'}">₹${data.profit.toLocaleString()}</span></div>
            <div class="result-row"><span>Tax Rate:</span><span>${data.tax_rate}</span></div>
            <div class="result-row"><span>Tax:</span><span class="negative">₹${data.tax.toLocaleString()}</span></div>
            <div class="result-row highlight"><span>Net Profit:</span><span class="${data.net_profit >= 0 ? 'positive' : 'negative'}">₹${data.net_profit.toLocaleString()}</span></div>
            <div class="result-note">${data.note}</div>
        </div>
    `;
}

// Economic Calendar
async function loadEconomicCalendar() {
    const container = document.getElementById('economicCalendar');
    container.innerHTML = '<p class="placeholder">Loading calendar...</p>';
    
    const data = await api('/api/more/calendar');
    
    if (data.error || !data.events) {
        container.innerHTML = '<p class="placeholder">No events data</p>';
        return;
    }
    
    container.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Event</th>
                    <th>Importance</th>
                    <th>Expected</th>
                </tr>
            </thead>
            <tbody>
                ${data.events.map(e => `
                    <tr>
                        <td>${e.date}</td>
                        <td><strong>${e.event}</strong></td>
                        <td><span class="badge ${e.importance === 'High' ? 'negative' : ''}">${e.importance}</span></td>
                        <td>${e.expected}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// Features Tab
async function loadFeaturesTab() {
    loadAllNotes();
}

// Theme Toggle
let isDarkTheme = true;
function toggleTheme() {
    isDarkTheme = !isDarkTheme;
    document.body.classList.toggle('light-theme', !isDarkTheme);
    document.getElementById('themeStatus').textContent = `Current: ${isDarkTheme ? 'Dark' : 'Light'}`;
    localStorage.setItem('theme', isDarkTheme ? 'dark' : 'light');
}

// Stock Notes
async function addStockNote() {
    const symbol = document.getElementById('noteSymbol').value;
    const note = document.getElementById('noteText').value;
    
    if (!symbol || !note) return showToast('Fill both fields', 'warning');
    
    await api('/api/features/notes', {
        method: 'POST',
        body: JSON.stringify({ symbol, note })
    });
    
    document.getElementById('noteText').value = '';
    loadAllNotes();
}

async function loadAllNotes() {
    const data = await api('/api/features/notes');
    const container = document.getElementById('notesList');
    
    if (!data.notes || data.notes.length === 0) {
        container.innerHTML = '<p class="placeholder">No notes yet</p>';
        return;
    }
    
    container.innerHTML = `
        <table>
            <thead><tr><th>Stock</th><th>Note</th><th>Date</th><th>Action</th></tr></thead>
            <tbody>
                ${data.notes.slice(0, 20).map(n => `
                    <tr>
                        <td><strong>${n.symbol.replace('.NS', '')}</strong></td>
                        <td>${n.note}</td>
                        <td style="font-size:11px; color:var(--text-muted);">${n.created_at}</td>
                        <td><button class="btn-danger" onclick="deleteNote('${n.symbol}', ${n.id})">Delete</button></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

async function deleteNote(symbol, noteId) {
    await api(`/api/features/notes/${symbol}/${noteId}`, { method: 'DELETE' });
    loadAllNotes();
}

// Earnings Calendar
async function loadEarningsCalendar() {
    const container = document.getElementById('earningsCalendar');
    container.innerHTML = '<p class="placeholder">Loading...</p>';
    
    const data = await api('/api/features/earnings');
    
    if (data.error || !data.earnings) {
        container.innerHTML = '<p class="placeholder">No earnings data</p>';
        return;
    }
    
    container.innerHTML = `
        <table>
            <thead><tr><th>Company</th><th>Date</th><th>Est. Revenue</th><th>Status</th></tr></thead>
            <tbody>
                ${data.earnings.map(e => `
                    <tr>
                        <td><strong>${e.company}</strong></td>
                        <td>${e.date}</td>
                        <td>${e['est Revenue']}</td>
                        <td><span class="badge positive">${e.status}</span></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// Multi-Chart
let multiChart = null;
async function loadMultiChart() {
    const symbols = document.getElementById('multiChartSymbols').value;
    if (!symbols) return showToast('Enter symbols', 'warning');
    
    const container = document.getElementById('multiChartContainer');
    container.innerHTML = '<p class="placeholder">Loading chart data...</p>';
    
    const data = await api(`/api/features/multi-chart?symbols=${symbols}`);
    
    if (data.error || !data.data) {
        container.innerHTML = '<p class="placeholder">No chart data</p>';
        return;
    }
    
    container.innerHTML = '';
    
    multiChart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 300,
        layout: { background: { color: getChartBg() }, textColor: '#8888a0' },
        grid: { vertLines: { color: 'rgba(255,255,255,0.04)' }, horzLines: { color: 'rgba(255,255,255,0.04)' } },
        timeScale: { borderColor: 'rgba(255,255,255,0.06)' }
    });
    
    const colors = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];
    let colorIndex = 0;
    
    for (const [symbol, points] of Object.entries(data.data)) {
        const lineSeries = multiChart.addLineSeries({
            color: colors[colorIndex % colors.length],
            lineWidth: 2,
            title: symbol
        });
        
        lineSeries.setData(points.map(p => ({ time: p.date, value: p.value })));
        colorIndex++;
    }
    
    multiChart.timeScale().fitContent();
}

// Gold & Silver
let goldChart = null;

async function loadGoldPrices() {
    const container = document.getElementById('goldPrices');
    container.innerHTML = '<p class="placeholder">Loading prices...</p>';
    
    const data = await api('/api/gold/prices');
    
    if (data.error || data.available === false) {
        container.innerHTML = `<p class="placeholder">${data.error || 'Spot gold and silver prices are not available with the current data provider.'}</p>`;
        return;
    }
    
    container.innerHTML = `
        <div class="gold-prices-grid">
            <div class="gold-price-card ${data.gold.changePercent >= 0 ? 'positive' : 'negative'}">
                <div class="price-header">
                    <span class="commodity-name">🥇 Gold</span>
                    <span class="commodity-symbol">${data.gold.name}</span>
                </div>
                <div class="price-value">$${data.gold.price}</div>
                <div class="price-change">${data.gold.changePercent >= 0 ? '+' : ''}${data.gold.changePercent}%</div>
                <div class="price-range">
                    <span>52W Low: $${data.gold.low52w}</span>
                    <span>52W High: $${data.gold.high52w}</span>
                </div>
            </div>
            
            <div class="gold-price-card ${data.silver.changePercent >= 0 ? 'positive' : 'negative'}">
                <div class="price-header">
                    <span class="commodity-name">🥈 Silver</span>
                    <span class="commodity-symbol">${data.silver.name}</span>
                </div>
                <div class="price-value">$${data.silver.price}</div>
                <div class="price-change">${data.silver.changePercent >= 0 ? '+' : ''}${data.silver.changePercent}%</div>
                <div class="price-range">
                    <span>52W Low: $${data.silver.low52w}</span>
                    <span>52W High: $${data.silver.high52w}</span>
                </div>
            </div>
        </div>
    `;
    
    // Render gold chart
    if (data.gold.chartData && data.gold.chartData.length > 0) {
        renderGoldChart(data.gold.chartData);
    }
}

function renderGoldChart(chartData) {
    const container = document.getElementById('goldChart');
    container.innerHTML = '';
    
    goldChart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 300,
        layout: { background: { color: getChartBg() }, textColor: '#8888a0' },
        grid: { vertLines: { color: 'rgba(255,255,255,0.04)' }, horzLines: { color: 'rgba(255,255,255,0.04)' } },
        timeScale: { borderColor: 'rgba(255,255,255,0.06)' }
    });
    
    const lineSeries = goldChart.addLineSeries({
        color: '#f59e0b',
        lineWidth: 2
    });
    
    lineSeries.setData(chartData.map(p => ({ time: p.date, value: p.price })));
    goldChart.timeScale().fitContent();
}

async function loadGoldNiftyRatio() {
    const container = document.getElementById('goldNiftyRatio');
    container.innerHTML = '<p class="placeholder">Loading comparison...</p>';
    
    const data = await api('/api/gold/nifty-ratio');
    
    if (data.error) {
        container.innerHTML = `<p class="placeholder">${data.error}</p>`;
        return;
    }
    
    container.innerHTML = `
        <div class="comparison-result">
            <div class="data-row"><span>Gold 1Y Return:</span><span class="${data.gold_return_1y >= 0 ? 'positive' : 'negative'}">${data.gold_return_1y}%</span></div>
            <div class="data-row"><span>Nifty 1Y Return:</span><span class="${data.nifty_return_1y >= 0 ? 'positive' : 'negative'}">${data.nifty_return_1y}%</span></div>
            <div class="data-row highlight"><span>Better Performer:</span><span class="positive">${data.better_performer}</span></div>
            <div class="data-row"><span>Gold/Nifty Ratio:</span><span>${data.ratio}</span></div>
            <div class="data-row"><span>Ratio Change:</span><span class="${data.ratio_change >= 0 ? 'positive' : 'negative'}">${data.ratio_change >= 0 ? '+' : ''}${data.ratio_change}%</span></div>
        </div>
    `;
}

async function calculateGoldValue() {
    const weight = parseFloat(document.getElementById('goldWeight').value);
    const purity = document.getElementById('goldPurity').value;
    
    const data = await api('/api/gold/calculate', {
        method: 'POST',
        body: JSON.stringify({ weight_grams: weight, purity: purity })
    });
    
    const container = document.getElementById('goldCalcResult');
    
    if (data.error) {
        container.innerHTML = `<p class="placeholder">${data.error}</p>`;
        return;
    }
    
    container.innerHTML = `
        <div class="calculator-result">
            <div class="result-row"><span>Gold Price (USD/oz):</span><span>$${data.gold_price_usd_per_oz}</span></div>
            <div class="result-row"><span>Gold Price (INR/g):</span><span>₹${data.gold_price_inr_per_gram}</span></div>
            <div class="result-row"><span>Weight:</span><span>${data.weight_grams}g</span></div>
            <div class="result-row"><span>Purity:</span><span>${data.purity} (${(data.purity_factor * 100).toFixed(1)}%)</span></div>
            <div class="result-row highlight"><span>Value (INR):</span><span class="positive">₹${data.total_value_inr.toLocaleString()}</span></div>
            <div class="result-row"><span>Value (USD):</span><span>$${data.total_value_usd.toLocaleString()}</span></div>
        </div>
    `;
}

async function loadGoldETFs() {
    const container = document.getElementById('goldETFs');
    container.innerHTML = '<p class="placeholder">Loading ETFs...</p>';
    
    const data = await api('/api/gold/etfs');
    
    if (data.error || !data.etfs) {
        container.innerHTML = '<p class="placeholder">No ETF data</p>';
        return;
    }
    
    container.innerHTML = `
        <table>
            <thead><tr><th>Symbol</th><th>Name</th><th>Price</th><th>Change</th></tr></thead>
            <tbody>
                ${data.etfs.map(e => `
                    <tr>
                        <td><strong>${e.symbol}</strong></td>
                        <td>${e.name}</td>
                        <td>$${e.price}</td>
                        <td class="${e.changePercent >= 0 ? 'positive' : 'negative'}">${e.changePercent >= 0 ? '+' : ''}${e.changePercent}%</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// Market Status Banner
async function loadMarketStatusBanner() {
    const data = await api('/api/analytics/market-status');
    const banner = document.getElementById('marketStatusBanner');
    const text = document.getElementById('marketStatusText');
    
    if (data.status === 'OPEN') {
        banner.className = 'market-status-banner open';
        text.textContent = `Market is OPEN • ${data.currentTime}`;
    } else if (data.status === 'PRE_MARKET') {
        banner.className = 'market-status-banner pre-market';
        text.textContent = `Pre-Market Session • ${data.currentTime}`;
    } else {
        banner.className = 'market-status-banner closed';
        text.textContent = `Market CLOSED • ${data.message}`;
    }
}

// Portfolio Analytics
// Live analytics state — raw holdings so updateAnalyticsLive() can
// recompute the summary and performer rows from WebSocket quotes.
let analyticsLiveHoldings = [];

async function loadPortfolioAnalytics() {
    const container = document.getElementById('portfolioAnalytics');
    container.innerHTML = '<p class="placeholder">Loading analytics...</p>';

    const data = await api('/api/analytics/portfolio');

    if (data.error) {
        analyticsLiveHoldings = [];
        container.innerHTML = `<p class="placeholder">${data.error}</p>`;
        return;
    }

    const summary = data.summary;
    analyticsLiveHoldings = data.holdings || [];

    container.innerHTML = `
        <div class="analytics-summary">
            <div class="analytics-card">
                <span class="label">Invested</span>
                <span class="value">₹${summary.totalInvested.toLocaleString()}</span>
            </div>
            <div class="analytics-card">
                <span class="label">Current Value</span>
                <span class="value" data-live-current-value>₹${summary.totalCurrentValue.toLocaleString()}</span>
            </div>
            <div class="analytics-card">
                <span class="label">P&L</span>
                <span class="value ${summary.totalPnL >= 0 ? 'positive' : 'negative'}" data-live-total-pnl>${summary.totalPnL >= 0 ? '+' : ''}₹${summary.totalPnL.toLocaleString()}</span>
            </div>
            <div class="analytics-card">
                <span class="label">Today</span>
                <span class="value ${summary.totalDayPnl >= 0 ? 'positive' : 'negative'}" data-live-day-pnl>${summary.totalDayPnl >= 0 ? '+' : ''}₹${summary.totalDayPnl.toLocaleString()}</span>
            </div>
            <div class="analytics-card">
                <span class="label">Return</span>
                <span class="value ${summary.totalReturn >= 0 ? 'positive' : 'negative'}" data-live-total-return>${summary.totalReturn >= 0 ? '+' : ''}${summary.totalReturn}%</span>
            </div>
        </div>

        <div class="grid-2 mt-2">
            <div class="sector-allocation">
                <h4>Sector Allocation</h4>
                <div class="allocation-bars">
                    ${Object.entries(data.sectorAllocation).sort((a,b) => b[1] - a[1]).map(([sector, pct]) => `
                        <div class="allocation-bar">
                            <span class="sector-name">${sector}</span>
                            <div class="bar-container">
                                <div class="bar-fill" style="width: ${Math.min(pct, 100)}%"></div>
                            </div>
                            <span class="sector-pct">${pct}%</span>
                        </div>
                    `).join('')}
                </div>
            </div>

            <div class="performers">
                <h4>Top Performers</h4>
                ${data.topPerformers.length ? data.topPerformers.map(p => `
                    <div class="performer-item ${p.returnPercent >= 0 ? 'positive' : 'negative'}" data-perf-symbol="${p.symbol}">
                        <span>${p.name}</span>
                        <span>${p.returnPercent >= 0 ? '+' : ''}${p.returnPercent}%</span>
                    </div>
                `).join('') : '<p class="placeholder">No profitable holdings yet</p>'}

                <h4 class="mt-2">Worst Performers</h4>
                ${data.worstPerformers.length ? data.worstPerformers.map(p => `
                    <div class="performer-item ${p.returnPercent >= 0 ? 'positive' : 'negative'}" data-perf-symbol="${p.symbol}">
                        <span>${p.name}</span>
                        <span>${p.returnPercent >= 0 ? '+' : ''}${p.returnPercent}%</span>
                    </div>
                `).join('') : '<p class="placeholder">No losing holdings 🎉</p>'}
            </div>
        </div>

        <div class="card mt-2" style="padding:16px;">
            <h4>Stock Allocation</h4>
            <div style="display:flex; align-items:center; gap:28px; flex-wrap:wrap; margin-top:8px;">
                <div id="allocationDonut"></div>
                <div id="allocationLegend" style="flex:1; min-width:240px;"></div>
            </div>
        </div>
    `;

    // Pick up quotes that arrived while we were rendering.
    updateAnalyticsLive();
}

// Recompute the Analytics summary + performer rows from liveQuoteCache so the
// Analytics section always matches the live P&L in the holdings table.
function updateAnalyticsLive() {
    const container = document.getElementById('portfolioAnalytics');
    if (!container || !analyticsLiveHoldings.length) return;

    let invested = 0;
    let current = 0;
    const pctBySymbol = {};

    analyticsLiveHoldings.forEach(h => {
        const qty = Number(h.quantity) || 0;
        const buy = Number(h.buyPrice) || 0;
        invested += qty * buy;
        const quote = getLiveQuote(h.symbol);
        const price = quote ? quote.price : (Number(h.currentPrice) || buy);
        current += price * qty;
        pctBySymbol[h.symbol] = buy > 0 ? ((price - buy) / buy) * 100 : 0;
    });

    const pnl = current - invested;
    const ret = invested > 0 ? (pnl / invested) * 100 : 0;

    const cvEl = container.querySelector('[data-live-current-value]');
    if (cvEl) cvEl.textContent = `₹${(Math.round(current * 100) / 100).toLocaleString()}`;

    const pnlEl = container.querySelector('[data-live-total-pnl]');
    if (pnlEl) {
        pnlEl.textContent = `${pnl >= 0 ? '+' : ''}₹${(Math.round(pnl * 100) / 100).toLocaleString()}`;
        pnlEl.classList.toggle('positive', pnl >= 0);
        pnlEl.classList.toggle('negative', pnl < 0);
    }

    const retEl = container.querySelector('[data-live-total-return]');
    if (retEl) {
        retEl.textContent = `${ret >= 0 ? '+' : ''}${ret.toFixed(2)}%`;
        retEl.classList.toggle('positive', ret >= 0);
        retEl.classList.toggle('negative', ret < 0);
    }

    const dayEl = container.querySelector('[data-live-day-pnl]');
    if (dayEl) {
        let day = 0;
        analyticsLiveHoldings.forEach(h => {
            const qty = Number(h.quantity) || 0;
            const quote = getLiveQuote(h.symbol);
            day += quote ? (quote.change || 0) * qty : (Number(h.dayChangePnl) || 0);
        });
        dayEl.textContent = `${day >= 0 ? '+' : ''}₹${(Math.round(day * 100) / 100).toLocaleString()}`;
        dayEl.classList.toggle('positive', day >= 0);
        dayEl.classList.toggle('negative', day < 0);
    }

    container.querySelectorAll('[data-perf-symbol]').forEach(el => {
        const pct = pctBySymbol[el.getAttribute('data-perf-symbol')];
        if (!Number.isFinite(pct)) return;
        const span = el.querySelector('span:last-child');
        if (span) span.textContent = `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`;
        el.classList.toggle('positive', pct >= 0);
        el.classList.toggle('negative', pct < 0);
    });

    // Stock weights drift with prices — keep the donut live too.
    renderAllocationDonut('allocationDonut', 'allocationLegend', analyticsLiveHoldings);
}

// Export Portfolio Report
async function exportPortfolioReport() {
    const data = await api('/api/analytics/portfolio/report');
    
    if (data.error) {
        showToast('No portfolio data to export', 'warning');
        return;
    }
    
    let reportText = `
STOCKPULSE PORTFOLIO REPORT
Generated: ${data.generatedAt}
Market Status: ${data.marketStatus}

SUMMARY
=======
Total Invested: ₹${data.summary.totalInvested.toLocaleString()}
Current Value: ₹${data.summary.totalCurrentValue.toLocaleString()}
P&L: ₹${data.summary.totalPnL.toLocaleString()}
Return: ${data.summary.totalReturn}%
Holdings: ${data.summary.holdingCount}

HOLDINGS
========
${data.holdings.map(h => `${h.name}: ₹${h.currentValue} (${h.returnPercent >= 0 ? '+' : ''}${h.returnPercent}%)`).join('\n')}

SECTOR ALLOCATION
=================
${Object.entries(data.sectorAllocation).map(([s, p]) => `${s}: ${p}%`).join('\n')}

---
This report is for educational purposes only.
    `;
    
    const blob = new Blob([reportText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'portfolio_report.txt';
    a.click();
    URL.revokeObjectURL(url);
}

// Smart Alerts Pro
async function createAlertPro() {
    const symbol = document.getElementById('alertProSymbol').value;
    const name = document.getElementById('alertProName').value;
    const rsiBelow = document.getElementById('alertProRsiBelow').value;
    const priceAbove = document.getElementById('alertProPriceAbove').value;
    const volume = document.getElementById('alertProVolume').value;
    
    if (!symbol) return showToast('Enter symbol', 'warning');
    
    const conditions = {};
    if (rsiBelow) conditions.rsi_below = parseFloat(rsiBelow);
    if (priceAbove) conditions.price_above = parseFloat(priceAbove);
    if (volume) conditions.volume_above_avg = parseFloat(volume);
    
    await api('/api/analytics/alerts', {
        method: 'POST',
        body: JSON.stringify({ symbol, name: name || `Alert on ${symbol}`, conditions })
    });
    
    loadAlertsPro();
}

async function loadAlertsPro() {
    const data = await api('/api/analytics/alerts');
    const container = document.getElementById('alertsProList');
    
    if (!data.alerts || data.alerts.length === 0) {
        container.innerHTML = '<p class="placeholder">No smart alerts set</p>';
        return;
    }
    
    container.innerHTML = `
        <table>
            <thead><tr><th>Name</th><th>Symbol</th><th>Conditions</th><th>Status</th><th>Action</th></tr></thead>
            <tbody>
                ${data.alerts.map(a => `
                    <tr>
                        <td><strong>${a.name}</strong></td>
                        <td>${a.symbol}</td>
                        <td>${Object.entries(a.conditions).map(([k,v]) => `${k}: ${v}`).join(', ')}</td>
                        <td><span class="badge ${a.active ? 'positive' : ''}">${a.active ? 'Active' : 'Inactive'}</span></td>
                        <td><button class="btn-danger" onclick="deleteAlertPro(${a.id})">Delete</button></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

async function deleteAlertPro(id) {
    await api(`/api/analytics/alerts/${id}`, { method: 'DELETE' });
    loadAlertsPro();
}

// ===== MUTUAL FUNDS =====
async function loadMutualFunds() {
    const container = document.getElementById('mutualFundsList');
    container.innerHTML = '<p class="placeholder">Loading funds...</p>';
    const data = await api('/api/mutual-funds');
    if (Array.isArray(data) && data.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Fund</th><th>NAV</th><th>Daily Change</th><th>1M</th><th>3M</th><th>1Y</th><th>Category</th></tr></thead>
                <tbody>
                    ${data.map(f => `
                        <tr>
                            <td><strong>${f.name}</strong></td>
                            <td>₹${fmtPrice(f.nav).replace('₹','')}</td>
                            <td class="${f.dailyChange >= 0 ? 'positive' : 'negative'}">${fmtChg(f.dailyChange)} (${fmtPct(f.dailyChangePct)})</td>
                            <td class="${(f.returns?.['1M']||0) >= 0 ? 'positive' : 'negative'}">${fmtPct(f.returns?.['1M'])}</td>
                            <td class="${(f.returns?.['3M']||0) >= 0 ? 'positive' : 'negative'}">${fmtPct(f.returns?.['3M'])}</td>
                            <td class="${(f.returns?.['1Y']||0) >= 0 ? 'positive' : 'negative'}">${fmtPct(f.returns?.['1Y'])}</td>
                            <td><span class="badge">${f.category}</span></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No fund data available</p>';
    }
}

async function calculateSIP() {
    const amount = parseFloat(document.getElementById('sipAmount').value);
    const annualReturn = parseFloat(document.getElementById('sipReturn').value);
    const years = parseInt(document.getElementById('sipYears').value);
    const data = await api('/api/mutual-funds/sip-calculator', {
        method: 'POST', body: JSON.stringify({ amount, annualReturn, years })
    });
    const container = document.getElementById('sipResult');
    if (data.totalInvested) {
        container.innerHTML = `
            <div class="analytics-summary" style="grid-template-columns: repeat(4, 1fr);">
                <div class="analytics-card"><span class="label">Invested</span><span class="value">₹${data.totalInvested.toLocaleString()}</span></div>
                <div class="analytics-card"><span class="label">Future Value</span><span class="value positive">₹${data.futureValue.toLocaleString()}</span></div>
                <div class="analytics-card"><span class="label">Wealth Gained</span><span class="value positive">₹${data.wealthGained.toLocaleString()}</span></div>
                <div class="analytics-card"><span class="label">Multiple</span><span class="value">${data.returnMultiple}x</span></div>
            </div>
        `;
    }
}

// ===== CURRENCY CONVERTER =====
async function convertCurrency() {
    const amount = parseFloat(document.getElementById('convertAmount').value);
    const from = document.getElementById('convertFrom').value;
    const to = document.getElementById('convertTo').value;
    const data = await api('/api/currency/convert', {
        method: 'POST', body: JSON.stringify({ amount, fromCurrency: from, toCurrency: to })
    });
    const container = document.getElementById('convertResult');
    if (data.convertedAmount) {
        container.innerHTML = `
            <div class="analytics-summary" style="grid-template-columns: repeat(3, 1fr);">
                <div class="analytics-card"><span class="label">From</span><span class="value">${data.amount} ${data.from}</span></div>
                <div class="analytics-card"><span class="label">Rate</span><span class="value">${data.rate}</span></div>
                <div class="analytics-card"><span class="label">To</span><span class="value positive">${data.convertedAmount.toLocaleString()} ${data.to}</span></div>
            </div>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">Could not fetch rate</p>';
    }
}

async function loadQuickRates() {
    const container = document.getElementById('quickRates');
    container.innerHTML = '<p class="placeholder">Loading rates...</p>';
    const currencies = ['USD', 'EUR', 'GBP', 'JPY', 'AED', 'SGD'];
    const rates = [];
    for (const cur of currencies) {
        const data = await api(`/api/currency/rate/${cur}`);
        if (data && data.rate) rates.push(data);
    }
    if (rates.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Currency</th><th>Rate (to INR)</th><th>Change</th><th>52W High</th><th>52W Low</th></tr></thead>
                <tbody>
                    ${rates.map(r => `
                        <tr>
                            <td><strong>${r.from}</strong></td>
                            <td>₹${r.rate}</td>
                            <td class="${r.change >= 0 ? 'positive' : 'negative'}">${fmtChg(r.changePct)}%</td>
                            <td>₹${r.high52w}</td>
                            <td>₹${r.low52w}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">Could not load rates</p>';
    }
}

// ===== QUARTERLY RESULTS =====
async function loadUpcomingResults() {
    const container = document.getElementById('upcomingResults');
    container.innerHTML = '<p class="placeholder">Loading results...</p>';
    const data = await api('/api/results/upcoming');
    if (data.results && data.results.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Stock</th><th>Date</th><th>Days Until</th><th>Status</th></tr></thead>
                <tbody>
                    ${data.results.map(r => `
                        <tr>
                            <td><strong>${r.symbol}</strong></td>
                            <td>${r.date}</td>
                            <td>${r.daysUntil > 0 ? r.daysUntil + ' days' : 'Today'}</td>
                            <td><span class="badge ${r.status === 'Upcoming' ? 'positive' : 'neutral'}">${r.status}</span></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No upcoming results found</p>';
    }
}

async function loadBlockDeals() {
    const container = document.getElementById('blockDealsList');
    container.innerHTML = '<p class="placeholder">Loading...</p>';
    const data = await api('/api/deals/block');
    if (data.deals && data.deals.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Stock</th><th>Type</th><th>Qty</th><th>Price</th><th>Value</th><th>Client</th></tr></thead>
                <tbody>
                    ${data.deals.map(d => `
                        <tr>
                            <td><strong>${d.symbol}</strong></td>
                            <td><span class="badge ${d.type === 'BUY' ? 'positive' : 'negative'}">${d.type}</span></td>
                            <td>${d.quantity.toLocaleString()}</td>
                            <td>₹${d.price}</td>
                            <td>₹${d.value.toLocaleString()}</td>
                            <td>${d.client}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No block deals today</p>';
    }
}

async function loadBulkDeals() {
    const container = document.getElementById('bulkDealsList');
    container.innerHTML = '<p class="placeholder">Loading...</p>';
    const data = await api('/api/deals/bulk');
    if (data.deals && data.deals.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Stock</th><th>Type</th><th>Qty</th><th>Price</th><th>Value</th><th>Client</th></tr></thead>
                <tbody>
                    ${data.deals.map(d => `
                        <tr>
                            <td><strong>${d.symbol}</strong></td>
                            <td><span class="badge ${d.type === 'BUY' ? 'positive' : 'negative'}">${d.type}</span></td>
                            <td>${d.quantity.toLocaleString()}</td>
                            <td>₹${d.price}</td>
                            <td>₹${d.value.toLocaleString()}</td>
                            <td>${d.client}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No bulk deals today</p>';
    }
}

// ===== SCREENER STRATEGIES =====
async function loadStrategies() {
    const container = document.getElementById('strategiesList');
    const data = await api('/api/strategies');
    if (data) {
        container.innerHTML = Object.entries(data).map(([key, s]) => `
            <button class="preset-btn" onclick="runStrategy('${key}')">
                <span class="preset-icon">✦</span>
                <span>${s.name}</span>
                <span class="preset-desc">${s.description}</span>
            </button>
        `).join('');
    }
}

async function runStrategy(key) {
    const container = document.getElementById('strategyResults');
    container.innerHTML = '<p class="placeholder">Running strategy...</p>';
    const data = await api(`/api/strategies/${key}`);
    if (data.results && data.results.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Stock</th><th>Price</th><th>Change</th><th>P/E</th><th>P/B</th><th>Div Yield</th><th>Earnings Growth</th></tr></thead>
                <tbody>
                    ${data.results.map(s => `
                        <tr>
                            <td><strong>${s.name}</strong></td>
                            <td>${fmtPrice(s.price)}</td>
                            <td class="${s.changePercent >= 0 ? 'positive' : 'negative'}">${fmtPct(s.changePercent)}</td>
                            <td>${s.pe || '-'}</td>
                            <td>${s.pb || '-'}</td>
                            <td>${s.dividendYield}%</td>
                            <td class="${s.earningsGrowth >= 0 ? 'positive' : 'negative'}">${fmtPct(s.earningsGrowth)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            <p class="placeholder" style="margin-top:8px">${data.count} stocks found</p>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No stocks match this strategy</p>';
    }
}

// ===== DOWNSTOX LIVE DATA =====

// Superinvestors
async function loadSuperinvestors() {
    const container = document.getElementById('superinvestorsList');
    container.innerHTML = '<p class="placeholder">Loading investors...</p>';
    const data = await api('/api/downstox/superinvestors');
    if (data.investors && data.investors.length > 0) {
        container.innerHTML = `
            <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap:8px;">
                ${data.investors.map(inv => `
                    <div class="preset-btn" onclick="loadSuperinvestorDetail('${inv.slug || inv.name}')" style="text-align:center;">
                        <span style="font-size:14px; font-weight:600;">${inv.name}</span>
                        <span class="preset-desc">${inv.firm || ''}</span>
                    </div>
                `).join('')}
            </div>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No investor data</p>';
    }
}

async function loadSuperinvestorDetail(slug) {
    const container = document.getElementById('superinvestorDetail');
    container.innerHTML = '<p class="placeholder">Loading portfolio...</p>';
    const data = await api(`/api/downstox/superinvestors/${slug}`);
    if (data.error) {
        container.innerHTML = `<p class="placeholder">${data.error}</p>`;
        return;
    }
    const holdings = data.holdings || data.data?.holdings || [];
    if (holdings.length > 0) {
        container.innerHTML = `
            <h4 style="font-size:14px; margin-bottom:8px;">${data.name || slug} Holdings</h4>
            <table>
                <thead><tr><th>Company</th><th>Shares</th><th>Value</th><th>% Change</th></tr></thead>
                <tbody>
                    ${holdings.slice(0, 15).map(h => `
                        <tr>
                            <td><strong>${h.company || h.name || ''}</strong></td>
                            <td>${h.shares ? h.shares.toLocaleString() : '-'}</td>
                            <td>${h.value ? '₹' + h.value.toLocaleString() : '-'}</td>
                            <td class="${(h.change || 0) >= 0 ? 'positive' : 'negative'}">${h.change ? fmtPct(h.change) : '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = `<p class="placeholder">No holdings data for ${slug}</p>`;
    }
}

// Breakout Stocks
async function loadBreakouts() {
    const container = document.getElementById('breakoutsList');
    container.innerHTML = '<p class="placeholder">Loading breakouts...</p>';
    const data = await api('/api/downstox/breakouts');
    if (data.data) {
        const labels = data.labels || {};
        const tabs = Object.keys(data.data).map(k => `<button class="preset-btn" onclick="showBreakoutPeriod('${k}')" style="padding:6px 12px; font-size:12px;">${labels[k] || k + 'D'}</button>`).join('');
        container.innerHTML = `
            <div style="display:flex; gap:6px; margin-bottom:12px; flex-wrap:wrap;">${tabs}</div>
            <div id="breakoutTable"></div>
        `;
        window._breakoutData = data.data;
        showBreakoutPeriod('10');
    } else {
        container.innerHTML = '<p class="placeholder">No breakout data</p>';
    }
}

function showBreakoutPeriod(period) {
    const container = document.getElementById('breakoutTable');
    const stocks = (window._breakoutData || {})[period] || [];
    if (stocks.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Symbol</th><th>Exchange</th><th>Price</th><th>Prev High</th><th>Magnitude</th><th>Volume Ratio</th></tr></thead>
                <tbody>
                    ${stocks.slice(0, 15).map(s => `
                        <tr>
                            <td><strong>${s.symbol}</strong></td>
                            <td>${s.exchange}</td>
                            <td>₹${s.price}</td>
                            <td>₹${s.prevHigh}</td>
                            <td class="positive">+${s.magnitude?.toFixed(1)}%</td>
                            <td class="${s.volumeRatio > 2 ? 'positive' : ''}">${s.volumeRatio?.toFixed(1)}x</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No breakouts for this period</p>';
    }
}

// Dividend Aristocrats
async function loadDividendAristocrats() {
    const container = document.getElementById('dividendAristocrats');
    container.innerHTML = '<p class="placeholder">Loading...</p>';
    const data = await api('/api/downstox/dividend-aristocrats');
    if (data.stocks && data.stocks.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Symbol</th><th>Company</th><th>Dividend Yield</th><th>Consecutive Years</th><th>Price</th></tr></thead>
                <tbody>
                    ${data.stocks.slice(0, 20).map(s => `
                        <tr>
                            <td><strong>${s.symbol || s.name}</strong></td>
                            <td>${s.company || s.symbol || ''}</td>
                            <td class="positive">${s.dividendYield ? s.dividendYield + '%' : '-'}</td>
                            <td>${s.consecutiveYears || s.years || '-'} years</td>
                            <td>${s.price ? '₹' + s.price : '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No dividend aristocrat data</p>';
    }
}

// Global Market Sentiment
async function loadGlobalSentiment() {
    const container = document.getElementById('globalSentiment');
    container.innerHTML = '<p class="placeholder">Loading...</p>';
    const data = await api('/api/downstox/sentiments');
    if (data.sentiments) {
        const entries = Object.entries(data.sentiments);
        container.innerHTML = `
            <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap:8px;">
                ${entries.map(([key, s]) => `
                    <div class="preset-btn" style="text-align:left;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <strong style="text-transform:uppercase;">${key}</strong>
                            <span class="badge ${s.label === 'Bullish' ? 'positive' : s.label === 'Bearish' ? 'negative' : ''}">${s.label}</span>
                        </div>
                        <span class="preset-desc">${s.reason || ''}</span>
                    </div>
                `).join('')}
            </div>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No sentiment data</p>';
    }
}

// Weekly Outlook
async function loadWeeklyOutlook() {
    const container = document.getElementById('weeklyOutlook');
    container.innerHTML = '<p class="placeholder">Loading...</p>';
    const data = await api('/api/downstox/weekly-outlook');
    if (data.error) {
        container.innerHTML = `<p class="placeholder">${data.error}</p>`;
        return;
    }
    const indices = data.indices || data.data || {};
    const entries = Object.entries(indices);
    if (entries.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Index</th><th>RSI</th><th>ATR</th><th>Regime</th><th>Support</th><th>Resistance</th></tr></thead>
                <tbody>
                    ${entries.map(([name, info]) => `
                        <tr>
                            <td><strong>${name}</strong></td>
                            <td>${info.rsi || '-'}</td>
                            <td>${info.atr || '-'}</td>
                            <td><span class="badge">${info.regime || '-'}</span></td>
                            <td>${info.support || '-'}</td>
                            <td>${info.resistance || '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = `<pre style="font-size:12px; white-space:pre-wrap;">${JSON.stringify(data, null, 2).substring(0, 2000)}</pre>`;
    }
}

// Holidays
async function loadHolidays() {
    const container = document.getElementById('holidaysList');
    container.innerHTML = '<p class="placeholder">Loading...</p>';
    const data = await api('/api/downstox/holidays');
    if (data.upcoming && data.upcoming.length > 0) {
        const ms = data.marketStatus || {};
        container.innerHTML = `
            <div style="margin-bottom:12px; font-size:12px; color:var(--text-secondary);">
                Status: <span class="badge ${ms.open ? 'positive' : 'negative'}">${ms.open ? 'OPEN' : 'CLOSED'}</span>
                ${ms.reason ? ' - ' + ms.reason : ''}
                ${ms.nextTradingDay ? ' | Next: ' + ms.nextTradingDay.label : ''}
            </div>
            <table>
                <thead><tr><th>Date</th><th>Holiday</th></tr></thead>
                <tbody>
                    ${data.upcoming.map(h => `
                        <tr>
                            <td>${h.date}</td>
                            <td><strong>${h.name}</strong></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No holiday data</p>';
    }
}

// Announcements
async function loadAnnouncements() {
    const container = document.getElementById('announcementsList');
    container.innerHTML = '<p class="placeholder">Loading...</p>';
    const data = await api('/api/downstox/announcements');
    if (data.announcements && data.announcements.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Company</th><th>Subject</th><th>Date</th><th>Exchange</th></tr></thead>
                <tbody>
                    ${data.announcements.slice(0, 20).map(a => `
                        <tr>
                            <td><strong>${a.company || a.symbol || ''}</strong></td>
                            <td style="max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${a.subject || a.title || ''}</td>
                            <td>${a.date || ''}</td>
                            <td>${a.exchange || ''}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No announcements</p>';
    }
}

// Other Side (Market Regime)
async function loadOtherSide() {
    const container = document.getElementById('otherSideData');
    container.innerHTML = '<p class="placeholder">Loading...</p>';
    const data = await api('/api/downstox/other-side');
    if (data.error) { container.innerHTML = `<p class="placeholder">${data.error}</p>`; return; }
    const r = data.regime || {};
    container.innerHTML = `
        <div style="margin-bottom:8px; font-size:12px; color:var(--text-secondary);">As of: ${data.asOf}</div>
        <div class="analytics-summary" style="grid-template-columns: repeat(3, 1fr);">
            <div class="analytics-card"><span class="label">Regime</span><span class="value" style="font-size:12px;">${r.regime || '-'}</span></div>
            <div class="analytics-card"><span class="label">FII Stance</span><span class="value ${r.fii_stance?.includes('short') ? 'negative' : 'positive'}">${r.fii_stance || '-'}</span></div>
            <div class="analytics-card"><span class="label">Retail Stance</span><span class="value">${r.retail_stance || '-'}</span></div>
        </div>
        <div style="margin-top:12px;">
            <div class="data-row"><span>FII Index Fut Net:</span><span class="${(r.fii_idx_fut_net||0) >= 0 ? 'positive' : 'negative'}">${(r.fii_idx_fut_net||0).toLocaleString()}</span></div>
            <div class="data-row"><span>FII Index Fut Percentile:</span><span>${r.fii_idx_fut_pctl || '-'}</span></div>
            <div class="data-row"><span>Client Put Short Net:</span><span>${(r.client_put_short_net||0).toLocaleString()}</span></div>
            <div class="data-row"><span>Fragility:</span><span class="${r.fragility_label === 'Extreme' ? 'negative' : ''}">${r.fragility_pctl || '-'} (${r.fragility_label || '-'})</span></div>
            <div class="data-row"><span>FII Cash 20D:</span><span class="${parseFloat(r.fii_cash_20d||0) >= 0 ? 'positive' : 'negative'}">₹${r.fii_cash_20d || '-'} Cr</span></div>
            <div class="data-row"><span>Divergence:</span><span class="negative">${r.divergence_state || '-'}</span></div>
        </div>
    `;
}

// Pre-Open Base Rates
async function loadPreOpen() {
    const container = document.getElementById('preOpenData');
    container.innerHTML = '<p class="placeholder">Loading...</p>';
    const data = await api('/api/downstox/pre-open');
    if (data.error) { container.innerHTML = `<p class="placeholder">${data.error}</p>`; return; }
    const rates = data.rates || {};
    container.innerHTML = `
        <div style="margin-bottom:8px; font-size:12px; color:var(--text-secondary);">Sessions: ${data.sessions} | ${data.firstSession} to ${data.lastSession}</div>
        <table>
            <thead><tr><th>Signal</th><th>Samples</th><th>Closed Up</th><th>Hit Rate</th></tr></thead>
            <tbody>
                ${Object.entries(rates).map(([k, v]) => `
                    <tr>
                        <td><strong>${k.replace(/([A-Z])/g, ' $1').trim()}</strong></td>
                        <td>${v.n}</td>
                        <td>${v.closedUp}</td>
                        <td class="${v.rate > 0.5 ? 'positive' : v.rate < 0.35 ? 'negative' : ''}">${(v.rate * 100).toFixed(1)}%</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
        <p class="placeholder" style="margin-top:8px;">${data.note}</p>
    `;
}

// Promises Tracker
async function loadPromises() {
    const container = document.getElementById('promisesData');
    container.innerHTML = '<p class="placeholder">Loading...</p>';
    const data = await api('/api/downstox/promises');
    if (data.promises && data.promises.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Company</th><th>Promised</th><th>Metric</th><th>Target</th><th>Period</th><th>Status</th></tr></thead>
                <tbody>
                    ${data.promises.slice(0, 15).map(p => `
                        <tr>
                            <td><strong>${p.company || p.symbol}</strong></td>
                            <td style="max-width:250px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px;">"${p.quote || ''}"</td>
                            <td>${p.metric || '-'}</td>
                            <td class="positive">${p.target || '-'}</td>
                            <td>${p.reportingPeriod || p.timeframe || '-'}</td>
                            <td><span class="badge ${p.status === 'delivered' ? 'positive' : p.status === 'missed' ? 'negative' : ''}">${p.status || 'stated'}</span></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No promises data</p>';
    }
}

// Stock Deep Dive
async function loadStockDetail() {
    const symbol = document.getElementById('stockDetailSymbol').value;
    if (!symbol) return showToast('Enter a symbol', 'warning');
    const container = document.getElementById('stockDetailData');
    container.innerHTML = '<p class="placeholder">Loading...</p>';
    const data = await api(`/api/downstox/stocks/${symbol}`);
    if (data.error) { container.innerHTML = `<p class="placeholder">${data.error}</p>`; return; }
    const s = data.stock || {};
    const f = data.fundamentals || {};
    container.innerHTML = `
        <div style="margin-bottom:8px;">
            <strong style="font-size:14px;">${s.name || symbol}</strong>
            <span style="margin-left:8px; font-size:12px; color:var(--text-secondary);">${s.exchange || ''} | ${data.sector || ''}</span>
            <span class="badge" style="margin-left:8px;">${(data.indices || []).join(', ')}</span>
        </div>
        <div class="analytics-summary" style="grid-template-columns: repeat(4, 1fr);">
            <div class="analytics-card"><span class="label">CMP</span><span class="value">${f.cmp ? '₹' + f.cmp : '-'}</span></div>
            <div class="analytics-card"><span class="label">P/E</span><span class="value">${f.pe || '-'}</span></div>
            <div class="analytics-card"><span class="label">ROE</span><span class="value">${f.roe ? f.roe + '%' : '-'}</span></div>
            <div class="analytics-card"><span class="label">F-Score</span><span class="value">${f.fScore || '-'}</span></div>
        </div>
        <div style="margin-top:12px;">
            <div class="data-row"><span>Market Cap:</span><span>${f.mcap ? '₹' + f.mcap.toLocaleString() + ' Cr' : '-'}</span></div>
            <div class="data-row"><span>Book Value:</span><span>${f.bookValue ? '₹' + f.bookValue : '-'}</span></div>
            <div class="data-row"><span>Price/Book:</span><span>${f.priceToBook || '-'}</span></div>
            <div class="data-row"><span>Div Yield:</span><span>${f.divYield ? f.divYield + '%' : '-'}</span></div>
            <div class="data-row"><span>ROCE:</span><span>${f.roce ? f.roce + '%' : '-'}</span></div>
            <div class="data-row"><span>MTF Available:</span><span>${data.mtfAvailable ? 'Yes' : 'No'}</span></div>
        </div>
        ${s.rates ? `
            <div style="margin-top:12px; font-size:12px;">
                <strong>Broker MTF Rates:</strong>
                ${Object.entries(s.rates).slice(0,6).map(([k,v]) => `<span style="margin-left:8px; color:var(--text-secondary);">${k}: ${v}%</span>`).join('')}
            </div>
        ` : ''}
    `;
}

// US Multibaggers
async function loadUSMultibaggers() {
    const container = document.getElementById('usMultibaggers');
    container.innerHTML = '<p class="placeholder">Loading...</p>';
    const data = await api('/api/downstox/us-multibaggers');
    if (data.error) { container.innerHTML = `<p class="placeholder">${data.error}</p>`; return; }
    container.innerHTML = `
        <div style="margin-bottom:8px; font-size:12px; color:var(--text-secondary);">Universe: ${data.universeSize} US stocks</div>
        ${data.crazy && data.crazy.length > 0 ? `
            <h4 style="font-size:13px; margin-bottom:8px;">Crazy Returns (>250% in 1Y)</h4>
            <table>
                <thead><tr><th>Ticker</th><th>Company</th><th>Price</th><th>1Y Return</th><th>From Low</th><th>Exchange</th></tr></thead>
                <tbody>
                    ${data.crazy.map(s => `
                        <tr>
                            <td><strong>${s.ticker}</strong></td>
                            <td>${s.name}</td>
                            <td>$${s.price}</td>
                            <td class="positive">+${s.ret1y}%</td>
                            <td>+${s.fromLow}%</td>
                            <td>${s.exchange}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        ` : ''}
        ${data.multibaggers && data.multibaggers.length > 0 ? `
            <h4 style="font-size:13px; margin:12px 0 8px;">Multibaggers (100-250%)</h4>
            <table>
                <thead><tr><th>Ticker</th><th>Company</th><th>Price</th><th>1Y Return</th><th>Exchange</th></tr></thead>
                <tbody>
                    ${data.multibaggers.slice(0,10).map(s => `
                        <tr>
                            <td><strong>${s.ticker}</strong></td>
                            <td>${s.name}</td>
                            <td>$${s.price}</td>
                            <td class="positive">+${s.ret1y}%</td>
                            <td>${s.exchange}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        ` : ''}
    `;
}

// MF Schemes
async function loadMFSchemes() {
    const container = document.getElementById('mfSchemesList');
    container.innerHTML = '<p class="placeholder">Loading...</p>';
    const data = await api('/api/downstox/mf/schemes?limit=20');
    if (data.schemes && data.schemes.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Fund</th><th>Category</th><th>NAV</th><th>1M</th><th>1Y</th><th>3Y</th></tr></thead>
                <tbody>
                    ${data.schemes.map(s => `
                        <tr>
                            <td><strong style="font-size:12px;">${s.scheme_name?.substring(0,40)}</strong></td>
                            <td><span class="badge">${s.category || ''}</span></td>
                            <td>₹${s.nav || '-'}</td>
                            <td class="${parseFloat(s.return_1m||0) >= 0 ? 'positive' : 'negative'}">${s.return_1m ? s.return_1m + '%' : '-'}</td>
                            <td class="${parseFloat(s.return_1y||0) >= 0 ? 'positive' : 'negative'}">${s.return_1y ? s.return_1y + '%' : '-'}</td>
                            <td>${s.return_3y ? s.return_3y + '%' : '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No scheme data</p>';
    }
}

// Upgrade FII/DII to use live Downstox data
async function loadFiiDii() {
    const container = document.getElementById('fiiDiiActivity');
    container.innerHTML = '<p class="placeholder">Loading live FII/DII data...</p>';
    const data = await api('/api/downstox/fii-dii');
    if (data.error) {
        container.innerHTML = `<p class="placeholder">${data.error}</p>`;
        return;
    }
    const fii = data.fii || {};
    const dii = data.dii || {};
    const ms = data.marketStatus || {};
    container.innerHTML = `
        <div class="fii-dii-card">
            <p style="font-size:12px; color:var(--text-secondary); margin-bottom:12px;">Date: ${data.date} | Status: ${ms.open ? 'Market Open' : 'Closed'}</p>
            <div class="data-row"><span>FII Buy:</span><span>₹${(fii.buyValue || 0).toLocaleString()} Cr</span></div>
            <div class="data-row"><span>FII Sell:</span><span class="negative">₹${(fii.sellValue || 0).toLocaleString()} Cr</span></div>
            <div class="data-row"><span>FII Net:</span><span class="${(fii.netValue || 0) >= 0 ? 'positive' : 'negative'}">₹${(fii.netValue || 0).toLocaleString()} Cr</span></div>
            <div style="border-top:1px solid var(--border); margin:8px 0;"></div>
            <div class="data-row"><span>DII Buy:</span><span>₹${(dii.buyValue || 0).toLocaleString()} Cr</span></div>
            <div class="data-row"><span>DII Sell:</span><span class="negative">₹${(dii.sellValue || 0).toLocaleString()} Cr</span></div>
            <div class="data-row"><span>DII Net:</span><span class="${(dii.netValue || 0) >= 0 ? 'positive' : 'negative'}">₹${(dii.netValue || 0).toLocaleString()} Cr</span></div>
        </div>
    `;
}

// ===== TOAST NOTIFICATION SYSTEM (UI/UX Pro Max Enhanced) =====
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const icons = {
        success: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>',
        error: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#ef4444" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
        warning: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#f59e0b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
        info: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#3b82f6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');

    toast.innerHTML = `
        <div class="toast-content" style="display:flex; align-items:flex-start; gap:12px;">
            <div class="toast-icon" style="flex-shrink:0; margin-top:2px;">${icons[type] || icons.info}</div>
            <div class="toast-message" style="flex-grow:1; font-size:13px; font-weight:500; color:var(--text-primary); line-height:1.4;">${message}</div>
            <button class="toast-close" onclick="this.closest('.toast').remove()" aria-label="Close notification" style="background:none; border:none; color:var(--text-muted); cursor:pointer; padding:0; display:flex; align-items:center; justify-content:center; width:18px; height:18px; border-radius:4px; transition:color 0.2s;">
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        </div>
        <div class="toast-progress" style="position:absolute; bottom:0; left:0; height:2px; width:100%; animation: toastProgress 3s linear forwards;"></div>
    `;

    container.appendChild(toast);
    requestAnimationFrame(() => { toast.classList.add('show'); });

    const timeoutId = setTimeout(() => {
        toast.classList.remove('show');
        toast.classList.add('hide');
        setTimeout(() => toast.remove(), 300);
    }, 3000);

    toast.addEventListener('mouseenter', () => clearTimeout(timeoutId));
}

// ===== TABLE SORTING =====
function sortTable(tableId, colIndex, type = 'text') {
    const table = document.getElementById(tableId);
    if (!table) return;
    const tbody = table.querySelector('tbody');
    if (!tbody) return;
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const th = table.querySelectorAll('th')[colIndex];
    const isAsc = th.classList.contains('asc');
    table.querySelectorAll('th').forEach(h => { h.classList.remove('asc', 'desc'); });
    th.classList.add(isAsc ? 'desc' : 'asc');
    rows.sort((a, b) => {
        let va = a.cells[colIndex]?.textContent.trim() || '';
        let vb = b.cells[colIndex]?.textContent.trim() || '';
        if (type === 'number') {
            va = parseFloat(va.replace(/[₹,%x+]/g, '')) || 0;
            vb = parseFloat(vb.replace(/[₹,%x+]/g, '')) || 0;
            return isAsc ? vb - va : va - vb;
        }
        return isAsc ? vb.localeCompare(va) : va.localeCompare(vb);
    });
    rows.forEach(r => tbody.appendChild(r));
}

// ===== TAB CACHING =====
const tabCache = {};
const TAB_CACHE_TTL = 60000;
function getCachedTab(tabName) {
    const entry = tabCache[tabName];
    if (entry && Date.now() - entry.ts < TAB_CACHE_TTL) return entry.data;
    return null;
}
function setCachedTab(tabName, data) {
    tabCache[tabName] = { data, ts: Date.now() };
}

// ===== CHART CSS VARIABLE FIX =====
function getChartBg() {
    return getComputedStyle(document.body).getPropertyValue('--chart-bg').trim() || '#16161f';
}

// ===== STOCK DETAIL DRAWER =====
async function openStockDrawer(symbol) {
    const overlay = document.getElementById('drawerOverlay');
    const drawer = document.getElementById('stockDrawer');
    const content = document.getElementById('drawerContent');
    overlay.classList.add('active');
    drawer.classList.add('open');
    content.innerHTML = '<p class="placeholder">Loading ' + symbol + '...</p>';
    const [quote, detail] = await Promise.all([
        api(`/api/stocks/${symbol}/live`),
        api(`/api/downstox/stocks/${symbol.replace('.NS','')}`)
    ]);
    const q = quote || {};
    const f = detail.fundamentals || {};
    const s = detail.stock || {};
    content.innerHTML = `
        <div class="drawer-header">
            <h2>${symbol.replace('.NS','')}</h2>
            <p style="font-size:12px; color:var(--text-secondary);">${detail.sector || ''} | ${s.exchange || 'NSE'}</p>
        </div>
        <div class="drawer-stats">
            <div class="drawer-stat"><span class="label">Price</span><span class="value">${fmtPrice(q.price)}</span></div>
            <div class="drawer-stat"><span class="label">Change</span><span class="value ${(q.change||0)>=0?'positive':'negative'}">${fmtChg(q.change)} (${fmtPct(q.changePercent)})</span></div>
            <div class="drawer-stat"><span class="label">P/E</span><span class="value">${f.pe || '-'}</span></div>
            <div class="drawer-stat"><span class="label">ROE</span><span class="value">${f.roe ? f.roe+'%' : '-'}</span></div>
            <div class="drawer-stat"><span class="label">Mkt Cap</span><span class="value">${f.mcap ? '₹'+f.mcap.toLocaleString()+' Cr' : '-'}</span></div>
            <div class="drawer-stat"><span class="label">Div Yield</span><span class="value">${f.divYield ? f.divYield+'%' : '-'}</span></div>
        </div>
        <div style="display:flex;gap:8px;">
            <button class="btn-primary" onclick="closeDrawer();selectStock('${symbol}')">View Chart</button>
            <button class="btn-secondary" onclick="closeDrawer();showTab('watchlist');addToWatchlist('${symbol}')">+ Watchlist</button>
        </div>
    `;
}
function closeDrawer() {
    document.getElementById('drawerOverlay')?.classList.remove('active');
    document.getElementById('stockDrawer')?.classList.remove('open');
}

// ===== SECTOR DRILL-DOWN =====
async function drillSector(sectorName) {
    const container = document.getElementById('sectorDrillDown');
    if (!container) return;
    container.innerHTML = '<p class="placeholder">Loading ' + sectorName + ' stocks...</p>';
    container.style.display = 'block';
    const data = await api(`/api/sectors/${encodeURIComponent(sectorName)}`);
    if (data.stocks && data.stocks.length > 0) {
        container.innerHTML = `
            <h4 style="margin-bottom:8px;">${sectorName} Stocks</h4>
            <table id="sectorDrillTable">
                <thead><tr><th>Symbol</th><th>Name</th><th>Price</th><th>Change</th></tr></thead>
                <tbody>
                    ${data.stocks.map(s => `
                        <tr onclick="openStockDrawer('${s.symbol}')" style="cursor:pointer;">
                            <td><strong>${s.symbol?.replace('.NS','')}</strong></td>
                            <td>${s.name || ''}</td>
                            <td>${fmtPrice(s.price)}</td>
                            <td class="${(s.change||0)>=0?'positive':'negative'}">${fmtChg(s.change)} (${fmtPct(s.changePercent)})</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No stocks found</p>';
    }
}

// ===== MF FUND COMPARISON =====
const mfCompareList = [];
function toggleMFCompare(schemeCode, name) {
    const idx = mfCompareList.findIndex(x => x.code === schemeCode);
    if (idx >= 0) { mfCompareList.splice(idx, 1); showToast(`${name} removed from comparison`, 'info'); }
    else if (mfCompareList.length < 3) { mfCompareList.push({ code: schemeCode, name }); showToast(`${name} added to comparison`, 'success'); }
    else { showToast('Max 3 funds for comparison', 'warning'); return; }
    renderMFCompare();
}
function renderMFCompare() {
    const container = document.getElementById('mfCompareContainer');
    if (!container) return;
    if (mfCompareList.length < 2) { container.innerHTML = '<p class="placeholder">Select 2-3 funds to compare</p>'; return; }
    container.innerHTML = '<p class="placeholder">Loading comparison...</p>';
    Promise.all(mfCompareList.map(f => api(`/api/downstox/mf/scheme/${f.code}`))).then(results => {
        container.innerHTML = results.map((r, i) => `
            <div style="flex:1;min-width:200px;">
                <h4 style="font-size:13px;margin-bottom:8px;">${mfCompareList[i].name}</h4>
                <div class="data-row"><span>NAV:</span><span>₹${r.nav || '-'}</span></div>
                <div class="data-row"><span>1M:</span><span>${r.return_1m ? r.return_1m+'%' : '-'}</span></div>
                <div class="data-row"><span>1Y:</span><span>${r.return_1y ? r.return_1y+'%' : '-'}</span></div>
                <div class="data-row"><span>3Y:</span><span>${r.return_3y ? r.return_3y+'%' : '-'}</span></div>
            </div>
        `).join('<div style="width:1px;background:var(--border);margin:0 12px;"></div>');
    });
}

// ===== KEYBOARD SHORTCUTS =====
document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
    const key = e.key.toLowerCase();
    const shortcuts = { w: 'watchlist', p: 'portfolio', s: 'screener', a: 'analysis', g: 'gold', m: 'mutualfunds', c: 'currency' };
    if (shortcuts[key]) { e.preventDefault(); showTab(shortcuts[key]); }
    if (key === '?') { e.preventDefault(); showToast('Shortcuts: D=Dashboard, M=Market, S=Screener, W=Watchlist, P=Portfolio, G=Gold, /=Search, R=Refresh', 'info'); }
    if (key === 'arrowleft' && chart) { chart.scrollByLogicalPosition(-5, 0); }
    if (key === 'arrowright' && chart) { chart.scrollByLogicalPosition(5, 0); }
});

// ===== PDF EXPORT (txt format) =====
function exportPortfolioPDF() {
    const data = JSON.parse(localStorage.getItem('portfolio') || '{"holdings":[]}');
    if (!data.holdings || data.holdings.length === 0) { showToast('No portfolio data to export', 'warning'); return; }
    let txt = 'STOCKPULSE PRO - PORTFOLIO REPORT\n' + '='.repeat(50) + '\n\n';
    txt += 'Holdings:\n' + '-'.repeat(50) + '\n';
    data.holdings.forEach(h => {
        txt += `${h.symbol} | Qty: ${h.quantity} | Avg: ₹${h.avgPrice} | Current: ₹${h.currentPrice || '-'}\n`;
    });
    txt += '\nGenerated: ' + new Date().toLocaleString();
    const blob = new Blob([txt], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'portfolio-report.txt';
    a.click();
    showToast('Portfolio report exported', 'success');
}

// ===== SCREENER PERMALINKS =====
function generateScreenerLink() {
    const params = new URLSearchParams();
    document.querySelectorAll('.screener-filter').forEach(el => {
        if (el.value) params.set(el.name, el.value);
    });
    const url = window.location.origin + '/?' + params.toString();
    navigator.clipboard?.writeText(url);
    showToast('Screener link copied to clipboard', 'success');
}

// ===== WATCHLIST SPARKLINE =====
function drawSparkline(container, data, color) {
    if (!data || data.length < 2) return;
    const canvas = document.createElement('canvas');
    canvas.width = 80;
    canvas.height = 28;
    container.innerHTML = '';
    container.appendChild(canvas);
    const ctx = canvas.getContext('2d');
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    ctx.strokeStyle = color || (data[data.length-1] >= data[0] ? '#10b981' : '#ef4444');
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    data.forEach((v, i) => {
        const x = (i / (data.length - 1)) * 80;
        const y = 28 - ((v - min) / range) * 24 - 2;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
}

// ===== BACKTEST EQUITY CURVE =====
function renderBacktestEquityCurve(containerId, equityData) {
    const container = document.getElementById(containerId);
    if (!container || !equityData || equityData.length < 2) return;
    const chartObj = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 200,
        layout: { background: { color: getChartBg() }, textColor: '#8888a0' },
        grid: { vertLines: { color: 'rgba(255,255,255,0.04)' }, horzLines: { color: 'rgba(255,255,255,0.04)' } },
        rightPriceScale: { borderColor: 'rgba(255,255,255,0.06)' },
        timeScale: { borderColor: 'rgba(255,255,255,0.06)' }
    });
    const lineSeries = chartObj.addLineSeries({ color: '#6366f1', lineWidth: 2 });
    lineSeries.setData(equityData.map((d, i) => ({ time: i, value: d })));
}

// ===== WEBSOCKET LIVE PRICES =====
let ws = null;
let wsReconnectAttempts = 0;
const MAX_WS_RECONNECT = 5;
const WS_INDEX_SYMBOLS = ['^NSEI', '^BSESN', '^NSEBANK', '^CNXIT', '^NSEMDCP50'];
const WS_MAX_SYMBOLS = 200;

// Latest quote per symbol, shared by every page/table.
const liveQuoteCache = new Map();

// Symbols rendered on the current DOM (market cards, watchlist, tables, ...).
let liveDomSymbols = new Set();
let lastWsSubscriptionKey = '';
let lastWsMessageAt = 0;

function getLiveQuote(symbol) {
    return liveQuoteCache.get(normalizeSymbol(symbol));
}

function cacheLiveQuotes(prices) {
    Object.entries(prices || {}).forEach(([symbol, quote]) => {
        const price = Number(quote && quote.price);
        if (!Number.isFinite(price) || price <= 0) return;
        liveQuoteCache.set(normalizeSymbol(symbol), {
            price: price,
            change: Number(quote.change) || 0,
            changePercent: Number(quote.changePercent) || 0
        });
    });
}

function collectLiveDomSymbols() {
    const ordered = new Set();
    const addFrom = (root) => {
        if (!root) return;
        root.querySelectorAll('[data-live-symbol]').forEach(el => {
            const symbol = normalizeSymbol(el.getAttribute('data-live-symbol'));
            if (symbol) ordered.add(symbol);
        });
    };

    // Prioritise the visible tab, then keep remaining rendered tabs live too.
    const activeTab = document.querySelector('.tab-content.active');
    addFrom(activeTab);
    document.querySelectorAll('.tab-content').forEach(tab => {
        if (tab !== activeTab) addFrom(tab);
    });
    return ordered;
}

function buildWsSymbolList() {
    const symbols = new Set(WS_INDEX_SYMBOLS);
    chartWsSymbols.forEach(s => symbols.add(normalizeSymbol(s)));
    liveDomSymbols.forEach(s => symbols.add(normalizeSymbol(s)));
    return Array.from(symbols).filter(Boolean).slice(0, WS_MAX_SYMBOLS);
}

// Send the full subscription (indices + chart + everything rendered on-page).
// Returns true when the socket is open and the message was sent.
function sendWsSubscription(force = false) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;

    const symbols = buildWsSymbolList();
    const key = symbols.join('|');
    if (!force && key === lastWsSubscriptionKey) return true;

    lastWsSubscriptionKey = key;
    ws.send(JSON.stringify({ symbols: symbols }));
    console.log('[WS] Subscribed to', symbols.length, 'symbols:', symbols);
    return true;
}

function refreshLiveSubscriptions() {
    liveDomSymbols = collectLiveDomSymbols();
    sendWsSubscription();
}

function connectWebSocket() {
    // Don't open a second socket if one is already open/connecting.
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        return;
    }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/live-prices`;
    ws = new WebSocket(wsUrl);

    ws.onopen = function() {
        console.log('[WS] Connected to live prices');
        wsReconnectAttempts = 0;
        lastWsMessageAt = Date.now();
        updateConnectionStatus('connected');
        lastWsSubscriptionKey = '';
        // Pick up everything already rendered on the page before subscribing.
        liveDomSymbols = collectLiveDomSymbols();
        sendWsSubscription(true);
        if (chartWsSymbols.size > 0) setChartWsStatus('connecting');
    };

    ws.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            if (data.prices) {
                lastWsMessageAt = Date.now();
                cacheLiveQuotes(data.prices);
                updateMarketOverviewLive(data.prices);
                updateMarketPulseFromLiveQuotes();

                // Also update chart if it's showing this symbol
                Object.entries(data.prices).forEach(([symbol, q]) => {
                    if (chartWsSymbols.has(symbol)) {
                        updateChartLivePrice(symbol, q.price, q.change, q.changePercent);
                    }
                });

                // Refresh every table/card rendered with data-live-* hooks
                applyLiveDomQuotes();
            }
        } catch (e) {
            console.error('[WS] Parse error:', e);
        }
    };

    ws.onclose = function() {
        console.log('[WS] Disconnected');
        updateConnectionStatus('disconnected');
        setChartWsStatus('offline');
        lastWsSubscriptionKey = '';
        if (wsReconnectAttempts < MAX_WS_RECONNECT) {
            wsReconnectAttempts++;
            const delay = 3000 * wsReconnectAttempts;
            console.log(`[WS] Reconnecting in ${delay / 1000}s (attempt ${wsReconnectAttempts}/${MAX_WS_RECONNECT})`);
            setTimeout(connectWebSocket, delay);
        } else {
            console.log('[WS] Max reconnect attempts reached');
            updateConnectionStatus('error');
        }
    };

    ws.onerror = function() {
        console.log('[WS] Error');
        updateConnectionStatus('error');
        setChartWsStatus('error');
    };
}

// REST fallback for live quotes. If the WebSocket cannot deliver (proxy
// blocking WS, extension, server restart, tab left open for days), batch-poll
// the same symbols so prices still populate on every page.
let liveFallbackTimer = null;
let liveFallbackInFlight = false;

function startLivePriceFallback() {
    if (liveFallbackTimer) return;
    liveFallbackTimer = setInterval(async () => {
        const wsHealthy = ws && ws.readyState === WebSocket.OPEN &&
            (Date.now() - lastWsMessageAt) < 12000;
        if (wsHealthy || liveFallbackInFlight) return;

        liveDomSymbols = collectLiveDomSymbols();
        const symbols = buildWsSymbolList();
        if (!symbols.length) return;

        liveFallbackInFlight = true;
        try {
            const data = await api(
                `/api/market/quotes?symbols=${encodeURIComponent(symbols.join(','))}`
            );
            if (data && data.prices) {
                cacheLiveQuotes(data.prices);
                updateMarketOverviewLive(data.prices);
                updateMarketPulseFromLiveQuotes();
                applyLiveDomQuotes();
            }
        } catch (err) {
            // Silent: the WebSocket reconnect path keeps trying too.
        } finally {
            liveFallbackInFlight = false;
        }
    }, 8000);
}

function updateMarketOverviewLive(prices) {
    // Map symbols to DOM element IDs and labels
    const indexMap = {
        '^NSEI':    { priceEl: 'wsNiftyPrice',    changeEl: 'wsNiftyChange',    name: 'NIFTY 50' },
        '^BSESN':   { priceEl: 'wsSensexPrice',   changeEl: 'wsSensexChange',   name: 'SENSEX' },
        '^NSEBANK': { priceEl: 'wsBankniftyPrice', changeEl: 'wsBankniftyChange', name: 'BANKNIFTY' },
        '^CNXIT':   { priceEl: 'wsNiftyItPrice',   changeEl: 'wsNiftyItChange',   name: 'NIFTY IT' },
        '^NSEMDCP50': { priceEl: 'wsNiftyMidcapPrice', changeEl: 'wsNiftyMidcapChange', name: 'NIFTY MIDCAP 100' }
    };

    for (const [symbol, mapping] of Object.entries(indexMap)) {
        const priceData = prices[symbol];
        if (!priceData) continue;

        const priceEl = document.getElementById(mapping.priceEl);
        const changeEl = document.getElementById(mapping.changeEl);

        if (priceEl) {
            const oldPriceText = priceEl.textContent.replace(/[₹,%]/g, '').trim();
            const oldPrice = parseFloat(oldPriceText) || 0;
            const newPrice = priceData.price;

            priceEl.textContent = `₹${Number(newPrice).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

            // Flash animation on price change
            if (oldPrice > 0 && newPrice !== oldPrice) {
                flashElement(priceEl, newPrice > oldPrice ? 'flash-green' : 'flash-red');
            }
        }

        if (changeEl) {
            const sign = priceData.change >= 0 ? '+' : '';
            changeEl.textContent = `${sign}${Number(priceData.change).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (${sign}${priceData.changePercent}%)`;
            changeEl.classList.toggle('positive', priceData.change >= 0);
            changeEl.classList.toggle('negative', priceData.change < 0);
        }
    }

    // Also update the topbar live price for the currently selected stock if we have data
    const currentSym = normalizeSymbol(currentSymbol);
    if (prices[currentSym]) {
        const priceData = prices[currentSym];
        const livePriceEl = document.getElementById('livePrice');
        if (livePriceEl) {
            livePriceEl.textContent = `₹${Number(priceData.price).toFixed(2)}`;
            livePriceEl.className = 'price-badge ' + (priceData.change >= 0 ? 'positive' : 'negative');
        }
    }
}

// Apply cached WebSocket quotes to every element marked with data-live-*.
// Markup convention:
//   data-live-symbol="TCS.NS" on the card/row container
//   data-live-price / data-live-change / data-live-change-pct inside it
//   data-live-pnl + data-live-qty + data-live-buy for holdings
function applyLiveDomQuotes(root = document) {
    root.querySelectorAll('[data-live-symbol]').forEach(container => {
        const quote = getLiveQuote(container.getAttribute('data-live-symbol'));
        if (!quote) return;

        const priceEl = container.querySelector('[data-live-price]');
        if (priceEl) {
            const oldPrice = parseFloat((priceEl.textContent || '').replace(/[₹,%]/g, '').trim());
            const newText = fmtPrice(quote.price);
            if (priceEl.textContent !== newText) {
                priceEl.textContent = newText;
                if (Number.isFinite(oldPrice) && oldPrice > 0 && quote.price !== oldPrice) {
                    flashElement(priceEl, quote.price > oldPrice ? 'flash-green' : 'flash-red');
                }
            }
        }

        const changeEl = container.querySelector('[data-live-change]');
        if (changeEl) {
            const sign = quote.change >= 0 ? '+' : '';
            changeEl.textContent = `${sign}${Number(quote.change).toFixed(2)} (${sign}${Number(quote.changePercent).toFixed(2)}%)`;
            changeEl.classList.toggle('positive', quote.change >= 0);
            changeEl.classList.toggle('negative', quote.change < 0);
        }

        const pctEl = container.querySelector('[data-live-change-pct]');
        if (pctEl) {
            const sign = quote.changePercent >= 0 ? '+' : '';
            pctEl.textContent = `${sign}${Number(quote.changePercent).toFixed(2)}%`;
            pctEl.classList.toggle('positive', quote.changePercent >= 0);
            pctEl.classList.toggle('negative', quote.changePercent < 0);
        }

        const dayEl = container.querySelector('[data-live-daypnl]');
        if (dayEl) {
            const qty = parseFloat(container.getAttribute('data-live-qty'));
            if (Number.isFinite(qty)) {
                const dayPnl = (quote.change || 0) * qty;
                const pct = Number(quote.changePercent || 0);
                dayEl.textContent = `${dayPnl >= 0 ? '+' : '-'}₹${Math.abs(dayPnl).toFixed(2)} (${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%)`;
                dayEl.classList.toggle('positive', dayPnl >= 0);
                dayEl.classList.toggle('negative', dayPnl < 0);
            }
        }

        const pnlEl = container.querySelector('[data-live-pnl]');
        if (pnlEl) {
            const qty = parseFloat(container.getAttribute('data-live-qty'));
            const buy = parseFloat(container.getAttribute('data-live-buy'));
            if (Number.isFinite(qty) && Number.isFinite(buy) && buy > 0) {
                const pnl = (quote.price - buy) * qty;
                const pnlPct = ((quote.price - buy) / buy) * 100;
                pnlEl.textContent = `${pnl >= 0 ? '+' : '-'}₹${Math.abs(pnl).toFixed(2)} (${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%)`;
                pnlEl.classList.toggle('positive', pnl >= 0);
                pnlEl.classList.toggle('negative', pnl < 0);
            }
        }
    });

    // Keep the Analytics summary + dashboard portfolio card in sync.
    if (root === document) {
        updateAnalyticsLive();
        updateDashboardPortfolioValue();
        updatePortfolioSummaryBar();
    }
}

function flashElement(el, className) {
    el.classList.remove('flash-green', 'flash-red');
    void el.offsetWidth; // Force reflow to restart animation
    el.classList.add(className);
    setTimeout(() => el.classList.remove(className), 1000);
}

function updateConnectionStatus(status) {
    const indicator = document.getElementById('wsStatus');
    if (indicator) {
        indicator.className = `ws-status ws-${status}`;
        indicator.title = `WebSocket: ${status}`;
    }
    // Update the live indicator text in sidebar (the second span, after the pulse)
    const liveText = document.querySelector('.live-indicator span:nth-child(2)');
    if (liveText) {
        if (status === 'connected') {
            liveText.textContent = 'Live Mode';
        } else if (status === 'disconnected') {
            liveText.textContent = 'Reconnecting...';
        } else {
            liveText.textContent = 'Offline';
        }
    }
}

// Market Status Bar
async function updateMarketStatus() {
    try {
        const data = await api('/api/market/status');
        const dot = document.getElementById('marketStatusDot');
        const text = document.getElementById('marketStatusText');
        if (dot && text) {
            dot.className = 'status-dot status-' + data.status.toLowerCase();
            text.textContent = data.message;
        }
    } catch (e) {
        console.error('Market status error:', e);
    }
}

// Market Pulse
function applyMarketPulse(score, label, color) {
    const pulseValue = document.getElementById('pulseValue');
    const gaugeScore = document.getElementById('gaugeScore');
    const gaugeText = document.getElementById('gaugeText');
    const needle = document.getElementById('gaugeNeedle');

    if (pulseValue) pulseValue.textContent = `${score} - ${label}`;
    if (gaugeScore) gaugeScore.textContent = score;
    if (gaugeText) {
        gaugeText.textContent = label;
        gaugeText.style.color = color || '#ffaa00';
    }
    if (needle) {
        // Rotate needle: -90deg (bearish) to +90deg (bullish)
        const rotation = (score / 100) * 90;
        needle.style.transform = `rotate(${rotation}deg)`;
    }
}

function updateMarketPulseFromLiveQuotes() {
    const changes = WS_INDEX_SYMBOLS
        .map(symbol => getLiveQuote(symbol))
        .filter(Boolean)
        .map(quote => quote.changePercent);

    if (changes.length === 0) return;

    const avgChange = changes.reduce((sum, value) => sum + value, 0) / changes.length;
    const score = Math.round(Math.min(100, Math.max(0, 50 + avgChange * 25)));
    let label = 'Neutral';
    let color = '#f59e0b';
    if (score >= 65) {
        label = 'Bullish';
        color = '#10b981';
    } else if (score <= 35) {
        label = 'Bearish';
        color = '#ef4444';
    }
    applyMarketPulse(score, label, color);
}

async function updateMarketPulse() {
    try {
        const data = await api('/api/market/pulse');
        applyMarketPulse(data.score, data.label, data.color);
    } catch (e) {
        console.error('Market pulse error:', e);
    }
}

// Live clock
function updateClock() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const el = document.getElementById('currentTime');
    if (el) el.textContent = timeStr;
}

// ===== OPTION CHAIN =====
let optionChainRefreshInterval = null;

// ===== MARKET DEPTH =====
async function loadMarketDepth(symbol) {
    if (!symbol) return showToast('Enter a stock symbol', 'warning');
    try {
        const response = await fetch(`/api/market/depth/${encodeURIComponent(symbol)}`);
        const data = await response.json();

        if (data.error) {
            console.error('Market depth error:', data.error);
            showToast(`Depth error: ${data.error}`, 'error');
            return;
        }

        // Update symbol
        const symbolEl = document.getElementById('depthSymbol');
        if (symbolEl) symbolEl.textContent = symbol;

        // Update bids (highest first, already sorted descending)
        const bidsContainer = document.getElementById('depthBids');
        if (bidsContainer) {
            bidsContainer.innerHTML = data.bids.map(bid => `
                <div class="depth-row bid-row">
                    <span class="depth-price">${bid.price}</span>
                    <span class="depth-qty">${bid.quantity.toLocaleString()}</span>
                    <span class="depth-orders">${bid.orders}</span>
                </div>
            `).join('');
        }

        // Update asks (lowest first, already sorted ascending)
        const asksContainer = document.getElementById('depthAsks');
        if (asksContainer) {
            asksContainer.innerHTML = data.asks.map(ask => `
                <div class="depth-row ask-row">
                    <span class="depth-price">${ask.price}</span>
                    <span class="depth-qty">${ask.quantity.toLocaleString()}</span>
                    <span class="depth-orders">${ask.orders}</span>
                </div>
            `).join('');
        }

        // Update totals and spread
        document.getElementById('totalBidQty').textContent = data.totalBidQty.toLocaleString();
        document.getElementById('totalAskQty').textContent = data.totalAskQty.toLocaleString();
        document.getElementById('spreadValue').textContent = `₹${data.spread}`;
        document.getElementById('bidAskRatio').textContent = data.bidAskRatio;

        // Color code ratio
        const ratioEl = document.getElementById('bidAskRatio');
        if (ratioEl) {
            ratioEl.className = `ratio-value ${data.bidAskRatio > 1.2 ? 'positive' : (data.bidAskRatio < 0.8 ? 'negative' : '')}`;
        }

    } catch (error) {
        console.error('Error loading market depth:', error);
    }
}

// ===== VOLUME ALERTS =====
async function loadVolumeAlerts() {
    try {
        const response = await fetch('/api/market/volume-alerts');
        const data = await response.json();

        const container = document.getElementById('volumeAlertsList');
        const countBadge = document.getElementById('volumeAlertCount');

        if (!container) return;

        if (data.alerts && data.alerts.length > 0) {
            if (countBadge) countBadge.textContent = data.alerts.length;
            container.innerHTML = data.alerts.map(alert => `
                <div class="volume-alert-item ${alert.signal.toLowerCase()}" data-live-symbol="${normalizeSymbol(alert.symbol)}">
                    <div class="alert-left">
                        <span class="alert-symbol" onclick="selectStock('${alert.symbol}.NS'); showTab('chart')" style="cursor:pointer">${alert.symbol}</span>
                        <span class="alert-price" data-live-price>₹${alert.price}</span>
                    </div>
                    <div class="alert-center">
                        <span class="alert-change ${alert.change >= 0 ? 'positive' : 'negative'}" data-live-change-pct>
                            ${alert.change >= 0 ? '+' : ''}${alert.change}%
                        </span>
                    </div>
                    <div class="alert-right">
                        <span class="alert-volume">${alert.volumeRatio}x avg</span>
                        <span class="alert-signal signal-${alert.signal.toLowerCase()}">${alert.signal}</span>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div class="no-data">No unusual volume detected</div>';
            if (countBadge) countBadge.textContent = '0';
        }

        refreshLiveSubscriptions();
        applyLiveDomQuotes();
    } catch (error) {
        console.error('Error loading volume alerts:', error);
    }
}

// ===== AUTO-REFRESH GAINERS/LOSERS =====
function startAutoRefreshGainersLosers() {
    // Ensure the WS socket is connected and subscribed so that
    // liveQuoteCache gets populated with top-movers symbols.
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        connectWebSocket();
    }
    // No setInterval needed — WebSocket ticks every ~3s will
    // refresh the DOM quotes via the existing applyLiveDomQuotes() path.
    // The old 60s interval is removed — gainers/losers now update live
    // automatically through the shared liveQuoteCache.
}

// ===== PORTFOLIO LIVE P&L TICKER =====
let portfolioTickerInterval = null;

async function loadPortfolioTicker() {
    try {
        const data = await api('/api/portfolio/live-pnl');
        const holdings = data.holdings || [];

        // Feed the same live pipeline the Analytics section uses so the
        // dashboard Portfolio Holdings card ticks with the WebSocket too.
        analyticsLiveHoldings = holdings.map(h => ({
            symbol: h.symbol,
            quantity: h.quantity,
            buyPrice: h.buyPrice,
            currentPrice: h.currentPrice,
            dayChangePnl: h.dayChangePnl
        }));
        updateDashboardPortfolioValue();

        const ticker = document.getElementById('tickerContent');
        if (!ticker || holdings.length === 0) return;

        // Create scrolling ticker content
        const tickerItems = holdings.map(h => `
            <span class="ticker-item" onclick="selectStock('${h.symbol}'); showTab('chart')" style="cursor:pointer">
                <span class="ticker-symbol">${h.symbol.replace('.NS', '')}</span>
                <span class="ticker-price">₹${h.currentPrice}</span>
                <span class="ticker-pnl ${h.pnl >= 0 ? 'positive' : 'negative'}">
                    ${h.pnl >= 0 ? '▲' : '▼'} ₹${Math.abs(h.pnl)} (${h.pnlPercent}%)
                </span>
            </span>
        `).join('');

        // Duplicate for seamless scroll
        ticker.innerHTML = tickerItems + tickerItems;

        // Subscribe portfolio symbols so WebSocket quotes start flowing.
        refreshLiveSubscriptions();
    } catch (error) {
        console.error('Error loading portfolio ticker:', error);
    }
}

// Dashboard "Portfolio Holdings" quick-stat card: total current value +
// total P&L, recomputed from liveQuoteCache on every WebSocket tick.
function updateDashboardPortfolioValue() {
    const valEl = document.getElementById('dashPortfolioVal');
    if (!valEl) return;
    const pnlEl = document.getElementById('dashPortfolioPnl');

    // #9b — allocation donut on the dashboard (re-rendered live, per tick).
    const allocCard = document.getElementById('dashAllocationCard');
    if (allocCard) {
        if (!analyticsLiveHoldings.length) {
            allocCard.style.display = 'none';
        } else {
            allocCard.style.display = '';
            renderAllocationDonut('dashAllocationDonut', 'dashAllocationLegend', analyticsLiveHoldings);
        }
    }

    if (!analyticsLiveHoldings.length) {
        valEl.textContent = '₹0.00';
        if (pnlEl) {
            pnlEl.textContent = 'No holdings yet';
            pnlEl.className = '';
        }
        return;
    }

    let invested = 0;
    let current = 0;
    let dayPnl = 0;
    analyticsLiveHoldings.forEach(h => {
        const qty = Number(h.quantity) || 0;
        const buy = Number(h.buyPrice) || 0;
        invested += qty * buy;
        const quote = getLiveQuote(h.symbol);
        current += (quote ? quote.price : (Number(h.currentPrice) || buy)) * qty;
        dayPnl += quote ? (quote.change || 0) * qty : (Number(h.dayChangePnl) || 0);
    });
    const pnl = current - invested;

    valEl.textContent = `₹${(Math.round(current * 100) / 100).toLocaleString()}`;
    if (pnlEl) {
        const n = analyticsLiveHoldings.length;
        pnlEl.innerHTML = `<span class="${pnl >= 0 ? 'positive' : 'negative'}">${pnl >= 0 ? '+' : '-'}₹${Math.abs(Math.round(pnl * 100) / 100).toLocaleString()}</span>` +
            ` · <span class="${dayPnl >= 0 ? 'positive' : 'negative'}">${dayPnl >= 0 ? '+' : '-'}₹${Math.abs(Math.round(dayPnl * 100) / 100).toLocaleString()} today</span>` +
            ` · ${n} stock${n > 1 ? 's' : ''}`;
    }
}

function startPortfolioTicker() {
    loadPortfolioTicker();
    portfolioTickerInterval = setInterval(loadPortfolioTicker, 30000); // Every 30 seconds
}

// ===== HTML ESCAPE HELPER =====
function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// ===== AI INTELLIGENCE DESK (SENTINEL) =====
let sentinelWs = null;
let sentinelWsReconnectTimer = null;
let sentinelAudioCtx = null;
let sentinelAlerts = [];
let sentinelDigests = [];
let sentinelCurrentFilter = 'ALL';

// --- Web Audio Chime Synthesis ---
function playSentinelAudioChime() {
    try {
        const chimeEnabled = localStorage.getItem('sentinel_audio_chime') !== 'false';
        if (!chimeEnabled) return;

        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextClass) return;

        if (!sentinelAudioCtx) {
            sentinelAudioCtx = new AudioContextClass();
        }
        if (sentinelAudioCtx.state === 'suspended') {
            sentinelAudioCtx.resume();
        }

        const now = sentinelAudioCtx.currentTime;

        // Tone 1: D5 (587.33 Hz) pleasant prompt
        const osc1 = sentinelAudioCtx.createOscillator();
        const gain1 = sentinelAudioCtx.createGain();
        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(587.33, now);
        gain1.gain.setValueAtTime(0.12, now);
        gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
        osc1.connect(gain1);
        gain1.connect(sentinelAudioCtx.destination);
        osc1.start(now);
        osc1.stop(now + 0.15);

        // Tone 2: A5 (880 Hz) harmonic chime
        const osc2 = sentinelAudioCtx.createOscillator();
        const gain2 = sentinelAudioCtx.createGain();
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(880.0, now + 0.12);
        gain2.gain.setValueAtTime(0.15, now + 0.12);
        gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
        osc2.connect(gain2);
        gain2.connect(sentinelAudioCtx.destination);
        osc2.start(now + 0.12);
        osc2.stop(now + 0.35);
    } catch (e) {
        console.warn('Sentinel audio chime error:', e);
    }
}

function toggleSentinelAudio() {
    const current = localStorage.getItem('sentinel_audio_chime') !== 'false';
    const next = !current;
    localStorage.setItem('sentinel_audio_chime', next ? 'true' : 'false');
    updateSentinelAudioUI();
    if (next) {
        playSentinelAudioChime();
        showToast('Sentinel audio chime enabled', 'info');
    } else {
        showToast('Sentinel audio alerts muted', 'info');
    }
}

function updateSentinelAudioUI() {
    const isEnabled = localStorage.getItem('sentinel_audio_chime') !== 'false';
    const icon = document.getElementById('sentinelAudioIcon');
    const text = document.getElementById('sentinelAudioText');
    const btn = document.getElementById('sentinelAudioToggle');
    if (icon) icon.textContent = isEnabled ? '🔊' : '🔇';
    if (text) text.textContent = isEnabled ? 'ON' : 'MUTED';
    if (btn) {
        if (isEnabled) {
            btn.classList.remove('muted');
        } else {
            btn.classList.add('muted');
        }
    }
}

// --- WebSocket Management ---
function initSentinelWebSocket() {
    if (sentinelWs && (sentinelWs.readyState === WebSocket.OPEN || sentinelWs.readyState === WebSocket.CONNECTING)) {
        return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/sentinel`;

    const wsBadge = document.getElementById('sentinelWsBadge');
    if (wsBadge) {
        wsBadge.textContent = 'WS: Connecting...';
        wsBadge.className = 'badge neutral';
    }

    try {
        sentinelWs = new WebSocket(wsUrl);

        sentinelWs.onopen = () => {
            if (wsBadge) {
                wsBadge.textContent = 'WS: Live Connected';
                wsBadge.className = 'badge positive';
            }
            if (sentinelWsReconnectTimer) {
                clearTimeout(sentinelWsReconnectTimer);
                sentinelWsReconnectTimer = null;
            }
        };

        sentinelWs.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'SENTINEL_ALERT' && msg.alert) {
                    onSentinelAlertReceived(msg.alert);
                } else if (msg.type === 'SENTINEL_DIGEST' && msg.digest) {
                    onSentinelDigestReceived(msg.digest);
                }
            } catch (err) {
                console.error('Error parsing Sentinel WS message:', err);
            }
        };

        sentinelWs.onclose = () => {
            if (wsBadge) {
                wsBadge.textContent = 'WS: Reconnecting...';
                wsBadge.className = 'badge negative';
            }
            scheduleSentinelWsReconnect();
        };

        sentinelWs.onerror = () => {
            if (wsBadge) {
                wsBadge.textContent = 'WS: Error';
                wsBadge.className = 'badge negative';
            }
            sentinelWs.close();
        };
    } catch (e) {
        console.error('Failed to create Sentinel WebSocket:', e);
        scheduleSentinelWsReconnect();
    }
}

function scheduleSentinelWsReconnect() {
    if (sentinelWsReconnectTimer) return;
    sentinelWsReconnectTimer = setTimeout(() => {
        sentinelWsReconnectTimer = null;
        initSentinelWebSocket();
    }, 5000);
}

function onSentinelAlertReceived(alert) {
    const existingIdx = sentinelAlerts.findIndex(a => a.id === alert.id);
    if (existingIdx >= 0) {
        sentinelAlerts[existingIdx] = alert;
    } else {
        sentinelAlerts.unshift(alert);
    }
    sentinelAlerts = sentinelAlerts.slice(0, 100);

    playSentinelAudioChime();

    const toastType = alert.severity === 'CRITICAL' ? 'negative' : (alert.severity === 'HIGH' ? 'warning' : 'info');
    showToast(`🧠 Sentinel Alert [${alert.symbol.replace('.NS', '')}]: ${alert.title}`, toastType);

    renderSentinelFeed();
}

function onSentinelDigestReceived(digest) {
    const existingIdx = sentinelDigests.findIndex(d => d.id === digest.id);
    if (existingIdx >= 0) {
        sentinelDigests[existingIdx] = digest;
    } else {
        sentinelDigests.unshift(digest);
    }
    sentinelDigests = sentinelDigests.slice(0, 30);

    showToast(`📰 Market Routine Digest: ${digest.title}`, 'info');
    renderSentinelDigests();
}

// --- Live Feed ---
async function loadSentinelFeed() {
    const feedContainer = document.getElementById('sentinelAlertFeed');
    if (!feedContainer) return;

    try {
        const res = await api('/api/sentinel/feed');
        if (res && res.alerts) {
            sentinelAlerts = res.alerts;
            renderSentinelFeed();
        } else {
            feedContainer.innerHTML = '<p class="placeholder">No sentinel alerts recorded yet. Surveillance engine is active.</p>';
        }
    } catch (e) {
        console.error('Error loading sentinel feed:', e);
        feedContainer.innerHTML = '<p class="placeholder">Error loading intelligence feed.</p>';
    }
}

function filterSentinelFeed(severity, btn) {
    sentinelCurrentFilter = severity;
    const parent = btn?.parentElement;
    if (parent) {
        parent.querySelectorAll('.timeframe-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    }
    renderSentinelFeed();
}

function renderSentinelFeed() {
    const feedContainer = document.getElementById('sentinelAlertFeed');
    const countBadge = document.getElementById('sentinelAlertCountBadge');
    if (!feedContainer) return;

    const filtered = sentinelAlerts.filter(a => {
        if (sentinelCurrentFilter === 'ALL') return true;
        return a.severity === sentinelCurrentFilter;
    });

    if (countBadge) {
        countBadge.textContent = `${filtered.length} Alert${filtered.length === 1 ? '' : 's'}`;
        countBadge.className = `badge ${filtered.length > 0 ? 'positive' : 'neutral'}`;
    }

    if (!filtered || filtered.length === 0) {
        feedContainer.innerHTML = `<p class="placeholder">No ${sentinelCurrentFilter === 'ALL' ? '' : sentinelCurrentFilter.toLowerCase()} alerts in feed. Surveillance engine is actively monitoring.</p>`;
        return;
    }

    feedContainer.innerHTML = filtered.map(alert => renderSentinelAlertCard(alert)).join('');
}

function renderSentinelAlertCard(alert) {
    const severityClass = alert.severity === 'CRITICAL' ? 'severity-critical' : (alert.severity === 'HIGH' ? 'severity-high' : 'severity-info');
    const cleanSym = (alert.symbol || '').replace('.NS', '');
    const analysis = alert.analysis || {};
    const findings = alert.findings || [];

    return `
        <div class="sentinel-alert-card ${severityClass}" id="card_${alert.id}">
            <div class="sentinel-card-header">
                <div class="sentinel-header-left">
                    <span class="sentinel-symbol-pill" onclick="selectStock('${alert.symbol}'); showTab('chart');" title="Click to view chart on dashboard">
                        ${cleanSym}
                    </span>
                    <span class="sentinel-severity-badge ${severityClass}">${alert.severity}</span>
                    <h4 class="sentinel-card-title">${escapeHtml(alert.title)}</h4>
                </div>
                <div class="sentinel-header-right">
                    <span class="sentinel-time">${alert.created_at || alert.data_as_of || ''}</span>
                </div>
            </div>

            <p class="sentinel-summary">${escapeHtml(alert.summary)}</p>

            <!-- Bull vs Bear Meter & Consensus -->
            ${renderBullBearMeter(analysis)}

            <!-- Bull vs Bear Breakdown Grid -->
            <div class="sentinel-dossier-grid">
                <div class="sentinel-case-box bull-case-box">
                    <div class="case-header">
                        <span class="case-icon">🐂</span>
                        <strong>Bull Thesis</strong>
                    </div>
                    <p class="case-text">${escapeHtml(analysis.bull_case || 'No bull catalysts recorded.')}</p>
                    ${analysis.bull_catalysts && analysis.bull_catalysts.length > 0 ? `
                        <div class="catalyst-tags">
                            ${analysis.bull_catalysts.map(c => `<span class="catalyst-tag bull-tag">▲ ${escapeHtml(c)}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>

                <div class="sentinel-case-box bear-case-box">
                    <div class="case-header">
                        <span class="case-icon">🐻</span>
                        <strong>Bear Thesis</strong>
                    </div>
                    <p class="case-text">${escapeHtml(analysis.bear_case || 'No bear risks recorded.')}</p>
                    ${analysis.bear_risks && analysis.bear_risks.length > 0 ? `
                        <div class="catalyst-tags">
                            ${analysis.bear_risks.map(r => `<span class="catalyst-tag bear-tag">▼ ${escapeHtml(r)}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>
            </div>

            <!-- Key Levels & Strategic Target -->
            <div class="sentinel-levels-row">
                <div class="level-item">
                    <span class="level-label">Key Support:</span>
                    <span class="level-value">${analysis.key_support != null ? '₹' + Number(analysis.key_support).toFixed(2) : 'N/A'}</span>
                </div>
                <div class="level-item">
                    <span class="level-label">Invalidation (SL):</span>
                    <span class="level-value stop-loss">${analysis.invalidation_level != null ? '₹' + Number(analysis.invalidation_level).toFixed(2) : 'N/A'}</span>
                </div>
                <div class="level-item">
                    <span class="level-label">Target Resistance:</span>
                    <span class="level-value target-price">${analysis.target_resistance != null ? '₹' + Number(analysis.target_resistance).toFixed(2) : 'N/A'}</span>
                </div>
            </div>

            <!-- Specialist Desk Findings -->
            ${findings.length > 0 ? `
                <div class="sentinel-findings-section">
                    <div class="findings-header">
                        <span class="findings-title">Specialist Desk Evidence (${findings.length})</span>
                    </div>
                    <div class="findings-list">
                        ${findings.map(f => renderDeskFinding(f)).join('')}
                    </div>
                </div>
            ` : ''}

            <!-- Card Footer Actions -->
            <div class="sentinel-card-footer">
                <button class="btn-sm btn-primary" onclick="selectStock('${alert.symbol}'); showTab('chart');">
                    📈 View Chart
                </button>
                <button class="btn-sm btn-secondary" onclick="investigateSymbolSentinel('${alert.symbol}')">
                    🔬 Deep Re-Scan
                </button>
                <button class="btn-sm btn-secondary" onclick="addToWatchlist('${alert.symbol}')">
                    + Watchlist
                </button>
            </div>
        </div>
    `;
}

function renderBullBearMeter(analysis) {
    if (!analysis) return '';

    const bias = analysis.consensus_bias || 'NEUTRAL';
    const confidence = Math.min(100, Math.max(0, analysis.confidence_score ?? 50));

    let biasLabel = bias.replace(/_/g, ' ');
    let biasClass = 'neutral';
    let bullRatio = 50;

    if (bias === 'STRONG_BULLISH') {
        biasClass = 'positive';
        bullRatio = Math.max(65, confidence);
    } else if (bias === 'MODERATE_BULLISH') {
        biasClass = 'positive';
        bullRatio = Math.max(55, Math.round(50 + confidence / 4));
    } else if (bias === 'STRONG_BEARISH') {
        biasClass = 'negative';
        bullRatio = Math.min(35, 100 - confidence);
    } else if (bias === 'MODERATE_BEARISH') {
        biasClass = 'negative';
        bullRatio = Math.min(45, Math.round(50 - confidence / 4));
    } else {
        bullRatio = 50;
        biasClass = 'neutral';
    }

    const bearRatio = 100 - bullRatio;

    return `
        <div class="bull-bear-meter-container">
            <div class="meter-header">
                <div class="consensus-label">
                    <span>Consensus Bias:</span>
                    <strong class="bias-badge ${biasClass}">${biasLabel}</strong>
                </div>
                <div class="confidence-label">
                    <span>Confidence Score:</span>
                    <strong>${confidence}%</strong>
                </div>
            </div>
            <div class="bull-bear-meter">
                <div class="meter-bar bull-bar" style="width: ${bullRatio}%;">
                    ${bullRatio >= 20 ? `<span>Bull ${bullRatio}%</span>` : ''}
                </div>
                <div class="meter-bar bear-bar" style="width: ${bearRatio}%;">
                    ${bearRatio >= 20 ? `<span>Bear ${bearRatio}%</span>` : ''}
                </div>
            </div>
        </div>
    `;
}

function renderDeskFinding(finding) {
    const desk = finding.desk || 'GENERAL';
    const deskIcon = {
        'ACTIVITY': '⚡',
        'TECHNICAL': '📐',
        'NEWS': '📰',
        'FUNDAMENTALS': '📊'
    }[desk] || '◈';

    const sigClass = finding.significance === 'CRITICAL' ? 'sig-critical' : (finding.significance === 'HIGH' ? 'sig-high' : 'sig-medium');

    const metricsStr = finding.metrics && Object.keys(finding.metrics).length > 0
        ? Object.entries(finding.metrics).map(([k, v]) => `<span class="metric-pill"><strong>${escapeHtml(k)}:</strong> ${escapeHtml(String(v))}</span>`).join(' ')
        : '';

    return `
        <div class="desk-finding-item">
            <div class="finding-top">
                <span class="desk-badge desk-${desk.toLowerCase()}">${deskIcon} ${desk} DESK</span>
                <span class="significance-badge ${sigClass}">${finding.significance}</span>
                <span class="finding-headline">${escapeHtml(finding.headline)}</span>
            </div>
            ${metricsStr ? `<div class="finding-metrics">${metricsStr}</div>` : ''}
        </div>
    `;
}

// --- Routine Digests ---
async function loadSentinelDigests() {
    const container = document.getElementById('sentinelDigestsContainer');
    if (!container) return;

    try {
        const res = await api('/api/sentinel/digests');
        if (res && res.digests) {
            sentinelDigests = res.digests;
            renderSentinelDigests();
        } else {
            container.innerHTML = '<p class="placeholder">No routine briefings recorded yet.</p>';
        }
    } catch (e) {
        console.error('Error loading sentinel digests:', e);
        container.innerHTML = '<p class="placeholder">Error loading routine digests.</p>';
    }
}

function renderSentinelDigests() {
    const container = document.getElementById('sentinelDigestsContainer');
    if (!container) return;

    if (!sentinelDigests || sentinelDigests.length === 0) {
        container.innerHTML = '<p class="placeholder">No scheduled briefings yet. Click any routine button above to generate on-demand.</p>';
        return;
    }

    container.innerHTML = sentinelDigests.map(d => renderSentinelDigestCard(d)).join('');
}

function renderSentinelDigestCard(d) {
    const routineIcon = {
        'PRE_MARKET': '🌅',
        'MIDDAY_PULSE': '⚡',
        'POST_MARKET_WRAP': '📊'
    }[d.routine_type] || '📅';

    const routineName = {
        'PRE_MARKET': 'Pre-Market Briefing (08:30 IST)',
        'MIDDAY_PULSE': 'Midday Pulse (12:30 IST)',
        'POST_MARKET_WRAP': 'Post-Market Wrap (15:40 IST)'
    }[d.routine_type] || d.routine_type;

    return `
        <div class="routine-digest-box" id="digest_${d.id}">
            <div class="digest-header">
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                    <span class="routine-icon-badge">${routineIcon}</span>
                    <strong class="digest-type-label">${routineName}</strong>
                    <span class="digest-title-text">${escapeHtml(d.title)}</span>
                </div>
                <span class="digest-time">${d.timestamp || ''}</span>
            </div>

            <p class="digest-summary-text">${escapeHtml(d.summary)}</p>

            ${d.macro_cues && d.macro_cues.length > 0 ? `
                <div class="digest-section">
                    <span class="section-label">🌐 Macro & Global Cues:</span>
                    <div class="cues-list">
                        ${d.macro_cues.map(c => `<span class="cue-pill">◈ ${escapeHtml(c)}</span>`).join('')}
                    </div>
                </div>
            ` : ''}

            ${d.top_stocks_in_focus && d.top_stocks_in_focus.length > 0 ? `
                <div class="digest-section">
                    <span class="section-label">🎯 Key Stocks in Focus:</span>
                    <div class="focus-stocks-list">
                        ${d.top_stocks_in_focus.map(sym => `
                            <button class="focus-stock-btn" onclick="selectStock('${sym}'); showTab('chart');">
                                ${sym.replace('.NS', '')}
                            </button>
                        `).join('')}
                    </div>
                </div>
            ` : ''}

            ${((d.sector_leaders && d.sector_leaders.length > 0) || (d.sector_laggards && d.sector_laggards.length > 0)) ? `
                <div class="digest-sectors-row">
                    ${d.sector_leaders && d.sector_leaders.length > 0 ? `
                        <div class="sector-subgroup">
                            <span class="section-label positive">▲ Sector Leaders:</span>
                            <div class="sector-pills">
                                ${d.sector_leaders.map(s => `<span class="badge positive">${escapeHtml(s)}</span>`).join('')}
                            </div>
                        </div>
                    ` : ''}
                    ${d.sector_laggards && d.sector_laggards.length > 0 ? `
                        <div class="sector-subgroup">
                            <span class="section-label negative">▼ Sector Laggards:</span>
                            <div class="sector-pills">
                                ${d.sector_laggards.map(s => `<span class="badge negative">${escapeHtml(s)}</span>`).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            ` : ''}
        </div>
    `;
}

// --- On-Demand Stock Investigation ---
async function investigateSymbolSentinel(symbol) {
    const input = document.getElementById('sentinelSymbolInput');
    const sym = (symbol || input?.value || '').trim().toUpperCase();
    if (!sym) {
        showToast('Please enter a valid stock symbol', 'warning');
        return;
    }

    const formattedSym = sym.includes('.') || sym.startsWith('^') ? sym : `${sym}.NS`;
    if (input) input.value = formattedSym;

    const resultContainer = document.getElementById('sentinelInvestigationResult');
    const btn = document.getElementById('sentinelInvestigateBtn');

    if (resultContainer) {
        resultContainer.style.display = 'block';
        resultContainer.innerHTML = `
            <div class="sentinel-scanning-state">
                <div class="spinner"></div>
                <div class="scan-progress-text">
                    <strong>Scanning ${formattedSym} Across 4 Specialist Desks...</strong>
                    <div class="desk-scan-indicators">
                        <span>⚡ Activity Desk</span> • <span>📐 Technical Desk</span> • <span>📰 News Desk</span> • <span>📊 Fundamentals Desk</span> • <span>🤖 Adversarial AI Synthesizer</span>
                    </div>
                </div>
            </div>
        `;
    }

    if (btn) btn.disabled = true;

    try {
        const alert = await api(`/api/sentinel/analyze/${encodeURIComponent(formattedSym)}`, {
            method: 'POST'
        });

        if (alert && alert.symbol) {
            resultContainer.innerHTML = `
                <div class="investigation-result-wrapper">
                    <div class="result-banner">
                        <span>🔬 Comprehensive Intelligence Dossier: <strong>${alert.symbol.replace('.NS', '')}</strong></span>
                        <span class="badge ${alert.severity === 'CRITICAL' ? 'negative' : (alert.severity === 'HIGH' ? 'warning' : 'positive')}">${alert.severity}</span>
                    </div>
                    ${renderSentinelAlertCard(alert)}
                </div>
            `;
            showToast(`Investigation complete for ${formattedSym}`, 'success');
        } else {
            resultContainer.innerHTML = `<p class="placeholder">Failed to generate intelligence dossier for ${formattedSym}. ${alert.error || ''}</p>`;
        }
    } catch (e) {
        console.error('Error investigating symbol:', e);
        if (resultContainer) {
            resultContainer.innerHTML = `<p class="placeholder">Error investigating ${formattedSym}: ${e.message}</p>`;
        }
    } finally {
        if (btn) btn.disabled = false;
    }
}

// --- Trigger Scheduled Routine Manually ---
async function triggerSentinelRoutine(routineType) {
    showToast(`Triggering ${routineType} routine...`, 'info');
    showLoading();
    try {
        const res = await api(`/api/sentinel/routine/${routineType}`, {
            method: 'POST'
        });
        hideLoading();
        if (res && res.message) {
            showToast(res.message, 'success');
            await loadSentinelDigests();
        } else {
            showToast(res.error || 'Failed to trigger routine', 'negative');
        }
    } catch (e) {
        hideLoading();
        console.error('Error triggering routine:', e);
        showToast('Error triggering routine: ' + e.message, 'negative');
    }
}

// Init - run immediately if DOM is already loaded (script at end of body), otherwise wait for DOMContentLoaded
function initApp() {
    // Theme auto-detection
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light') { document.body.classList.add('light-theme'); }
    else if (savedTheme === 'dark') { document.body.classList.remove('light-theme'); }
    else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
        document.body.classList.add('light-theme');
    }

    checkAuthStatus();

    initChart();

    const lastStock = localStorage.getItem('lastStock');
    const lastTab = localStorage.getItem('lastTab');

    if (lastStock) {
        currentSymbol = lastStock;
        document.getElementById('currentStockName').textContent = lastStock.replace('.NS', '');
        const chartInput = document.getElementById('chartSymbolInput');
        if (chartInput) chartInput.value = lastStock;
        localStorage.setItem('lastStock', lastStock);
    }

    if (lastTab) {
        showTab(lastTab);
    } else {
        loadChart();
    }

    loadDashboardGainersLosers();
    updateMarketStatus();
    updateMarketPulse();
    updateClock();
    setInterval(updateMarketStatus, 60000);   // Every minute
    setInterval(updateMarketPulse, 300000);   // Every 5 minutes
    setInterval(updateClock, 1000);           // Every second
    startLiveUpdates();
    startAutoRefreshGainersLosers();
    startLivePriceFallback();
    startPortfolioTicker();

    // Refresh volume alerts every 5 minutes
    setTimeout(() => {
        loadVolumeAlerts();
        setInterval(loadVolumeAlerts, 300000);
    }, 2000);

    // Connect WebSocket for live index prices
    setTimeout(connectWebSocket, 1000);

    // Initialize Sentinel AI Desk & Web Audio UI
    updateSentinelAudioUI();
    setTimeout(initSentinelWebSocket, 1500);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

async function showUpstoxSubTab(tabId, btn) {
    document.querySelectorAll('.upstox-sub-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.sub-nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    btn.classList.add('active');
}

// ===== TRADER DESK =====
// Sub-tab switching scoped to #traderdesk so it never fights the Upstox desk sub-nav
function showTraderSubTab(tabId, btn) {
    const desk = document.getElementById('traderdesk');
    if (!desk) return;
    desk.querySelectorAll('.td-sub-content').forEach(t => t.classList.remove('active'));
    desk.querySelectorAll('.td-sub-btn').forEach(b => b.classList.remove('active'));
    const pane = document.getElementById(tabId);
    if (pane) pane.classList.add('active');
    if (btn) btn.classList.add('active');
    if (tabId === 'td-orders') tdLoadSlips();
    if (tabId === 'td-entry') tdInitEntryTimer();
    if (tabId === 'td-alerts') tdInitAlerts();
}

// Session strip helpers (all times IST)
function _tdIstParts(date = new Date()) {
    const parts = new Intl.DateTimeFormat('en-GB', {
        timeZone: 'Asia/Kolkata',
        weekday: 'short', year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    }).formatToParts(date);
    const get = t => (parts.find(p => p.type === t) || {}).value;
    return {
        h: (parseInt(get('hour'), 10) || 0) % 24,
        m: parseInt(get('minute'), 10) || 0,
        s: parseInt(get('second'), 10) || 0,
        weekday: get('weekday') || '',
        dateStr: `${get('year')}-${get('month')}-${get('day')}`,
    };
}

const TD_ORB_START = 9 * 60 + 15;   // 09:15
const TD_ORB_END = 9 * 60 + 30;     // 09:30
const TD_ENTRY_END = 14 * 60 + 30;  // 14:30 (matches api/entry.py defaults)
const TD_FLAT_BY = 15 * 60 + 15;    // 15:15
const TD_SCAN_AT = 9 * 60 + 31;     // 09:31 scheduled ORB scan

function _tdHm(min) {
    return String(Math.floor(min / 60)).padStart(2, '0') + ':' + String(min % 60).padStart(2, '0');
}

function _tdUpdateStrip() {
    const clockEl = document.getElementById('tdClock');
    if (!clockEl) return;
    const ist = _tdIstParts();
    clockEl.textContent = _tdHm(ist.h * 60 + ist.m) + ':' + String(ist.s).padStart(2, '0');
    if (!document.getElementById('traderdesk')?.classList.contains('active')) return;

    const mod = ist.h * 60 + ist.m;
    const isWeekday = !['Sat', 'Sun'].includes(ist.weekday);

    const orbEl = document.getElementById('tdOrbWindow');
    if (orbEl) {
        if (mod < TD_ORB_START) orbEl.textContent = 'opens ' + _tdHm(TD_ORB_START);
        else if (mod < TD_ORB_END) orbEl.textContent = 'forming · ends ' + _tdHm(TD_ORB_END);
        else orbEl.textContent = 'formed ' + _tdHm(TD_ORB_START) + '–' + _tdHm(TD_ORB_END);
    }

    const entryEl = document.getElementById('tdEntryWindow');
    if (entryEl) {
        if (!isWeekday) entryEl.textContent = 'closed (weekend)';
        else if (mod < TD_ORB_END) entryEl.textContent = 'opens ' + _tdHm(TD_ORB_END);
        else if (mod < TD_ENTRY_END) entryEl.textContent = 'open · closes ' + _tdHm(TD_ENTRY_END);
        else entryEl.textContent = 'closed ' + _tdHm(TD_ENTRY_END);
    }

    const flatEl = document.getElementById('tdFlatBy');
    if (flatEl) {
        if (!isWeekday) flatEl.textContent = '15:15';
        else if (mod < TD_FLAT_BY) flatEl.textContent = '15:15 · in ' + (TD_FLAT_BY - mod) + 'm';
        else flatEl.textContent = 'square-off done';
    }

    const scanEl = document.getElementById('tdNextScan');
    if (scanEl) {
        if (!isWeekday) scanEl.textContent = 'Mon ' + _tdHm(TD_SCAN_AT);
        else if (mod < TD_SCAN_AT) {
            const mins = TD_SCAN_AT - mod;
            scanEl.textContent = (mins >= 60 ? Math.floor(mins / 60) + 'h ' : '') + (mins % 60) + 'm';
        } else scanEl.textContent = 'next: ' + _tdHm(TD_SCAN_AT) + ' tomorrow';
    }
}

const TD_PHASE_LABEL = {
    'pre_open': 'Pre-open', 'opening': 'Opening…', 'open': 'Open',
    'closing': 'Closing…', 'closed': 'Closed',
};

async function tdFetchMarketPhase() {
    if (!document.getElementById('traderdesk')?.classList.contains('active')) return;
    try {
        const data = await api('/api/market/status');
        const el = document.getElementById('tdMarketPhase');
        if (el) {
            const st = (data.status || 'closed').toLowerCase();
            el.textContent = TD_PHASE_LABEL[st] || data.status;
            el.className = 'td-strip-value td-phase-' + st;
        }
    } catch (e) {
        const el = document.getElementById('tdMarketPhase');
        if (el) { el.textContent = 'offline'; el.className = 'td-strip-value td-phase-closed'; }
    }
}

let _tdStripTimer = null;
let _tdPhaseTimer = null;

function initTraderDesk() {
    if (_tdStripTimer) return; // timers are global once started; ticks no-op when tab hidden
    _tdUpdateStrip();
    _tdStripTimer = setInterval(_tdUpdateStrip, 1000);
    tdFetchMarketPhase();
    _tdPhaseTimer = setInterval(tdFetchMarketPhase, 30000);
    tdInitEntryTimer();
}

// ===== TRADER DESK: Scanner =====
const TD_SETUP_LABELS = {
    breakout_20d: '20d-high breakout',
    bull_flag: 'bull flag',
    reclaim_ma20: 'reclaimed MA20',
    oversold: 'oversold (RSI<30)',
    oversold_bounce: 'oversold bounce',
};

async function tdResolveUniverse() {
    const sel = document.getElementById('tdScanUniverse');
    const mode = sel ? sel.value : 'core';
    if (mode === 'core') return null; // server default = curated ALL_SYMBOLS
    try {
        if (mode === 'nifty50') {
            const data = await api('/api/scanner/universe');
            return (data.universe || []).slice(0, 50).map(u => u.symbol);
        }
        const data = await api('/api/scanner/universe?full=true');
        return (data.universe || []).map(u => u.symbol);
    } catch (e) {
        showToast('Could not load universe: ' + (e.message || e), 'error');
        return null;
    }
}

function tdOnScanTypeChange() {
    const type = document.getElementById('tdScanType')?.value || 'orb';
    const wrap = document.getElementById('tdOrMinutesWrap');
    if (wrap) wrap.style.display = type === 'orb' ? '' : 'none';
    const title = document.getElementById('tdScanTitle');
    if (title) title.textContent = type === 'orb' ? 'ORB Breakout Hits' : 'Daily Setup Hits';
}

async function runTdScan() {
    const type = document.getElementById('tdScanType')?.value || 'orb';
    const badge = document.getElementById('tdScanBadge');
    const btn = document.getElementById('tdScanBtn');
    const results = document.getElementById('tdScanResults');
    if (!badge || !btn) return;

    const body = { min_price: parseFloat(document.getElementById('tdMinPrice')?.value) || 50 };
    const minVol = parseInt(document.getElementById('tdMinVolume')?.value, 10);
    if (minVol > 0) body.min_volume = minVol;
    if (type === 'orb') body.or_minutes = parseInt(document.getElementById('tdOrMinutes')?.value, 10) || 15;
    const symbols = await tdResolveUniverse();
    if (symbols) {
        body.symbols = symbols;
        if (symbols.length > 150) showToast('Scanning ' + symbols.length + ' symbols — this can take a few minutes…', 'info');
    }

    badge.textContent = 'scanning…';
    badge.className = 'badge';
    btn.disabled = true;
    if (results) results.innerHTML = '<p class="placeholder">Scanning ' + (symbols ? symbols.length : 'core universe') + ' symbols via Upstox…</p>';
    try {
        const data = await api('/api/scanner/' + type, { method: 'POST', body: JSON.stringify(body) });
        if (!data || data.error || (!data.hits && data.detail)) {
            const msg = (data && (data.detail || data.error)) || 'Scan failed';
            showToast(msg, 'error');
            badge.textContent = 'error';
            badge.className = 'badge negative';
            if (results) results.innerHTML = '<p class="placeholder">' + msg + '</p>';
            return;
        }
        tdRenderScan(data, type);
    } catch (e) {
        showToast('Scan failed: ' + (e.message || e), 'error');
        badge.textContent = 'error';
        if (results) results.innerHTML = '<p class="placeholder">Scan failed: ' + (e.message || e) + '</p>';
    } finally {
        btn.disabled = false;
    }
}

function tdRenderScan(data, type) {
    const badge = document.getElementById('tdScanBadge');
    const meta = document.getElementById('tdScanMeta');
    const wrap = document.getElementById('tdScanResults');
    if (!wrap) return;

    const hits = data.hits || [];
    const counts = data.counts || {};
    const isOrb = type === 'orb';

    if (meta) {
        meta.textContent = (hits.length + ' hits · scanned ' + (counts.scanned || 0) + '/' + (counts.requested || data.universe || 0) +
            (counts.failed ? ' · failed ' + counts.failed : '') + ' · as of ' + (data.as_of || '—') + ' · Upstox') +
            (isOrb ? ' · OR' + (data.or_minutes || 15) + 'm' : '');
    }

    if (badge) {
        badge.textContent = hits.length + ' hits';
        badge.className = 'badge' + (hits.length ? ' positive' : '');
    }

    if (!hits.length) {
        wrap.innerHTML = '<p class="placeholder">No setups passed the filters. Loosen min price / range ratio and re-run.</p>';
        return;
    }

    const header = isOrb
        ? '<tr><th>Symbol</th><th>Triggered</th><th>Price</th><th>OR High</th><th>OR Low</th><th>Range %</th><th>Over High</th><th>Actions</th></tr>'
        : '<tr><th>Symbol</th><th>Setups</th><th>Price</th><th>RSI</th><th>MA20</th><th>20d High</th><th>Actions</th></tr>';

    const rows = hits.map(h => {
        const sym = h.symbol;
        const live = '<span data-live-price>₹' + fmtPrice(h.price) + '</span> <span data-live-change-pct class="muted"></span>';
        const actions =
            '<button class="btn-secondary td-row-btn" onclick="tdWatchFromScan(\'' + sym + '\')" title="Watch entry trigger">⏱ Entry</button>' +
            '<button class="btn-secondary td-row-btn" onclick="tdPlanFromScan(\'' + sym + '\',' + (h.or_high || h.price) + ',' + (h.or_low || h.price) + ')" title="Plan exit (Exit Planner)">🎯 Exit</button>';
        if (isOrb) {
            return '<tr class="td-hit-row" data-live-symbol="' + sym + '">' +
                '<td><a href="#" onclick="openStockChart(\'' + sym + '\'); return false;"><b>' + sym.replace('.NS', '') + '</b></a></td>' +
                '<td>' + (h.at || '') + '</td>' +
                '<td>' + live + '</td>' +
                '<td>₹' + fmtPrice(h.or_high) + '</td>' +
                '<td>₹' + fmtPrice(h.or_low) + '</td>' +
                '<td>' + (h.range_ratio_pct != null ? h.range_ratio_pct + '%' : '—') + '</td>' +
                '<td class="' + ((h.pct_over || 0) >= 0 ? 'positive' : 'negative') + '">' + (h.pct_over != null ? '+' + h.pct_over + '%' : '—') + '</td>' +
                '<td class="td-actions-cell">' + actions + '</td></tr>';
        }
        const setups = (h.setups || []).map(s => '<span class="td-chip td-chip-no-data">' + (TD_SETUP_LABELS[s] || s) + '</span>').join(' ');
        return '<tr class="td-hit-row" data-live-symbol="' + sym + '">' +
            '<td><a href="#" onclick="openStockChart(\'' + sym + '\'); return false;"><b>' + sym.replace('.NS', '') + '</b></a></td>' +
            '<td>' + setups + '</td>' +
            '<td>' + live + '</td>' +
            '<td>' + (h.rsi != null ? h.rsi : '—') + '</td>' +
            '<td>' + (h.ma20 != null ? '₹' + fmtPrice(h.ma20) : '—') + '</td>' +
            '<td>' + (h.high20 != null ? '₹' + fmtPrice(h.high20) : '—') + '</td>' +
            '<td class="td-actions-cell">' + actions + '</td></tr>';
    }).join('');

    wrap.innerHTML =
        '<p class="td-note">💡 ' + (data.note || '') + '</p>' +
        '<div class="table-container"><table><thead>' + header + '</thead><tbody>' + rows + '</tbody></table></div>';

    applyLiveDomQuotes(wrap);
    refreshLiveSubscriptions();
}

function tdWatchFromScan(symbol) {
    tdAddToEntryWatch({ symbol: symbol, setup: 'orb' });
    showToast(symbol.replace('.NS', '') + ' added to Entry Timer (ORB watch)', 'success');
}

function tdPlanFromScan(symbol, orHigh, orLow) {
    // Hand off to the Exit Planner with the OR box prefilled
    const set = (id, v) => { const el = document.getElementById(id); if (el && v != null) el.value = v; };
    set('tdExitSymbol', symbol);
    set('tdExitEntry', (getLiveQuote(symbol) || {}).price || orHigh);
    set('tdExitOrHigh', orHigh);
    set('tdExitOrLow', orLow);
    const rule = document.getElementById('tdExitStopRule');
    if (rule) rule.value = 'orb_mid';
    const target = document.getElementById('tdExitTargetParam');
    if (target && !target.value) target.value = 2;
    showTraderSubTab('td-exit', document.querySelectorAll('#traderdesk .td-sub-btn')[2]);
    showToast(symbol.replace('.NS', '') + ' OR box loaded into Exit Planner — build the plan', 'success');
    runTdExitPlan();
}

// ===== TRADER DESK: Exit Planner =====
let tdDeskState = {}; // cross-pane hand-off (lastExitPlan, lastSize, …)

async function runTdExitPlan() {
    const g = id => document.getElementById(id);
    const badge = document.getElementById('tdExitBadge');
    const out = document.getElementById('tdExitPlanOut');
    if (!g('tdExitSymbol') || !g('tdExitEntry') || !out) return;

    const body = {
        symbol: (g('tdExitSymbol').value || '').trim().toUpperCase() || 'RELIANCE',
        entry: parseFloat(g('tdExitEntry').value),
        stop_rule: g('tdExitStopRule').value || 'orb_mid',
        target_rule: g('tdExitTargetRule').value || 'r',
        qty: parseInt(g('tdExitQty').value, 10) || 10,
        broker: g('tdExitBroker').value || 'discount',
        exchange: 'NSE',
    };
    if (g('tdExitStopParam').value) body.stop_param = parseFloat(g('tdExitStopParam').value);
    if (g('tdExitOrHigh').value) body.or_high = parseFloat(g('tdExitOrHigh').value);
    if (g('tdExitOrLow').value) body.or_low = parseFloat(g('tdExitOrLow').value);
    if (g('tdExitTargetParam').value !== '') body.target_param = parseFloat(g('tdExitTargetParam').value);
    if (g('tdExitAtr').value) body.atr = parseFloat(g('tdExitAtr').value);

    if (!Number.isFinite(body.entry)) { showToast('Enter the entry price', 'warning'); return; }

    badge.textContent = 'planning…';
    badge.className = 'badge';
    try {
        const data = await api('/api/exit/plan', { method: 'POST', body: JSON.stringify(body) });
        if (!data || data.error || data.detail) {
            const msg = (data && (data.detail || data.error)) || 'Plan failed';
            showToast(msg, 'error');
            badge.textContent = 'error';
            badge.className = 'badge negative';
            out.innerHTML = '<p class="placeholder">' + msg + '</p>';
            return;
        }
        tdDeskState.lastExitPlan = data;
        tdRenderExitPlan(data);
        badge.textContent = 'net R:R ' + (data.net_reward_risk != null ? data.net_reward_risk.toFixed(2) : '—');
        badge.className = 'badge' + ((data.net_reward_risk || 0) >= 1 ? ' positive' : '');
    } catch (e) {
        showToast('Plan failed: ' + (e.message || e), 'error');
        badge.textContent = 'error';
    }
}

function _tdCostRow(label, value) {
    return '<tr><td>' + label + '</td><td style="text-align:right;">' + value + '</td></tr>';
}

function tdRenderExitPlan(p) {
    const out = document.getElementById('tdExitPlanOut');
    if (!out) return;
    const c = p.statutory_costs || {};
    const costRows = Object.keys(c).map(k => _tdCostRow(k.replace(/_/g, ' '), '₹' + fmtPrice(c[k]))).join('');
    const warn = (p.warnings || []).length
        ? '<p class="td-note">⚠️ ' + p.warnings.map(w => String(w).replace(/</g, '&lt;')).join(' · ') + '</p>'
        : '';
    const rrColor = (p.net_reward_risk || 0) >= 1 ? 'positive' : 'negative';

    out.innerHTML =
        '<div class="td-grid">' +
        '<div><table><tbody>' +
        _tdCostRow('<b>' + p.symbol + '</b> · ' + p.date, p.setup || '') +
        _tdCostRow('Entry', '₹' + fmtPrice(p.entry)) +
        _tdCostRow('Stop (' + p.stop_label + ')', '<b class="negative">₹' + fmtPrice(p.stop) + '</b>') +
        _tdCostRow('Target (' + p.target_label + ')', '<b class="positive">₹' + fmtPrice(p.target) + '</b> · ' + p.target_r + 'R') +
        _tdCostRow('Risk / share', '₹' + fmtPrice(p.risk_per_share)) +
        _tdCostRow('Gross R:R', p.reward_risk) +
        _tdCostRow('Net R:R after costs', '<b class="' + rrColor + '">' + p.net_reward_risk + '</b>') +
        _tdCostRow('Net reward / share', '₹' + fmtPrice(p.net_reward_per_share)) +
        '</tbody></table></div>' +
        '<div><table><tbody>' +
        _tdCostRow('Breakeven', '₹' + fmtPrice(p.breakeven) + ' (+' + fmtPrice(p.breakeven_diff) + ')') +
        _tdCostRow('Total hurdle / share', '₹' + fmtPrice(p.total_hurdle)) +
        _tdCostRow('Slippage allowance', '₹' + fmtPrice(p.slippage)) +
        _tdCostRow('Flat by', '<b>' + p.flat_by + '</b>') +
        '</tbody></table>' +
        (costRows ? '<p class="td-note" style="margin-top:8px;">Statutory costs (per share):</p><table><tbody>' + costRows + '</tbody></table>' : '') +
        '</div></div>' + warn +
        '<p class="td-note">' + (p.note || '') + '</p>';
}

function tdOnStopRuleChange() {
    // OR high/low only matter for orb_* rules; keep them visible for transparency anyway
}

function tdOnTargetRuleChange() {}

function tdExitToSizer() {
    const p = tdDeskState.lastExitPlan;
    if (!p) { showToast('Build an exit plan first', 'warning'); return; }
    const set = (id, v) => { const el = document.getElementById(id); if (el && v != null) el.value = v; };
    set('tdSizeSymbol', p.symbol && p.symbol.includes('.') ? p.symbol : p.symbol + '.NS');
    set('tdSizeEntry', p.entry);
    set('tdSizeStop', p.stop);
    set('tdSizeTarget', p.target);
    const qtyEl = document.getElementById('tdExitQty');
    if (qtyEl) set('tdSizeQty', parseInt(qtyEl.value, 10) || 10);
    const broker = document.getElementById('tdExitBroker');
    if (broker) set('tdSizeBroker', broker.value);
    showTraderSubTab('td-sizer', document.querySelectorAll('#traderdesk .td-sub-btn')[3]);
    runTdSize();
}

// ===== TRADER DESK: Position Sizer =====
async function runTdSize() {
    const g = id => document.getElementById(id);
    const badge = document.getElementById('tdSizeBadge');
    const out = document.getElementById('tdSizeOut');
    if (!g('tdSizeSymbol') || !out) return;

    const body = {
        symbol: (g('tdSizeSymbol').value || '').trim().toUpperCase(),
        entry: parseFloat(g('tdSizeEntry').value),
        stop: parseFloat(g('tdSizeStop').value),
        target: parseFloat(g('tdSizeTarget').value),
        qty: parseInt(g('tdSizeQty').value, 10) || 10,
        broker: g('tdSizeBroker').value || 'discount',
        exchange: 'NSE',
        budget: parseFloat(g('tdSizeBudget').value) || null,
        latest_price: (getLiveQuote(body_symbol(g('tdSizeSymbol').value)) || {}).price || null,
    };
    if (!Number.isFinite(body.entry) || !Number.isFinite(body.stop)) {
        showToast('Entry and stop are required', 'warning');
        return;
    }

    badge.textContent = 'sizing…';
    badge.className = 'badge';
    try {
        const data = await api('/api/budget/size', { method: 'POST', body: JSON.stringify(body) });
        if (!data || data.error || data.detail) {
            const msg = (data && (data.detail || data.error)) || 'Sizing failed';
            showToast(msg, 'error');
            badge.textContent = 'refused';
            badge.className = 'badge negative';
            out.innerHTML = '<p class="placeholder">' + msg + '</p>';
            return;
        }
        tdDeskState.lastSize = data;
        tdRenderSize(data);
        badge.textContent = data.qty ? (data.qty + ' shares · ' + data.bound_by) : 'refused';
        badge.className = 'badge' + (data.qty ? ' positive' : ' negative');
    } catch (e) {
        showToast('Sizing failed: ' + (e.message || e), 'error');
        badge.textContent = 'error';
    }
}

function body_symbol(s) {
    s = (s || '').trim().toUpperCase();
    return s.includes('.') ? s : s + '.NS';
}

function tdRenderSize(s) {
    const out = document.getElementById('tdSizeOut');
    if (!out) return;
    const c = s.costs || {};
    const costRows = Object.keys(c).map(k => _tdCostRow(k.replace(/_/g, ' '), '₹' + fmtPrice(c[k]))).join('');
    const prop = s.order_proposal || {};
    const refusal = s.refusal
        ? '<p class="td-note">🚫 <b>' + String(s.refusal).replace(/</g, '&lt;') + '</b></p>'
        : '';
    out.innerHTML =
        '<div class="td-grid">' +
        '<div><table><tbody>' +
        _tdCostRow('<b>' + s.symbol + '</b>', s.side.toUpperCase() + ' · ' + s.product + ' · ' + s.order_type) +
        _tdCostRow('Quantity', '<b>' + s.qty + '</b> shares') +
        _tdCostRow('Bound by', s.bound_by) +
        _tdCostRow('Risk / share', '₹' + fmtPrice(s.risk_per_share)) +
        _tdCostRow('Reward : risk', s.reward_risk) +
        _tdCostRow('Max loss at stop', '<b class="negative">₹' + fmtPrice(s.total_loss_at_stop) + '</b>') +
        _tdCostRow('Round-trip cost', '₹' + fmtPrice(s.cost)) +
        _tdCostRow('Flat by', s.flat_by) +
        '</tbody></table></div>' +
        '<div>' +
        (prop && Object.keys(prop).length
            ? '<p class="td-note">Bracket-order proposal — send it to Risk Check or straight to the Order Desk:</p><table><tbody>' +
              Object.keys(prop).filter(k => typeof prop[k] !== 'object').slice(0, 10)
                  .map(k => _tdCostRow(k.replace(/_/g, ' '), String(prop[k]))).join('') +
              '</tbody></table>'
            : '') +
        (costRows ? '<p class="td-note" style="margin-top:8px;">Statutory costs:</p><table><tbody>' + costRows + '</tbody></table>' : '') +
        '</div></div>' + refusal +
        '<p class="td-note">Slippage allowance ₹' + fmtPrice(s.slippage) + '. Advisory only.</p>';
}

function tdSizeToRisk() {
    const s = tdDeskState.lastSize;
    if (!s || !s.qty) { showToast('Size a trade first', 'warning'); return; }
    const prop = s.order_proposal || {};
    tdRiskOrders.push({
        symbol: s.symbol,
        side: (s.side || 'buy').toLowerCase(),
        qty: s.qty,
        type: (prop.order_type || s.order_type || 'limit').toLowerCase(),
        limit_price: prop.limit_price || s.entry || null,
        stop_loss_stop_price: s.stop || null,
        take_profit_limit_price: s.target || null,
    });
    tdRenderRiskOrders();
    showTraderSubTab('td-risk', document.querySelectorAll('#traderdesk .td-sub-btn')[4]);
    showToast('Order added to Risk Check — run the check', 'success');
}

// ===== TRADER DESK: Risk Check =====
let tdRiskOrders = [];

function tdAddRiskOrder() {
    const g = id => document.getElementById(id);
    if (!g('tdRiskSymbol')) return;
    let sym = (g('tdRiskSymbol').value || '').trim().toUpperCase();
    if (!sym) { showToast('Enter a symbol', 'warning'); return; }
    if (!sym.includes('.')) sym += '.NS';
    const qty = parseInt(g('tdRiskQty').value, 10) || 10;
    const limit = parseFloat(g('tdRiskLimit').value);
    tdRiskOrders.push({
        symbol: sym,
        side: g('tdRiskSide').value || 'buy',
        qty: qty,
        type: 'limit',
        limit_price: Number.isFinite(limit) ? limit : null,
    });
    g('tdRiskSymbol').value = '';
    tdRenderRiskOrders();
}

function tdRemoveRiskOrder(i) {
    tdRiskOrders.splice(i, 1);
    tdRenderRiskOrders();
}

function tdClearRiskOrders() {
    tdRiskOrders = [];
    tdRenderRiskOrders();
    const out = document.getElementById('tdRiskOut');
    if (out) out.innerHTML = '<p class="placeholder">Add orders and run the check.</p>';
    const badge = document.getElementById('tdRiskBadge');
    if (badge) { badge.textContent = 'idle'; badge.className = 'badge'; }
}

function tdRenderRiskOrders() {
    const out = document.getElementById('tdRiskOut');
    if (!out) return;
    if (!tdRiskOrders.length) {
        out.innerHTML = '<p class="placeholder">No orders queued. Add one above or send from the Sizer.</p>';
        return;
    }
    const rows = tdRiskOrders.map((o, i) =>
        '<tr><td><b>' + o.symbol.replace('.NS', '') + '</b></td>' +
        '<td class="' + (o.side === 'buy' ? 'positive' : 'negative') + '">' + o.side.toUpperCase() + '</td>' +
        '<td>' + o.qty + '</td><td>' + o.type + '</td>' +
        '<td>' + (o.limit_price ? '₹' + fmtPrice(o.limit_price) : 'LTP') + '</td>' +
        '<td><button class="btn-secondary td-row-btn" onclick="tdRemoveRiskOrder(' + i + ')">✕</button></td></tr>'
    ).join('');
    out.innerHTML = '<div class="table-container"><table><thead><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Type</th><th>Price</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>';
    refreshLiveSubscriptions();
}

async function tdRunRiskCheck() {
    const badge = document.getElementById('tdRiskBadge');
    const out = document.getElementById('tdRiskOut');
    if (!badge || !out) return;
    if (!tdRiskOrders.length) { showToast('Add at least one order', 'warning'); return; }

    const g = id => document.getElementById(id);
    const config = {
        budget: parseFloat(g('tdRiskBudget').value) || undefined,
        max_loss_per_trade_inr: parseFloat(g('tdRiskMaxLoss').value) || undefined,
        max_daily_loss_inr: parseFloat(g('tdRiskDailyLoss').value) || undefined,
    };
    Object.keys(config).forEach(k => config[k] === undefined && delete config[k]);

    // Attach live prices so entries without a limit price still get validated
    const prices = {};
    tdRiskOrders.forEach(o => {
        const q = getLiveQuote(o.symbol);
        if (q && q.price) prices[o.symbol] = q.price;
    });

    badge.textContent = 'checking…';
    badge.className = 'badge';
    try {
        const data = await api('/api/risk/check', {
            method: 'POST',
            body: JSON.stringify({ orders: tdRiskOrders, config: config, prices: prices }),
        });
        if (!data || data.error || data.detail) {
            const msg = (data && (data.detail || data.error)) || 'Check failed';
            showToast(msg, 'error');
            badge.textContent = 'error';
            badge.className = 'badge negative';
            out.insertAdjacentHTML('beforeend', '<p class="placeholder">' + msg + '</p>');
            return;
        }
        tdRenderRiskVerdicts(data);
        badge.textContent = data.pass + ' pass / ' + data.block + ' block';
        badge.className = 'badge' + (data.block ? ' negative' : ' positive');
    } catch (e) {
        showToast('Check failed: ' + (e.message || e), 'error');
        badge.textContent = 'error';
    }
}

function tdRenderRiskVerdicts(res) {
    const out = document.getElementById('tdRiskOut');
    if (!out) return;
    const rows = (res.results || []).map(r =>
        '<tr><td><b>' + r.symbol.replace('.NS', '') + '</b></td>' +
        '<td class="' + (r.side === 'BUY' ? 'positive' : 'negative') + '">' + r.side + ' ' + r.qty + '</td>' +
        '<td><span class="' + (r.verdict === 'PASS' ? 'td-chip td-chip-triggered' : 'td-chip td-chip-expired') + '">' + r.verdict + '</span></td>' +
        '<td class="muted">' + (r.reasons && r.reasons.length ? r.reasons.join(' · ') : (r.warnings || []).join(' · ') || '—') + '</td>' +
        '<td>' + (r.max_loss != null ? '₹' + fmtPrice(r.max_loss) : '—') + '</td></tr>'
    ).join('');
    const t = res.today || {};
    out.innerHTML =
        '<div class="table-container"><table><thead><tr><th>Symbol</th><th>Order</th><th>Verdict</th><th>Reasons</th><th>Max Loss</th></tr></thead><tbody>' +
        rows + '</tbody></table></div>' +
        '<p class="td-note">Portfolio state: ' + res.pass + ' PASS · ' + res.block + ' BLOCK · cash after ₹' + fmtPrice(res.cash_after) +
        ' · today: ' + (t.orders_placed || 0) + ' orders, loss-at-risk ₹' + fmtPrice(t.loss_at_risk) +
        (t.daily_loss_limit ? ' / ceiling ₹' + fmtPrice(t.daily_loss_limit) : '') +
        (res.daily_loss_halted ? ' · <b class="negative">DAILY LOSS HALT ACTIVE</b>' : '') + '</p>' +
        '<p class="td-note">' + (res.advisory_note || '') + '</p>';
}

// ===== TRADER DESK: Order Desk (manual slips only — no auto-execution) =====
async function runTdCreateSlip(prefill) {
    const g = id => document.getElementById(id);
    const badge = document.getElementById('tdSlipBadge');
    const out = document.getElementById('tdSlipOut');
    if (!g('tdSlipSymbol') || !out) return;

    if (prefill) {
        // Apply a sizer-derived order to the form before building
        for (const [id, v] of Object.entries(prefill)) {
            const el = g(id);
            if (el && v != null) el.value = v;
        }
    }

    let sym = (g('tdSlipSymbol').value || '').trim().toUpperCase();
    if (!sym) { showToast('Enter a symbol', 'warning'); return; }
    if (!sym.includes('.')) sym += '.NS';
    const price = parseFloat(g('tdSlipPrice').value);
    if (!Number.isFinite(price)) { showToast('Enter the order price', 'warning'); return; }

    const body = {
        symbol: sym,
        quantity: parseInt(g('tdSlipQty').value, 10) || 1,
        price: price,
        exchange: 'NSE',
        product: 'MIS',
        order_type: g('tdSlipOrderType').value || 'LIMIT',
        broker: g('tdSlipBroker').value || 'zerodha',
        setup: 'day trade',
    };
    if (g('tdSlipStop').value) body.stop = parseFloat(g('tdSlipStop').value);
    if (g('tdSlipTarget').value) body.target = parseFloat(g('tdSlipTarget').value);

    if (badge) { badge.textContent = 'creating…'; badge.className = 'badge'; }
    try {
        const data = await api('/api/broker/slip', { method: 'POST', body: JSON.stringify(body) });
        if (!data || data.error || data.detail) {
            const msg = (data && (data.detail || data.error)) || 'Slip failed';
            showToast(msg, 'error');
            if (badge) { badge.textContent = 'error'; badge.className = 'badge negative'; }
            return;
        }
        const esc = String(data.slip).replace(/</g, '&lt;');
        out.innerHTML =
            '<pre class="td-slip-text">' + esc + '</pre>' +
            '<div class="td-actions-row" style="display:flex; gap:8px; margin-top:10px;">' +
            '<button class="btn-primary" onclick="tdCopySlip(this)">📋 Copy Slip</button>' +
            '<span class="td-note" style="align-self:center;">ticket ' + data.ticket_id + ' · ' + data.broker + ' · PROPOSED</span></div>';
        if (badge) { badge.textContent = 'slip ready'; badge.className = 'badge positive'; }
        showToast('Slip ' + data.ticket_id + ' created — copy it into your broker app, then record the fill', 'success');
        tdLoadSlips();
    } catch (e) {
        showToast('Slip failed: ' + (e.message || e), 'error');
        if (badge) { badge.textContent = 'error'; badge.className = 'badge negative'; }
    }
}

function tdSlipPrefillFromSizer() {
    const s = tdDeskState.lastSize;
    if (!s || !s.qty) { showToast('Size a trade first', 'warning'); return; }
    const prop = s.order_proposal || {};
    showTraderSubTab('td-orders', document.querySelectorAll('#traderdesk .td-sub-btn')[5]);
    // Wait for the tab to be fully active before filling the form
    setTimeout(() => runTdCreateSlip({
        tdSlipSymbol: s.symbol,
        tdSlipQty: s.qty,
        tdSlipPrice: prop.limit_price || s.entry,
        tdSlipStop: s.stop,
        tdSlipTarget: s.target,
        tdSlipOrderType: (prop.order_type || 'LIMIT').toUpperCase(),
    }), 120);
}

function tdSizeToSlip() { tdSlipPrefillFromSizer(); }

async function tdCopySlip(btn) {
    const text = document.querySelector('#tdSlipOut .td-slip-text');
    if (!text) return;
    try {
        await navigator.clipboard.writeText(text.textContent);
        btn.textContent = '✅ Copied';
        setTimeout(() => { btn.textContent = '📋 Copy Slip'; }, 1500);
    } catch (e) {
        // clipboard API can be blocked; fall back to selection
        const range = document.createRange();
        range.selectNode(text);
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
        showToast('Press ⌘C to copy the selected slip', 'info');
    }
}

async function tdLoadSlips() {
    const wrap = document.getElementById('tdSlipList');
    if (!wrap) return;
    try {
        const data = await api('/api/broker/slips');
        const slips = (data && data.slips) || [];
        if (!slips.length) {
            wrap.innerHTML = '<p class="placeholder">No slips yet.</p>';
            return;
        }
        const rows = slips.slice().reverse().slice(0, 15).map(s => {
            const id = s.ticket_id;
            return '<tr data-ticket="' + id + '">' +
                '<td class="muted" style="font-family:monospace;">' + id + '</td>' +
                '<td><b>' + (s.symbol || '').replace('.NS', '') + '</b></td>' +
                '<td>' + (s.side || 'BUY') + ' ' + (s.quantity || '') + '</td>' +
                '<td>' + (s.price || '') + '</td>' +
                '<td>' + (s.stop || '—') + ' / ' + (s.target || '—') + '</td>' +
                '<td>' + (s.broker || '') + '</td>' +
                '<td><span class="td-chip td-chip-no-data">' + (s.status || 'PROPOSED') + '</span></td>' +
                '<td><button class="btn-secondary td-row-btn" onclick="tdFillForm(\'' + id + '\',' + (s.quantity || 0) + ',' + (parseFloat(s.price) || 0) + ')">✍ Fill</button></td></tr>' +
                '<tr class="td-fill-row" id="tdFill-' + id + '" style="display:none;"><td colspan="8">' +
                '<div class="td-controls" style="margin:6px 0;">' +
                '<div class="filter-group"><label>Fill Price (₹)</label><input type="number" id="tdFillPrice-' + id + '" step="0.05" value="' + (parseFloat(s.price) || '') + '"></div>' +
                '<div class="filter-group"><label>Fill Qty</label><input type="number" id="tdFillQty-' + id + '" value="' + (s.quantity || '') + '"></div>' +
                '<div class="filter-group"><label>Note</label><input type="text" id="tdFillNote-' + id + '" placeholder="executed manually"></div>' +
                '<div class="filter-group td-actions-row"><button class="btn-primary" onclick="tdSubmitFill(\'' + id + '\')">Record Fill</button></div>' +
                '</div></td></tr>';
        }).join('');
        wrap.innerHTML = '<div class="table-container"><table><thead><tr><th>Ticket</th><th>Symbol</th><th>Order</th><th>Price</th><th>SL / TGT</th><th>Broker</th><th>Status</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>';
    } catch (e) {
        wrap.innerHTML = '<p class="placeholder">Could not load slips: ' + (e.message || e) + '</p>';
    }
}

function tdFillForm(ticketId, qty, price) {
    const row = document.getElementById('tdFill-' + ticketId);
    if (!row) return;
    row.style.display = row.style.display === 'none' ? '' : 'none';
}

async function tdSubmitFill(ticketId) {
    const g = id => document.getElementById(id);
    const price = parseFloat((g('tdFillPrice-' + ticketId) || {}).value);
    const qty = parseInt((g('tdFillQty-' + ticketId) || {}).value, 10);
    const reason = (g('tdFillNote-' + ticketId) || {}).value || 'manual fill';
    if (!Number.isFinite(price) || !qty) { showToast('Fill price and quantity are required', 'warning'); return; }
    try {
        const data = await api('/api/broker/fill', {
            method: 'POST',
            body: JSON.stringify({ ticket_id: ticketId, price: price, quantity: qty, reason: reason }),
        });
        if (!data || data.error || data.detail) {
            showToast((data && (data.detail || data.error)) || 'Fill failed', 'error');
            return;
        }
        showToast('Fill recorded for ' + ticketId + ' — ' + qty + ' @ ₹' + fmtPrice(price), 'success');
        const row = document.getElementById('tdFill-' + ticketId);
        if (row) row.style.display = 'none';
    } catch (e) {
        showToast('Fill failed: ' + (e.message || e), 'error');
    }
}

// ===== TRADER DESK: Time Machine =====
let tdTmJobId = null;
let tdTmPollTimer = null;

function tdTmPrefillFromSizer() {
    const s = tdDeskState.lastSize;
    if (!s || !s.qty) { showToast('Size a trade first', 'warning'); return; }
    const set = (id, v) => { const el = document.getElementById(id); if (el && v != null) el.value = v; };
    set('tdTmSymbol', s.symbol);
    set('tdTmEntry', s.entry);
    set('tdTmStop', s.stop);
    set('tdTmTarget', s.target);
    set('tdTmShares', s.qty);
    set('tdTmSide', s.side || 'buy');
    showTraderSubTab('td-timemachine', document.querySelectorAll('#traderdesk .td-sub-btn')[6]);
    runTdTimeMachine();
}

async function runTdTimeMachine() {
    const g = id => document.getElementById(id);
    const badge = document.getElementById('tdTmBadge');
    const mcOut = document.getElementById('tdTmMcOut');
    const wfOut = document.getElementById('tdTmWfOut');
    if (!g('tdTmSymbol') || !mcOut || !wfOut) return;

    const sym = (g('tdTmSymbol').value || '').trim().toUpperCase() || 'RELIANCE.NS';
    if (!sym.includes('.')) sym += '.NS';
    const body = {
        symbol: sym,
        date: g('tdTmDate').value || new Date().toISOString().slice(0, 10),
        entry: parseFloat(g('tdTmEntry').value),
        stop: parseFloat(g('tdTmStop').value),
        target: parseFloat(g('tdTmTarget').value),
        entry_time: g('tdTmEntryTime').value || '09:35',
        side: g('tdTmSide').value || 'buy',
        shares: parseInt(g('tdTmShares').value, 10) || 100,
        replays: parseInt(g('tdTmReplays').value, 10) || 5000,
        until: g('tdTmUntil').value || '15:30',
        split_ratio: parseFloat(g('tdTmSplit').value) || 0.70,
        embargo_sessions: parseInt(g('tdTmEmbargo').value, 10) || 1,
    };
    if (!Number.isFinite(body.entry) || !Number.isFinite(body.stop) || !Number.isFinite(body.target)) {
        showToast('Entry, stop, and target are required', 'warning');
        return;
    }

    if (badge) { badge.textContent = 'submitting…'; badge.className = 'badge'; }
    mcOut.innerHTML = '<p class="placeholder">Submitting simulation job…</p>';
    wfOut.innerHTML = '<p class="placeholder">Waiting for job to complete…</p>';

    try {
        const job = await api('/api/timemachine/job', { method: 'POST', body: JSON.stringify(body) });
        if (!job || job.error || job.detail) {
            const msg = (job && (job.detail || job.error)) || 'Job failed';
            showToast(msg, 'error');
            if (badge) { badge.textContent = 'error'; badge.className = 'badge negative'; }
            mcOut.innerHTML = '<p class="placeholder">' + msg + '</p>';
            return;
        }
        tdTmJobId = job.job_id;
        if (badge) { badge.textContent = 'running…'; badge.className = 'badge'; }
        tdPollTmJob();
    } catch (e) {
        showToast('Submit failed: ' + (e.message || e), 'error');
        if (badge) { badge.textContent = 'error'; badge.className = 'badge negative'; }
    }
}

function tdPollTmJob() {
    if (!tdTmJobId) return;
    const badge = document.getElementById('tdTmBadge');
    const mcOut = document.getElementById('tdTmMcOut');
    const wfOut = document.getElementById('tdTmWfOut');

    const check = async () => {
        try {
            const data = await api('/api/timemachine/result/' + tdTmJobId);
            if (!data || data.error) {
                if (badge) { badge.textContent = 'error'; badge.className = 'badge negative'; }
                mcOut.innerHTML = '<p class="placeholder">Job error: ' + (data && (data.detail || data.error)) + '</p>';
                if (tdTmPollTimer) { clearInterval(tdTmPollTimer); tdTmPollTimer = null; }
                return;
            }
            if (data.status === 'running') {
                if (badge) badge.textContent = 'running…';
                return;
            }
            if (data.status === 'error') {
                if (badge) { badge.textContent = 'error'; badge.className = 'badge negative'; }
                mcOut.innerHTML = '<p class="placeholder">Simulation failed: ' + (data.error || 'unknown') + '</p>';
                if (tdTmPollTimer) { clearInterval(tdTmPollTimer); tdTmPollTimer = null; }
                return;
            }
            // done
            if (tdTmPollTimer) { clearInterval(tdTmPollTimer); tdTmPollTimer = null; }
            const res = data.result;
            tdRenderTmResult(res);
            if (badge) { badge.textContent = 'done'; badge.className = 'badge positive'; }
            showToast('Time Machine complete — ' + (res.mc ? res.mc.win_rate ? (res.mc.win_rate * 100).toFixed(1) + '% win' : 'done' : ''), 'success');
            tdLoadTmHistory();
        } catch (e) {
            console.error('TMPoll error:', e);
        }
    };
    check();
    tdTmPollTimer = setInterval(check, 3000);
}

function _tdTmCostRow(label, value) {
    return '<tr><td>' + label + '</td><td style="text-align:right;">' + value + '</td></tr>';
}

function tdRenderTmResult(res) {
    const mcOut = document.getElementById('tdTmMcOut');
    const wfOut = document.getElementById('tdTmWfOut');
    if (!mcOut || !wfOut || !res) return;

    const mc = res.mc || {};
    const hist = res.history || [];
    const wf = res.walk_forward || [];

    // Monte Carlo card
    const vr = (mc.p_target || 0) * 100;
    const vs = (mc.p_stop || 0) * 100;
    const vn = (mc.p_neither || 0) * 100;
    const netMed = mc.net_pnl_median || 0;
    const wr = (mc.win_rate || 0) * 100;
    const pf = mc.profit_factor || 'N/A';

    const bands = mc.bands || []; // P50/P95 equity path bands
    let bandSvg = '';
    if (bands.length) {
        // Build simple SVG band chart (P50 line + P5/P95 shading)
        const W = 420, H = 160;
        const times = mc.band_times || [];
        const p50 = bands.map(b => b.p50).filter(x => x != null);
        const p5 = bands.map(b => b.p05).filter(x => x != null);
        const p95 = bands.map(b => b.p95).filter(x => x != null);
        if (p50.length) {
            const maxV = Math.max(...p95, 1);
            const minV = Math.min(...p5, -1);
            const scaleY = v => H - 20 - (v - minV) / (maxV - minV) * (H - 40);
            const scaleX = i => 30 + i * (W - 60) / Math.max(p50.length - 1, 1);
            const path = (arr, color, dash) => '<path d="M' + arr.map((v, i) => scaleX(i) + ',' + scaleY(v)).join(' L') + '" stroke="' + color + '" stroke-width="2" fill="none" ' + (dash ? 'stroke-dasharray="4,4"' : '') + '/>';
            bandSvg = '<svg width="' + W + '" height="' + H + '" style="background:var(--bg-secondary);border:1px solid var(--border);border-radius:6px;">' +
                '<defs><linearGradient id="bandGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="rgba(16,185,129,0.15)"/><stop offset="100%" stop-color="rgba(239,68,68,0.15)"/></linearGradient></defs>' +
                '<path d="M' + p50.map((v, i) => scaleX(i) + ',' + scaleY(v)).join(' L') +
                ' L' + p95.slice().reverse().map((v, i) => scaleX(p50.length - 1 - i) + ',' + scaleY(v)).join(' L') + ' Z" fill="url(#bandGrad)"/>' +
                path(p50, 'var(--accent)') +
                '<text x="10" y="20" font-size="11" fill="var(--text-primary)">P50 Equity Path</text>' +
                '<text x="10" y="36" font-size="10" fill="var(--text-muted)">Shaded: P5–P95 band</text>' +
                '</svg>';
        }
    }

    mcOut.innerHTML =
        '<div class="td-grid">' +
        '<div><table><tbody>' +
        _tdTmCostRow('<b>Target first</b>', vr.toFixed(1) + '%') +
        _tdTmCostRow('<b>Stop first</b>', vs.toFixed(1) + '%') +
        _tdTmCostRow('<b>Neither</b>', vn.toFixed(1) + '%') +
        _tdTmCostRow('<b>Net P&L median</b>', '₹' + fmtPrice(netMed)) +
        _tdTmCostRow('<b>Win rate</b>', wr.toFixed(1) + '%') +
        _tdTmCostRow('<b>Profit factor</b>', pf) +
        _tdTmCostRow('Sessions in pool', mc.pool_sessions || '—') +
        _tdTmCostRow('Pool range', (mc.pool_from || '') + ' → ' + (mc.pool_to || '')) +
        _tdTmCostRow('Until', mc.until || '15:30') +
        '</tbody></table></div>' +
        '<div>' + bandSvg + '</div>' +
        '</div>' +
        '<p class="td-note"><b>Verdict: </b>' + (res.verdict || '—') + '</p>';

    // Walk-forward table
    if (wf.length) {
        const rows = wf.map(s =>
            '<tr><td>' + s.session + '</td>' +
            '<td class="' + (s.net_pnl >= 0 ? 'positive' : 'negative') + '">' + '₹' + fmtPrice(s.net_pnl) + '</td>' +
            '<td>' + (s.win ? 'WIN' : 'LOSS') + '</td>' +
            '<td>' + (s.hit_target ? 'TGT' : (s.hit_stop ? 'SL' : '—')) + '</td>' +
            '<td>' + (s.max_dd != null ? '₹' + fmtPrice(s.max_dd) : '—') + '</td></tr>'
        ).join('');
        wfOut.innerHTML = '<div class="table-container"><table><thead><tr><th>Session</th><th>Net P&L</th><th>Result</th><th>Exit</th><th>Max DD</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
    } else {
        wfOut.innerHTML = '<p class="placeholder">No walk-forward sessions available (need more history).</p>';
    }
}

async function tdLoadTmHistory() {
    const wrap = document.getElementById('tdTmHist');
    if (!wrap) return;
    try {
        const data = await api('/api/timemachine/history');
        const runs = (data && data.runs) || [];
        if (!runs.length) {
            wrap.innerHTML = '<p class="placeholder">No runs yet.</p>';
            return;
        }
        const rows = runs.map(r =>
            '<tr><td>' + (r.symbol || (r.plan && r.plan.symbol) || '—') + '</td>' +
            '<td>' + (r.plan && r.plan.date ? r.plan.date : (r.data && r.data.range ? r.data.range : '—')) + '</td>' +
            '<td>' + (r.mc ? (r.mc.win_rate ? (r.mc.win_rate * 100).toFixed(1) + '%' : '—') : '—') + '</td>' +
            '<td>' + (r.mc ? '₹' + fmtPrice(r.mc.net_pnl_median || 0) : '—') + '</td>' +
            '<td>' + (r.verdict ? r.verdict.slice(0, 80) + '…' : '—') + '</td>' +
            '<td><button class="btn-secondary td-row-btn" onclick="tdShowTmRun(\'' + (r.created_at || '') + '\')">View</button></td></tr>'
        ).join('');
        wrap.innerHTML = '<div class="table-container"><table><thead><tr><th>Symbol</th><th>Date</th><th>Win %</th><th>Median P&L</th><th>Verdict</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>';
    } catch (e) {
        wrap.innerHTML = '<p class="placeholder">Could not load history: ' + (e.message || e) + '</p>';
    }
}

async function tdShowTmRun(createdAt) {
    try {
        const data = await api('/api/timemachine/history?full=true');
        const runs = (data && data.runs) || [];
        const run = runs.find(r => r.created_at === createdAt);
        if (run) tdRenderTmResult(run);
    } catch (e) {
        showToast('Could not load run: ' + (e.message || e), 'error');
    }
}

// ===== TRADER DESK: Institutional =====
async function tdLoadInstDeals() {
    const g = id => document.getElementById(id);
    const badge = document.getElementById('tdInstDealsBadge');
    const out = document.getElementById('tdInstDealsOut');
    const sym = (g('tdInstSymbol').value || '').trim().toUpperCase() || null;
    if (sym && !sym.includes('.')) sym += '.NS';

    if (badge) { badge.textContent = 'loading…'; badge.className = 'badge'; }
    try {
        const url = sym ? '/api/institutional/deals?symbol=' + encodeURIComponent(sym) : '/api/institutional/deals';
        const data = await api(url);
        if (!data || data.error) {
            showToast((data && (data.detail || data.error)) || 'Failed', 'error');
            if (badge) { badge.textContent = 'error'; badge.className = 'badge negative'; }
            return;
        }
        const deals = data.deals || [];
        const rows = deals.map(d => {
            const live = '<span data-live-price>₹' + fmtPrice(d.price) + '</span> <span data-live-change-pct class="muted"></span>';
            const flag = d.flagged ? ' <span class="td-chip td-chip-triggered">YOUR WATCH</span>' : '';
            return '<tr class="td-hit-row" data-live-symbol="' + d.symbol + '">' +
                '<td><b>' + (d.symbol || '').replace('.NS', '') + '</b></td>' +
                '<td>' + (d.deal_type || d.type || '') + '</td>' +
                '<td>' + (d.client || '—') + '</td>' +
                '<td>' + (d.quantity ? d.quantity.toLocaleString('en-IN') : '—') + '</td>' +
                '<td>' + live + '</td>' +
                '<td>₹' + (d.value ? (d.value / 1e7).toFixed(2) + ' Cr' : '—') + '</td>' +
                '<td>' + (d.date || '') + flag + '</td></tr>';
        }).join('');
        out.innerHTML = '<div class="table-container"><table><thead><tr><th>Symbol</th><th>Type</th><th>Client</th><th>Qty</th><th>Price</th><th>Value</th><th>Date</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
        if (badge) { badge.textContent = deals.length + ' deals'; badge.className = 'badge' + (deals.length ? ' positive' : ''); }
        applyLiveDomQuotes(out);
        refreshLiveSubscriptions();
    } catch (e) {
        showToast('Load failed: ' + (e.message || e), 'error');
        if (badge) { badge.textContent = 'error'; badge.className = 'badge negative'; }
    }
}

async function tdLoadPit() {
    const g = id => document.getElementById(id);
    const badge = document.getElementById('tdInstPitBadge');
    const out = document.getElementById('tdPitOut');
    const sym = (g('tdPitSymbol').value || '').trim().toUpperCase() || null;
    if (sym && !sym.includes('.')) sym += '.NS';

    if (badge) { badge.textContent = 'loading…'; badge.className = 'badge'; }
    try {
        const url = sym ? '/api/institutional/pit?symbol=' + encodeURIComponent(sym) : '/api/institutional/pit';
        const data = await api(url);
        if (!data || data.error) {
            showToast((data && (data.detail || data.error)) || 'Failed', 'error');
            if (badge) { badge.textContent = 'error'; badge.className = 'badge negative'; }
            return;
        }
        const filings = data.filings || [];
        if (!filings.length) {
            out.innerHTML = '<p class="placeholder">No PIT filings available (SEBI does not publish a public JSON API). ' +
                'Check sebi.gov.in → "Insider Trading" disclosures for PDFs.</p>';
            if (badge) { badge.textContent = 'empty'; badge.className = 'badge'; }
            return;
        }
        const rows = filings.map(f =>
            '<tr><td>' + (f.symbol || '').replace('.NS', '') + '</td>' +
            '<td>' + (f.insider_name || f.name || '—') + '</td>' +
            '<td>' + (f.insider_category || f.category || '—') + '</td>' +
            '<td>' + (f.transaction_type || f.type || '—') + '</td>' +
            '<td>' + (f.quantity ? f.quantity.toLocaleString('en-IN') : '—') + '</td>' +
            '<td>₹' + (f.price ? fmtPrice(f.price) : '—') + '</td>' +
            '<td>' + (f.date || '') + '</td>' +
            '<td>' + (f.mode || '—') + '</td></tr>'
        ).join('');
        out.innerHTML = '<div class="table-container"><table><thead><tr><th>Symbol</th><th>Insider</th><th>Category</th><th>Type</th><th>Qty</th><th>Price</th><th>Date</th><th>Mode</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
        if (badge) { badge.textContent = filings.length + ' filings'; badge.className = 'badge positive'; }
    } catch (e) {
        showToast('Load failed: ' + (e.message || e), 'error');
        if (badge) { badge.textContent = 'error'; badge.className = 'badge negative'; }
    }
}

// ===== TRADER DESK: Analyst =====
async function tdLoadAnFacts() {
    const g = id => document.getElementById(id);
    const badge = document.getElementById('tdAnFactBadge');
    const out = document.getElementById('tdAnFactsOut');
    const sym = (g('tdAnSymbol').value || '').trim().toUpperCase() || 'RELIANCE.NS';
    const quarters = parseInt(g('tdAnQuarters').value, 10) || 8;
    if (!sym.includes('.')) sym += '.NS';

    if (badge) { badge.textContent = 'loading…'; badge.className = 'badge'; }
    try {
        const data = await api('/api/analyst/facts/' + sym + '?quarters=' + quarters);
        if (!data || data.error) {
            showToast((data && (data.detail || data.error)) || 'Failed', 'error');
            if (badge) { badge.textContent = 'error'; badge.className = 'badge negative'; }
            return;
        }
        const st = data.statement || [];
        const rows = st.map(q =>
            '<tr><td>' + q.quarter + '</td>' +
            '<td>₹' + fmtPrice(q.revenue_cr || 0) + ' Cr</td>' +
            '<td>₹' + fmtPrice(q.pat_cr || 0) + ' Cr</td>' +
            '<td>' + (q.margin_pct != null ? q.margin_pct.toFixed(2) + '%' : '—') + '</td>' +
            '<td>' + (q.yoy_pct != null ? (q.yoy_pct >= 0 ? '+' : '') + q.yoy_pct.toFixed(2) + '%' : '—') + '</td>' +
            '<td>' + (q.eps != null ? '₹' + fmtPrice(q.eps) : '—') + '</td></tr>'
        ).join('');
        const latest = data.latest || {};
        out.innerHTML =
            '<p class="td-note"><b>' + data.name + ' (' + data.symbol + ')</b> · Sector: ' + data.sector +
            ' · TTM Revenue: ₹' + fmtPrice(latest.revenue_cr || 0) + ' Cr · TTM PAT: ₹' + fmtPrice(latest.pat_cr || 0) + ' Cr</p>' +
            '<div class="table-container"><table><thead><tr><th>Quarter</th><th>Revenue</th><th>PAT</th><th>Margin %</th><th>YoY %</th><th>EPS</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
            '<p class="td-note">' + (data.note || '') + '</p>';
        if (badge) { badge.textContent = 'loaded'; badge.className = 'badge positive'; }
    } catch (e) {
        showToast('Load failed: ' + (e.message || e), 'error');
        if (badge) { badge.textContent = 'error'; badge.className = 'badge negative'; }
    }
}

async function tdLoadAnMetrics() {
    const g = id => document.getElementById(id);
    const badge = document.getElementById('tdAnMetBadge');
    const out = document.getElementById('tdAnMetricsOut');
    const syms = (g('tdAnMetricsSymbols').value || 'RELIANCE.NS,TCS.NS,HDFCBANK.NS,INFY.NS,ICICIBANK.NS').trim();
    if (badge) { badge.textContent = 'loading…'; badge.className = 'badge'; }
    try {
        const data = await api('/api/analyst/metrics?symbols=' + encodeURIComponent(syms));
        if (!data || data.error) {
            showToast((data && (data.detail || data.error)) || 'Failed', 'error');
            if (badge) { badge.textContent = 'error'; badge.className = 'badge negative'; }
            return;
        }
        const rows = (data.metrics || []).map(m =>
            '<tr><td><b>' + m.symbol + '</b></td>' +
            '<td>' + (m.name || '') + '</td>' +
            '<td>' + (m.sector || '') + '</td>' +
            '<td>₹' + fmtPrice(m.ttm_revenue_cr || 0) + ' Cr</td>' +
            '<td>₹' + fmtPrice(m.ttm_pat_cr || 0) + ' Cr</td>' +
            '<td>' + (m.ttm_eps ? '₹' + fmtPrice(m.ttm_eps) : '—') + '</td>' +
            '<td>' + (m.operating_margin_pct ? m.operating_margin_pct.toFixed(2) + '%' : '—') + '</td>' +
            '<td>' + (m.net_margin_pct ? m.net_margin_pct.toFixed(2) + '%' : '—') + '</td>' +
            '<td>' + (m.pe_ratio != null ? m.pe_ratio.toFixed(1) : '—') + '</td>' +
            '<td>' + (m.pb_ratio != null ? m.pb_ratio.toFixed(1) : '—') + '</td>' +
            '<td>' + (m.roe_pct ? m.roe_pct.toFixed(2) + '%' : '—') + '</td>' +
            '<td>' + (m.roce_pct ? m.roce_pct.toFixed(2) + '%' : '—') + '</td>' +
            '<td>' + (m.debt_equity != null ? m.debt_equity.toFixed(2) : '—') + '</td></tr>'
        ).join('');
        out.innerHTML = '<div class="table-container"><table><thead><tr><th>Symbol</th><th>Name</th><th>Sector</th><th>TTM Rev</th><th>TTM PAT</th><th>EPS</th><th>Op Margin</th><th>Net Margin</th><th>P/E</th><th>P/B</th><th>ROE</th><th>ROCE</th><th>D/E</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
        if (badge) { badge.textContent = (data.metrics || []).length + ' symbols'; badge.className = 'badge positive'; }
    } catch (e) {
        showToast('Load failed: ' + (e.message || e), 'error');
        if (badge) { badge.textContent = 'error'; badge.className = 'badge negative'; }
    }
}

// ===== TRADER DESK: Session Alerts =====
let tdAlertPollTimer = null;

function tdOnAlertTypeChange() {
    const t = document.getElementById('tdAlertType')?.value;
    const priceWrap = document.getElementById('tdAlertPriceWrap');
    const pctWrap = document.getElementById('tdAlertPctWrap');
    const timeWrap = document.getElementById('tdAlertTimeWrap');
    if (priceWrap) priceWrap.style.display = ['above', 'below', 'target', 'stop'].includes(t) ? '' : 'none';
    if (pctWrap) pctWrap.style.display = t === 'pct_move' ? '' : 'none';
    if (timeWrap) timeWrap.style.display = t === 'time' ? '' : 'none';
}

async function tdAddAlertRule() {
    const g = id => document.getElementById(id);
    const sym = (g('tdAlertSymbol').value || '').trim().toUpperCase();
    if (!sym) { showToast('Enter a symbol', 'warning'); return; }
    const finalSym = sym.includes('.') ? sym : sym + '.NS';
    const type = g('tdAlertType').value;
    const body = { symbol: finalSym, type: type };
    if (['above', 'below', 'target', 'stop'].includes(type)) {
        const p = parseFloat(g('tdAlertPrice').value);
        if (!Number.isFinite(p)) { showToast('Enter a price', 'warning'); return; }
        body.price = p;
    }
    if (type === 'pct_move') {
        const p = parseFloat(g('tdAlertPct').value);
        if (!Number.isFinite(p)) { showToast('Enter a %', 'warning'); return; }
        body.pct = p;
    }
    if (type === 'time') {
        const t = (g('tdAlertTime').value || '').trim();
        if (!t) { showToast('Enter a time (HH:MM)', 'warning'); return; }
        body.at = t;
    }
    try {
        const data = await api('/api/alerts/rules', { method: 'POST', body: JSON.stringify(body) });
        if (!data || data.error) {
            showToast((data && (data.detail || data.error)) || 'Failed', 'error');
            return;
        }
        showToast('Rule ' + data.id + ' added', 'success');
        tdLoadAlertRules();
    } catch (e) {
        showToast('Add failed: ' + (e.message || e), 'error');
    }
}

async function tdLoadAlertRules() {
    const out = document.getElementById('tdAlertRulesOut');
    const badge = document.getElementById('tdAlertRulesBadge');
    if (!out) return;
    try {
        const data = await api('/api/alerts/rules');
        const rules = (data && data.rules) || [];
        if (!rules.length) {
            out.innerHTML = '<p class="placeholder">No rules yet. Add one above.</p>';
            if (badge) { badge.textContent = 'none'; badge.className = 'badge'; }
            return;
        }
        const rows = rules.map(r =>
            '<tr><td><b>' + (r.symbol || '').replace('.NS', '') + '</b></td>' +
            '<td><span class="td-chip td-chip-no-data">' + r.type + '</span></td>' +
            '<td>' + (r.price != null ? '₹' + fmtPrice(r.price) : (r.pct != null ? r.pct + '%' : (r.at || '—'))) + '</td>' +
            '<td>' + (r.rung ? '<span class="td-chip td-chip-triggered">RUNG</span>' : '<span class="td-chip td-chip-waiting">ARMED</span>') + '</td>' +
            '<td>' + (r.created ? r.created.slice(0, 19).replace('T', ' ') : '—') + '</td>' +
            '<td><button class="btn-secondary td-row-btn" onclick="tdRemoveAlertRule(\'' + r.id + '\')">✕</button></td></tr>'
        ).join('');
        out.innerHTML = '<div class="table-container"><table><thead><tr><th>Symbol</th><th>Type</th><th>Value</th><th>State</th><th>Created</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>';
        if (badge) { badge.textContent = rules.length + ' rules'; badge.className = 'badge positive'; }
    } catch (e) {
        out.innerHTML = '<p class="placeholder">Load failed: ' + (e.message || e) + '</p>';
        if (badge) { badge.textContent = 'error'; badge.className = 'badge negative'; }
    }
}

async function tdRemoveAlertRule(id) {
    try {
        await api('/api/alerts/rules/' + id, { method: 'DELETE' });
        showToast('Rule removed', 'success');
        tdLoadAlertRules();
    } catch (e) {
        showToast('Remove failed: ' + (e.message || e), 'error');
    }
}

function tdStartAlertPoll() {
    if (tdAlertPollTimer) { clearInterval(tdAlertPollTimer); tdAlertPollTimer = null; }
    const sel = document.getElementById('tdAlertPoll');
    const secs = parseInt(sel?.value, 10) || 60;
    const badge = document.getElementById('tdAlertLiveBadge');
    if (secs > 0) {
        tdAlertPollTimer = setInterval(tdRunAlertCheck, secs * 1000);
        if (badge) { badge.textContent = 'polling ' + secs + 's'; badge.className = 'badge positive'; }
    } else {
        if (badge) { badge.textContent = 'off'; badge.className = 'badge'; }
    }
}

async function tdRunAlertCheck() {
    const out = document.getElementById('tdAlertCheckOut');
    if (!out) return;
    try {
        const data = await api('/api/alerts/check', { method: 'POST' });
        if (!data || data.error) {
            out.innerHTML = '<p class="placeholder">Check failed: ' + (data && (data.detail || data.error)) + '</p>';
            return;
        }
        const fired = data.fired || [];
        const checked = data.checked || [];
        const rows = fired.map(f =>
            '<tr class="td-flash"><td><b>' + (f.symbol || '').replace('.NS', '') + '</b></td>' +
            '<td><span class="td-chip td-chip-triggered">' + f.type + '</span></td>' +
            '<td>' + (f.price != null ? '₹' + fmtPrice(f.price) : (f.pct != null ? f.pct + '%' : '')) + '</td>' +
            '<td>' + (f.current_price ? '₹' + fmtPrice(f.current_price) : '—') + '</td>' +
            '<td>' + (f.at ? f.at.slice(11, 16) : '') + '</td></tr>'
        ).join('');
        out.innerHTML =
            (fired.length
                ? '<div class="table-container"><table><thead><tr><th>Symbol</th><th>Type</th><th>Rule</th><th>Current</th><th>Fired At</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
                : '<p class="placeholder">No alerts fired this check. (' + checked.length + ' rules evaluated)</p>') +
            '<p class="td-note">Checked ' + checked.length + ' rules at ' + new Date().toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false }) + ' IST.</p>';
        if (fired.length) {
            tdPlayChime();
            showToast('🔔 ' + fired.length + ' alert(s) fired!', 'success');
        }
    } catch (e) {
        out.innerHTML = '<p class="placeholder">Check failed: ' + (e.message || e) + '</p>';
    }
}

async function tdShowClock() {
    try {
        const data = await api('/api/alerts/clock');
        if (!data || data.error) { showToast('Clock failed', 'error'); return; }
        const phase = data.session_phase || '—';
        const isOpen = data.is_open ? 'YES' : 'NO';
        showToast('Market: ' + phase + ' (' + data.ist_time.slice(11, 19) + ') · Open: ' + isOpen +
            ' · Close: ' + data.market_close + ' · MIS square-off: ' + data.mis_square_off +
            (data.next_open ? ' · Next open: ' + data.next_open : ''), 'info');
    } catch (e) {
        showToast('Clock failed: ' + (e.message || e), 'error');
    }
}

// Initialize alerts on tab activation
function tdInitAlerts() {
    tdLoadAlertRules();
    tdOnAlertTypeChange();
    tdStartAlertPoll();
}

// ===== TRADER DESK: Entry Timer =====
const TD_ENTRY_WATCH_KEY = 'tdEntryWatch';
let tdEntryState = {};      // symbol -> last check result
let tdEntryPollTimer = null;
let tdEntryChecking = false;

function tdLoadEntryWatch() {
    try {
        const raw = JSON.parse(localStorage.getItem(TD_ENTRY_WATCH_KEY) || '[]');
        return Array.isArray(raw) ? raw.filter(w => w && w.symbol) : [];
    } catch (e) {
        return [];
    }
}

function tdSaveEntryWatch(list) {
    localStorage.setItem(TD_ENTRY_WATCH_KEY, JSON.stringify(list.slice(0, 25)));
}

function tdInitEntryTimer() {
    tdRenderEntryWatch();
    tdApplyEntryPoll();
}

function tdOnEntrySetupChange() {
    const setup = document.getElementById('tdEntrySetup')?.value || 'orb';
    const wrap = document.getElementById('tdEntryLevelWrap');
    if (wrap) wrap.style.display = setup === 'level' ? '' : 'none';
}

function tdAddEntryWatch() {
    const input = document.getElementById('tdEntrySymbol');
    if (!input) return;
    let sym = (input.value || '').trim().toUpperCase();
    if (!sym) { showToast('Enter a symbol first', 'warning'); return; }
    if (!sym.includes('.')) sym = sym + '.NS';
    const setup = document.getElementById('tdEntrySetup')?.value || 'orb';
    const item = { symbol: sym, setup: setup };
    if (setup === 'level') {
        const lvl = parseFloat(document.getElementById('tdEntryLevel')?.value);
        if (!lvl || lvl <= 0) { showToast('Enter the price level to watch', 'warning'); return; }
        item.level = lvl;
    }
    tdAddToEntryWatch(item);
    input.value = '';
    showToast(sym.replace('.NS', '') + ' (' + (setup === 'orb' ? 'ORB' : 'level ' + item.level) + ') added to Entry Timer', 'success');
}

function tdAddToEntryWatch(item) {
    const list = tdLoadEntryWatch();
    const existing = list.findIndex(w => w.symbol === item.symbol);
    if (existing >= 0) list[existing] = item; else list.push(item);
    tdSaveEntryWatch(list);
    tdRenderEntryWatch();
    // immediate first check so the user sees status right away
    tdCheckEntry(item.symbol);
}

function tdRemoveEntryWatch(symbol) {
    tdSaveEntryWatch(tdLoadEntryWatch().filter(w => w.symbol !== symbol));
    delete tdEntryState[symbol];
    tdRenderEntryWatch();
    refreshLiveSubscriptions();
}

function tdClearEntryWatch() {
    tdSaveEntryWatch([]);
    tdEntryState = {};
    tdRenderEntryWatch();
    if (tdEntryPollTimer) { clearInterval(tdEntryPollTimer); tdEntryPollTimer = null; }
    refreshLiveSubscriptions();
}

function tdApplyEntryPoll() {
    const sel = document.getElementById('tdEntryPollSecs');
    const secs = sel ? parseInt(sel.value, 10) : 60;
    if (tdEntryPollTimer) { clearInterval(tdEntryPollTimer); tdEntryPollTimer = null; }
    if (secs > 0) tdEntryPollTimer = setInterval(tdCheckAllEntries, secs * 1000);
}

async function tdCheckAllEntries() {
    const list = tdLoadEntryWatch();
    if (!list.length) return;
    await Promise.all(list.map(w => tdCheckEntry(w.symbol)));
}

function _tdSessionOpenNow() {
    const ist = _tdIstParts();
    if (['Sat', 'Sun'].includes(ist.weekday)) return false;
    const mod = ist.h * 60 + ist.m;
    return mod >= TD_ORB_START && mod <= 15 * 60 + 30;
}

async function tdCheckEntry(symbol) {
    const w = tdLoadEntryWatch().find(x => x.symbol === symbol);
    if (!w) return;
    const body = {
        symbol: w.symbol,
        setup: w.setup || 'orb',
        or_minutes: 15,
        interval: '5m',
        min_volume_x: 1.25,
    };
    if (w.setup === 'level' && w.level) body.level = w.level;
    try {
        const data = await api('/api/entry/check', { method: 'POST', body: JSON.stringify(body) });
        if (!data || data.error || data.detail) {
            tdEntryState[symbol] = { status: 'no-data', reason: (data && (data.detail || data.error)) || 'check failed', at: new Date().toISOString() };
        } else {
            const prev = tdEntryState[symbol];
            tdEntryState[symbol] = data;
            // Alert on transition into "triggered" only
            if (data.status === 'triggered' && (!prev || prev.status !== 'triggered')) {
                tdAnnounceTrigger(data);
            }
        }
    } catch (e) {
        tdEntryState[symbol] = { status: 'no-data', reason: 'network error: ' + (e.message || e) };
    }
    tdRenderEntryWatch();
}

function tdAnnounceTrigger(data) {
    const sym = (data.symbol || '').replace('.NS', '');
    const t = data.trigger || {};
    const lvlName = data.setup === 'orb' ? 'the ' + (data.or_minutes || 15) + 'm range high' : 'the level';
    const priceTxt = t.price != null ? ' @ ₹' + fmtPrice(t.price) : '';
    showToast('🚨 ' + sym + ' TRIGGERED — closed above ' + lvlName + priceTxt + (t.time ? ' (' + t.time + ')' : ''), 'success');
    tdPlayChime();
    const row = document.querySelector('#tdEntryResults tr[data-symbol="' + data.symbol + '"]');
    if (row) { row.classList.remove('td-flash'); void row.offsetWidth; row.classList.add('td-flash'); }
}

function tdPlayChime() {
    try {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return;
        if (!tdAudioCtx) tdAudioCtx = new AC();
        if (tdAudioCtx.state === 'suspended') tdAudioCtx.resume();
        const now = tdAudioCtx.currentTime;
        [[660, 0], [990, 0.15]].forEach(([freq, offset]) => {
            const osc = tdAudioCtx.createOscillator();
            const gain = tdAudioCtx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, now + offset);
            gain.gain.setValueAtTime(0.15, now + offset);
            gain.gain.exponentialRampToValueAtTime(0.001, now + offset + 0.25);
            osc.connect(gain);
            gain.connect(tdAudioCtx.destination);
            osc.start(now + offset);
            osc.stop(now + offset + 0.3);
        });
    } catch (e) { /* audio is best-effort */ }
}
let tdAudioCtx = null;

const TD_STATUS_CHIP = {
    waiting: ['td-chip td-chip-waiting', 'WAITING'],
    triggered: ['td-chip td-chip-triggered', 'TRIGGERED'],
    expired: ['td-chip td-chip-expired', 'EXPIRED'],
    'no-data': ['td-chip td-chip-no-data', 'NO DATA'],
};

function tdRenderEntryWatch() {
    const wrap = document.getElementById('tdEntryResults');
    const badge = document.getElementById('tdEntryBadge');
    if (!wrap) return;
    const list = tdLoadEntryWatch();

    if (badge) {
        const triggered = list.filter(w => (tdEntryState[w.symbol] || {}).status === 'triggered').length;
        badge.textContent = list.length ? (triggered ? triggered + ' triggered' : list.length + ' watched') : 'idle';
        badge.className = 'badge' + (triggered ? ' positive' : '');
    }

    if (!list.length) {
        wrap.innerHTML = '<p class="placeholder">No symbols watched yet. Add one above, or from Scanner hits.</p>';
        return;
    }

    const rows = list.map(w => {
        const st = tdEntryState[w.symbol] || {};
        const status = st.status || '…';
        const [chipClass, chipLabel] = TD_STATUS_CHIP[status] || ['td-chip td-chip-no-data', '…'];
        const or = st.opening_range;
        const orTxt = or ? 'OR ₹' + fmtPrice(or.high) + ' / ₹' + fmtPrice(or.low) + (or.avg_volume ? ' · avg vol ' + or.avg_volume.toLocaleString('en-IN') : '') : '—';
        const trig = st.trigger;
        const detail = status === 'triggered' && trig
            ? '<span class="positive">bar ' + (trig.time || trig.bar_start || '') + ' @ ₹' + fmtPrice(trig.price) + '</span>'
            : status === 'waiting'
                ? (st.last ? 'last bar ₹' + fmtPrice(st.last.close) + ' (' + (st.last.bar_start || '') + ')' : '')
                : (st.reason || '');
        const lvlTxt = w.setup === 'level' ? ' level ₹' + fmtPrice(w.level) : '';
        return '<tr class="td-hit-row" data-symbol="' + w.symbol + '" data-live-symbol="' + w.symbol + '">' +
            '<td><a href="#" onclick="openStockChart(\'' + w.symbol + '\'); return false;"><b>' + w.symbol.replace('.NS', '') + '</b></a></td>' +
            '<td>' + (w.setup === 'orb' ? 'ORB' + lvlTxt : 'Level') + '</td>' +
            '<td><span class="' + chipClass + '">' + chipLabel + '</span></td>' +
            '<td><span data-live-price>—</span> <span data-live-change-pct class="muted"></span></td>' +
            '<td class="muted">' + orTxt + '</td>' +
            '<td>' + detail + '</td>' +
            '<td><button class="btn-secondary td-row-btn" onclick="tdRemoveEntryWatch(\'' + w.symbol + '\')" title="Remove">✕</button></td>' +
            '</tr>';
    }).join('');

    wrap.innerHTML =
        '<div class="table-container"><table><thead><tr><th>Symbol</th><th>Setup</th><th>Status</th><th>LTP</th><th>Opening Range</th><th>Detail</th><th></th></tr></thead><tbody>' +
        rows + '</tbody></table></div>';

    applyLiveDomQuotes(wrap);
    refreshLiveSubscriptions();
}

const UpstoxDesk = {
    ws: null,
    reconnectInterval: 5000,
    lastPrices: {},
    audioCtx: null,

    async init() {
        this.connectWebSocket();
        await this.updateKPIs();
        await this.loadORB();
        await this.loadSignals();
        await this.updatePaperPortfolio();
    },

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/upstox/live`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('Upstox WebSocket Connected');
            document.getElementById('upstoxEngineStatus').textContent = 'Active';
            document.getElementById('upstoxEngineStatus').className = 'kpi-badge positive';
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMarketUpdate(data);
        };

        this.ws.onclose = () => {
            document.getElementById('upstoxEngineStatus').textContent = 'Reconnecting...';
            document.getElementById('upstoxEngineStatus').className = 'kpi-badge negative';
            setTimeout(() => this.connectWebSocket(), this.reconnectInterval);
        };

        this.ws.onerror = (err) => {
            console.error('Upstox WebSocket Error:', err);
        };
    },

    handleMarketUpdate(data) {
        if (data.symbol && data.last_price) {
            const symbol = data.symbol;
            const price = data.last_price;
            const prevPrice = this.lastPrices[symbol];

            this.lastPrices[symbol] = price;

            // Update Scanner Matrix
            const row = document.querySelector(`#upstoxScannerMatrix tr[data-symbol="${symbol}"]`);
            if (row) {
                const priceCell = row.querySelector('.ltp-cell');
                if (priceCell) {
                    priceCell.textContent = price.toFixed(2);
                    const flashClass = price > prevPrice ? 'flash-green' : price < prevPrice ? 'flash-red' : '';
                    priceCell.classList.remove('flash-green', 'flash-red');
                    if (flashClass) {
                        void priceCell.offsetWidth; // Trigger reflow
                        priceCell.classList.add(flashClass);
                    }
                }
                // Update other cells if provided in data
                if (data.change_percent) {
                    const chgCell = row.querySelector('.chg-cell');
                    if (chgCell) chgCell.textContent = `${data.change_percent > 0 ? '+' : ''}${data.change_percent.toFixed(2)}%`;
                }
            }
        }
    },

    async updateKPIs() {
        const data = await api('/api/upstox/paper/portfolio');
        document.getElementById('upstoxCash').textContent = `₹${data.cash.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
        document.getElementById('upstoxMtm').textContent = `₹${data.mtm.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
        document.getElementById('upstoxMtm').className = `kpi-value ${data.mtm >= 0 ? 'positive' : 'negative'}`;
        document.getElementById('upstoxOpenPos').textContent = data.positions.length;
        document.getElementById('upstoxRealized').textContent = `₹${data.realized_pnl.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
    },

    async loadORB() {
        const data = await api('/api/upstox/scanner/orb');
        const container = document.getElementById('upstoxOrbResults');
        if (!data.breakouts || data.breakouts.length === 0) {
            container.innerHTML = '<p class="placeholder">No ORB breakouts detected</p>';
            return;
        }

        container.innerHTML = data.breakouts.map(b => `
            <div class="orb-card">
                <div class="orb-card-header">
                    <span class="orb-symbol">${b.symbol}</span>
                    <span class="orb-status-badge ${b.direction === 'UP' ? 'breakout-up' : 'breakout-down'}">
                        ${b.direction === 'UP' ? 'Bullish Breakout' : 'Bearish Breakout'}
                    </span>
                </div>
                <div class="orb-details">
                    <div class="result-row"><span>Range High:</span> <span>₹${b.range_high}</span></div>
                    <div class="result-row"><span>Range Low:</span> <span>₹${b.range_low}</span></div>
                    <div class="result-row"><span>LTP:</span> <span class="positive">₹${b.last_price}</span></div>
                </div>
            </div>
        `).join('');
    },

    async loadSignals() {
        const data = await api('/api/upstox/scanner/signals');
        const container = document.getElementById('upstoxSignalsBoard');
        if (!data.signals || data.signals.length === 0) {
            container.innerHTML = '<p class="placeholder">No high-probability signals found</p>';
            return;
        }

        container.innerHTML = data.signals.map(s => `
            <div class="card" style="margin-bottom: 10px; border-left: 4px solid var(--green);">
                <div class="card-header">
                    <strong>${s.symbol}</strong>
                    <span class="badge positive">BUY SIGNAL</span>
                </div>
                <div class="result-row"><span>Confluence:</span> <span>${s.confluence_score}/10</span></div>
                <div class="result-row"><span>Target:</span> <span class="positive">₹${s.target}</span></div>
                <div class="result-row"><span>Stop Loss:</span> <span class="negative">₹${s.stop_loss}</span></div>
            </div>
        `).join('');
    },

    async updatePaperPortfolio() {
        const data = await api('/api/upstox/paper/portfolio');
        const tbody = document.querySelector('#paperPositionsTable tbody');
        if (!data.positions || data.positions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="placeholder">No open positions</td></tr>';
            return;
        }

        tbody.innerHTML = data.positions.map(p => `
            <tr>
                <td><strong>${p.symbol}</strong></td>
                <td>${p.quantity}</td>
                <td>₹${p.entry_price.toFixed(2)}</td>
                <td class="ltp-cell" data-symbol="${p.symbol}">₹${p.last_price.toFixed(2)}</td>
                <td class="pnl-cell ${p.mtm >= 0 ? 'positive' : 'negative'}">₹${p.mtm.toFixed(2)}</td>
                <td><button class="btn-danger" onclick="squareOffPosition('${p.position_id}')">Square Off</button></td>
            </tr>
        `).join('');
    },

    async loadScannerMatrix() {
        const data = await api('/api/upstox/quotes');
        const tbody = document.querySelector('#upstoxScannerMatrix tbody');
        if (!data.quotes || Object.keys(data.quotes).length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="placeholder">No quotes available</td></tr>';
            return;
        }

        tbody.innerHTML = Object.entries(data.quotes).map(([sym, q]) => `
            <tr data-symbol="${sym}">
                <td><strong>${sym}</strong></td>
                <td class="ltp-cell">₹${(q.last_price || q.currentPrice || 0).toFixed(2)}</td>
                <td class="chg-cell ${q.change_percent >= 0 ? 'positive' : 'negative'}">
                    ${q.change_percent > 0 ? '+' : ''}${ (q.change_percent || 0).toFixed(2)}%
                </td>
                <td class="vwap-cell">${(q.vwap || 0).toFixed(2)}</td>
                <td class="vol-cell">${q.volume || 0}</td>
                <td><span class="badge positive">Live</span></td>
            </tr>
        `).join('');
    },

    playChime(type) {
        if (!this.audioCtx) this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();

        osc.connect(gain);
        gain.connect(this.audioCtx.destination);

        if (type === 'breakout') {
            osc.type = 'sine';
            osc.frequency.setValueAtTime(880, this.audioCtx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(440, this.audioCtx.currentTime + 0.2);
        } else {
            osc.type = 'square';
            osc.frequency.setValueAtTime(220, this.audioCtx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(110, this.audioCtx.currentTime + 0.3);
        }

        gain.gain.setValueAtTime(0.1, this.audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.audioCtx.currentTime + 0.3);

        osc.start();
        osc.stop(this.audioCtx.currentTime + 0.3);
    }
};

async function executePaperOrder() {
    const symbol = document.getElementById('paperSymbol').value.toUpperCase();
    const quantity = parseInt(document.getElementById('paperQty').value);
    const stop_loss = parseFloat(document.getElementById('paperSL').value);
    const target = parseFloat(document.getElementById('paperTarget').value);

    if (!symbol || !quantity || !stop_loss || !target) return showToast('Fill all order details', 'warning');

    showLoading();
    try {
        const res = await api('/api/upstox/paper/order', 'POST', {
            symbol, quantity, stop_loss, target
        });
        showToast(`Buy Order Executed for ${symbol}`, 'success');
        await UpstoxDesk.updateKPIs();
        await UpstoxDesk.updatePaperPortfolio();
    } catch (e) {
        showToast(e.detail || 'Order failed', 'error');
    } finally {
        hideLoading();
    }
}

async function squareOffPosition(positionId) {
    if (!confirm('Are you sure you want to square off this position?')) return;

    showLoading();
    try {
        await api(`/api/upstox/paper/close/${positionId}`, 'POST', { reason: 'MANUAL' });
        showToast('Position Squared Off', 'success');
        await UpstoxDesk.updateKPIs();
        await UpstoxDesk.updatePaperPortfolio();
    } catch (e) {
        showToast(e.detail || 'Close failed', 'error');
    } finally {
        hideLoading();
    }
}

async function runUpstoxBacktest() {
    const symbol = document.getElementById('btSymbol').value.toUpperCase();
    const interval = document.getElementById('btInterval').value;
    if (!symbol) return showToast('Enter symbol', 'warning');

    showLoading();
    try {
        const res = await api('/api/upstox/backtest', 'POST', { symbol, interval });
        const container = document.getElementById('btResults');

        if (res.trades && res.trades.length > 0) {
            container.innerHTML = `
                <div class="card">
                    <div class="card-header">
                        <strong>Performance:</strong>
                        <span class="positive">Profit: ₹${res.total_pnl.toFixed(2)}</span> |
                        <span>Win Rate: ${res.win_rate}%</span>
                    </div>
                    <table class="mt-2">
                        <thead><tr><th>Entry</th><th>Exit</th><th>P&L</th></tr></thead>
                        <tbody>
                            ${res.trades.map(t => `
                                <tr>
                                    <td>${t.entry_time} @ ${t.entry_price}</td>
                                    <td>${t.exit_time} @ ${t.exit_price}</td>
                                    <td class="${t.pnl >= 0 ? 'positive' : 'negative'}">₹${t.pnl.toFixed(2)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        } else {
            container.innerHTML = '<p class="placeholder">No trades found for this strategy</p>';
        }
    } catch (e) {
        showToast('Backtest failed', 'error');
    } finally {
        hideLoading();
    }
}

async function openUpstoxDepth(symbol) {
    const modal = document.getElementById('upstoxDepthModal');
    document.getElementById('depthModalSymbol').textContent = `Market Depth: ${symbol}`;
    modal.style.display = 'flex';

    const data = await api(`/api/upstox/quote/${symbol}`);
    const bidsContainer = document.getElementById('depthModalBids');
    const asksContainer = document.getElementById('depthModalAsks');

    bidsContainer.innerHTML = (data.bids || []).slice(0, 5).map(b => `
        <div class="depth-row bid-row">
            <span class="depth-price">₹${b.price}</span>
            <span class="depth-qty">${b.quantity}</span>
            <span class="depth-orders">${b.orders}</span>
        </div>
    `).join('');

    asksContainer.innerHTML = (data.asks || []).slice(0, 5).map(a => `
        <div class="depth-row ask-row">
            <span class="depth-price">₹${a.price}</span>
            <span class="depth-qty">${a.quantity}</span>
            <span class="depth-orders">${a.orders}</span>
        </div>
    `).join('');

    document.getElementById('depthModalLtp').textContent = `₹${data.last_price}`;
    document.getElementById('depthModalSpread').textContent = `₹${data.spread}`;
}

function closeUpstoxDepthModal() {
    document.getElementById('upstoxDepthModal').style.display = 'none';
}

// Initialize Upstox Desk when tab is shown
function initUpstoxDesk() {
    UpstoxDesk.init();
    UpstoxDesk.loadScannerMatrix();
}



