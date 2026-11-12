/**
 * StockPulse Pro — Chart State Management (TradingView-style Workspace)
 */
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

    load() {
        try {
            const saved = localStorage.getItem('stockpulse_chart_workspace');
            if (saved) {
                const parsed = JSON.parse(saved);
                Object.assign(this, parsed);
            }
        } catch (e) {
            console.error('Failed to load chart workspace state:', e);
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
                theme: this.theme
            }));
        } catch (e) {
            console.error('Failed to save chart workspace state:', e);
        }
    }
};

window.ChartState = ChartState;
