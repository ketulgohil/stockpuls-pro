/**
 * StockPulse Pro — Chart Controller (Unified TradingView Workspace Engine)
 */
class ChartController {
    constructor(containerId) {
        this.containerId = containerId;
        this.container = null;
        this.chart = null;
        this.candleSeries = null;
        this.volumeSeries = null;
        this.emaSeries = {};
        this.vwapSeries = {};
        this.drawingLines = [];
        this.loadingLock = false;
        this.resizeObserver = null;
    }

    init() {
        this.container = document.getElementById(this.containerId);
        if (!this.container || typeof LightweightCharts === 'undefined') return;

        this.chart = LightweightCharts.createChart(this.container, {
            width: this.container.clientWidth || 800,
            height: this.container.clientHeight || 500,
            layout: {
                background: { color: '#0a0a0f' },
                textColor: '#8888a0',
                fontSize: 11,
                fontFamily: 'JetBrains Mono, monospace'
            },
            grid: {
                vertLines: { color: 'rgba(255,255,255,0.04)' },
                horzLines: { color: 'rgba(255,255,255,0.04)' }
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: { color: '#3b82f6', width: 1, style: 2 },
                horzLine: { color: '#3b82f6', width: 1, style: 2 }
            },
            rightPriceScale: {
                borderColor: 'rgba(255,255,255,0.06)',
                scaleMargins: { top: 0.1, bottom: 0.2 }
            },
            timeScale: {
                borderColor: 'rgba(255,255,255,0.06)',
                timeVisible: true,
                secondsVisible: false
            }
        });

        this.candleSeries = this.chart.addCandlestickSeries({
            upColor: '#10b981',
            downColor: '#ef4444',
            borderDownColor: '#ef4444',
            borderUpColor: '#10b981',
            wickDownColor: '#ef4444',
            wickUpColor: '#10b981',
            lastValueVisible: false,
            priceLineVisible: false
        });

        this.volumeSeries = this.chart.addHistogramSeries({
            priceFormat: { type: 'volume' },
            priceScaleId: 'volume',
            lastValueVisible: false,
            priceLineVisible: false
        });

        this.chart.priceScale('volume').applyOptions({
            scaleMargins: { top: 0.8, bottom: 0 }
        });

        // Resize observer with cleanup support
        this.resizeObserver = new ResizeObserver(() => {
            if (this.chart && this.container) {
                this.chart.resize(this.container.clientWidth, this.container.clientHeight);
            }
        });
        this.resizeObserver.observe(this.container);
    }

    setData(candles, volumes) {
        if (!this.candleSeries || !this.volumeSeries) return;
        const normCandles = ChartDataAdapter.normalizeCandles(candles);
        const normVolumes = volumes || ChartDataAdapter.normalizeVolumes(normCandles);
        this.candleSeries.setData(normCandles);
        this.volumeSeries.setData(normVolumes);
        if (this.chart) {
            this.chart.timeScale().fitContent();
        }
    }

    showLoading(message = 'Loading chart data...') {
        if (!this.container) return;
        let overlay = this.container.querySelector('.chart-state-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'chart-state-overlay';
            overlay.style.cssText = 'position:absolute; inset:0; background:rgba(10,13,20,0.85); display:flex; flex-direction:column; align-items:center; justify-content:center; z-index:10; font-family:Inter,sans-serif;';
            this.container.style.position = 'relative';
            this.container.appendChild(overlay);
        }
        overlay.innerHTML = `
            <div class="spinner" style="width:32px; height:32px; border:3px solid rgba(59,130,246,0.2); border-top-color:#3b82f6; border-radius:50%; animation:spin 0.8s linear infinite; margin-bottom:12px;"></div>
            <div style="font-size:13px; color:var(--text-secondary); font-weight:500;">${message}</div>
        `;
    }

    showError(message = 'Failed to load chart data') {
        if (!this.container) return;
        let overlay = this.container.querySelector('.chart-state-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'chart-state-overlay';
            overlay.style.cssText = 'position:absolute; inset:0; background:rgba(10,13,20,0.9); display:flex; flex-direction:column; align-items:center; justify-content:center; z-index:10; font-family:Inter,sans-serif;';
            this.container.style.position = 'relative';
            this.container.appendChild(overlay);
        }
        overlay.innerHTML = `
            <div style="font-size:24px; margin-bottom:8px;">⚠️</div>
            <div style="font-size:13px; color:#ef4444; font-weight:600; margin-bottom:4px;">Chart Error</div>
            <div style="font-size:12px; color:var(--text-muted); text-align:center; max-width:280px;">${message}</div>
        `;
    }

    clearState() {
        if (!this.container) return;
        const overlay = this.container.querySelector('.chart-state-overlay');
        if (overlay) overlay.remove();
    }

    destroy() {
        if (this.resizeObserver && this.container) {
            this.resizeObserver.unobserve(this.container);
            this.resizeObserver.disconnect();
            this.resizeObserver = null;
        }
        if (this.chart) {
            this.chart.remove();
            this.chart = null;
        }
    }
}

window.ChartController = ChartController;
