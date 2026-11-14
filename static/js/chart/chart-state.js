/**
 * StockPulse Pro — Chart State Management (TradingView-style Workspace)
 */
// Allowed values for persisted fields. Anything outside these is discarded
// (falls back to the current/default value) instead of being assigned.
const CHART_STATE_RESOLUTIONS = ['1d', '5d', '1mo', '3mo', '6mo', '1y', '5m', '15m', '30m', '1h'];
const CHART_STATE_CHART_TYPES = ['candles', 'line', 'area', 'bars', 'heikin-ashi'];
const CHART_STATE_SYMBOL_RE = /^[A-Z0-9&\-^]{1,20}(\.(NS|BO))?$/;

const ChartState = {
    symbol: 'RELIANCE.NS',
    resolution: '1d',
    chartType: 'candles',
    indicators: {
        ema9: true,
        ema21: true,
        ema50: true,
        ema200: true,
        vwap: true,
        pivots: true
    },
    drawings: [],
    theme: 'dark',
    sidebarWatchlist: true,
    sidebarContext: false,
    // Phase 3: Crosshair, legend, navigation state
    crosshair: {
        lockScale: false,
        visibleLogicalRange: null,
        showLegend: true
    },

    load() {
        try {
            const saved = localStorage.getItem('stockpulse_chart_workspace');
            if (!saved) return;
            const parsed = JSON.parse(saved);
            if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
                console.warn('Chart workspace state malformed — resetting.');
                this.clear();
                return;
            }

            // Whitelist restore: only known keys with valid types are applied.
            // Never blindly Object.assign a stored payload into the workspace —
            // a corrupted or hand-edited localStorage value could otherwise
            // inject unexpected properties (or functions) into this object.
            if (typeof parsed.symbol === 'string' && CHART_STATE_SYMBOL_RE.test(parsed.symbol)) {
                this.symbol = parsed.symbol;
            }
            if (typeof parsed.resolution === 'string' && CHART_STATE_RESOLUTIONS.includes(parsed.resolution)) {
                this.resolution = parsed.resolution;
            }
            if (typeof parsed.chartType === 'string' && CHART_STATE_CHART_TYPES.includes(parsed.chartType)) {
                this.chartType = parsed.chartType;
            }
            if (parsed.indicators && typeof parsed.indicators === 'object' && !Array.isArray(parsed.indicators)) {
                for (const key of Object.keys(this.indicators)) {
                    if (typeof parsed.indicators[key] === 'boolean') {
                        this.indicators[key] = parsed.indicators[key];
                    }
                }
            }
            if (Array.isArray(parsed.drawings)) {
                this.drawings = parsed.drawings.filter(d => d && typeof d === 'object');
            }
            if (parsed.theme === 'dark' || parsed.theme === 'light') {
                this.theme = parsed.theme;
            }
            if (parsed.crosshair && typeof parsed.crosshair === 'object' && !Array.isArray(parsed.crosshair)) {
                if (typeof parsed.crosshair.lockScale === 'boolean') {
                    this.crosshair.lockScale = parsed.crosshair.lockScale;
                }
                if (parsed.crosshair.visibleLogicalRange === null
                    || (typeof parsed.crosshair.visibleLogicalRange === 'number' && Number.isFinite(parsed.crosshair.visibleLogicalRange))) {
                    this.crosshair.visibleLogicalRange = parsed.crosshair.visibleLogicalRange;
                }
                if (typeof parsed.crosshair.showLegend === 'boolean') {
                    this.crosshair.showLegend = parsed.crosshair.showLegend;
                }
            }
        } catch (e) {
            console.error('Failed to load chart workspace state:', e);
            // Corrupted payload — drop it so the next save starts clean.
            this.clear();
        }
    },

    clear() {
        try {
            localStorage.removeItem('stockpulse_chart_workspace');
        } catch (e) {
            console.error('Failed to clear chart workspace state:', e);
        }
    },

    save() {
        try {
            localStorage.setItem('stockpulse_chart_workspace', JSON.stringify({
                symbol: this.symbol,
                resolution: this.resolution,
                chartType: this.chartType,
                indicators: this.indicators,
                drawings: this.drawings,
                theme: this.theme,
                crosshair: this.crosshair
            }));
        } catch (e) {
            console.error('Failed to save chart workspace state:', e);
        }
    }
};

window.ChartState = ChartState;
