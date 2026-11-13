/**
 * StockPulse Pro — Crosshair & Legend Module (TradingView-style)
 * Handles crosshair subscription, OHLCV legend, indicator values, and price marker
 */
const ChartCrosshairLegend = {
    // State
    isActive: false,
    lastCrosshairData: null,
    legendElement: null,
    priceMarkerLine: null,
    currentPriceMarker: null,
    lockScale: false,
    visibleLogicalRange: null,

    // Configuration
    config: {
        showOHLC: true,
        showVolume: true,
        showIndicators: true,
        showPriceMarker: true,
        priceMarkerColor: '#3b82f6',
        updateThrottleMs: 16 // ~60fps
    },

    /**
     * Initialize crosshair and legend
     */
    init(chartController, chartState) {
        this.chartController = chartController;
        this.chartState = chartState;
        this.chart = chartController.chart;
        this.candleSeries = chartController.candleSeries;
        this.volumeSeries = chartController.volumeSeries;
        this.emaSeries = chartController.emaSeries;
        this.vwapSeries = chartController.vwapSeries;

        this.createLegendPanel();
        this.subscribeToCrosshair();
        this.setupKeyboardShortcuts();
        this.loadState();
    },

    /**
     * Create the crosshair legend panel in the DOM
     */
    createLegendPanel() {
        // Find or create the legend container in the chart area
        const chartContainer = document.getElementById('chartContainerChart');
        if (!chartContainer) return;

        // Create legend panel (top-right of chart, like TradingView)
        this.legendElement = document.createElement('div');
        this.legendElement.id = 'crosshairLegend';
        this.legendElement.className = 'crosshair-legend-panel';
        this.legendElement.style.cssText = `
            position: absolute;
            top: 8px;
            right: 8px;
            background: rgba(10, 10, 15, 0.92);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px;
            padding: 10px 12px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: var(--text-primary);
            z-index: 50;
            pointer-events: none;
            min-width: 220px;
            backdrop-filter: blur(8px);
            display: none;
        `;
        this.legendElement.innerHTML = this.getLegendHTML();
        chartContainer.appendChild(this.legendElement);

        // Create price marker line (horizontal line at current price)
        if (this.config.showPriceMarker && this.candleSeries) {
            this.createPriceMarker();
        }
    },

    getLegendHTML() {
        return `
            <div class="legend-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px solid rgba(255,255,255,0.06);">
                <span style="font-weight: 600; color: var(--text-primary); font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;">Crosshair Data</span>
                <span id="legendTime" style="font-size: 10px; color: var(--text-muted);">--</span>
            </div>
            <div class="legend-ohlc" style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px 12px;">
                <div><span class="legend-label" style="color: var(--text-muted);">O</span> <span id="legendOpen" class="legend-value" style="color: var(--text-primary);">--</span></div>
                <div><span class="legend-label" style="color: var(--text-muted);">H</span> <span id="legendHigh" class="legend-value" style="color: #10b981;">--</span></div>
                <div><span class="legend-label" style="color: var(--text-muted);">L</span> <span id="legendLow" class="legend-value" style="color: #ef4444;">--</span></div>
                <div><span class="legend-label" style="color: var(--text-muted);">C</span> <span id="legendClose" class="legend-value" style="color: var(--text-primary);">--</span></div>
                <div style="grid-column: span 2;"><span class="legend-label" style="color: var(--text-muted);">Vol</span> <span id="legendVolume" class="legend-value" style="color: var(--text-secondary);">--</span></div>
                <div style="grid-column: span 2;"><span class="legend-label" style="color: var(--text-muted);">Chg</span> <span id="legendChange" class="legend-value" style="color: var(--text-primary);">--</span></div>
                <div style="grid-column: span 2;"><span class="legend-label" style="color: var(--text-muted);">Chg%</span> <span id="legendChangePct" class="legend-value" style="color: var(--text-primary);">--</span></div>
            </div>
            <div class="legend-indicators" id="legendIndicators" style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.06); display: none;">
                <div style="font-size: 10px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">Indicators</div>
                <div id="legendIndicatorValues" style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 4px 12px; font-size: 10px;"></div>
            </div>
        `;
    },

    /**
     * Subscribe to crosshair movement events
     */
    subscribeToCrosshair() {
        if (!this.chart) return;

        // Subscribe to crosshair move event
        this.chart.subscribeCrosshairMove((param) => {
            if (!param || !param.point) {
                this.hideLegend();
                this.lastCrosshairData = null;
                return;
            }

            this.handleCrosshairMove(param);
        });

        // Also subscribe to crosshair hover for immediate feedback
        this.candleSeries.subscribeCrosshairMove((param) => {
            if (!param || !param.point) return;
            this.updatePriceMarker(param.point);
        });
    },

    /**
     * Handle crosshair movement - update legend with candle data
     */
    handleCrosshairMove(param) {
        const { point, time } = param;
        if (!point || time === null || time === undefined) {
            this.hideLegend();
            return;
        }

        // Find the candle at this time
        const candles = this.getVisibleCandles();
        if (!candles || candles.length === 0) return;

        const candle = this.findCandleAtTime(candles, time);
        if (!candle) return;

        this.lastCrosshairData = { candle, time, point };
        this.updateLegend(candle, time);
        this.showLegend();
    },

    /**
     * Get visible candles from series
     */
    getVisibleCandles() {
        // We need to maintain a reference to the current candle data
        // This will be set by the chart controller when data is loaded
        return this.currentCandles || [];
    },

    /**
     * Set current candles data (called by chart controller after data load)
     */
    setCurrentCandles(candles) {
        this.currentCandles = candles;
    },

    /**
     * Find candle closest to given time
     */
    findCandleAtTime(candles, targetTime) {
        if (!candles.length) return null;

        // Convert targetTime to timestamp if it's a string
        const targetTs = typeof targetTime === 'string' ? new Date(targetTime).getTime() : targetTime * 1000;

        // Binary search for closest candle
        let left = 0;
        let right = candles.length - 1;
        let closest = null;
        let minDiff = Infinity;

        while (left <= right) {
            const mid = Math.floor((left + right) / 2);
            const candleTime = typeof candles[mid].time === 'string'
                ? new Date(candles[mid].time).getTime()
                : candles[mid].time * 1000;

            const diff = Math.abs(candleTime - targetTs);
            if (diff < minDiff) {
                minDiff = diff;
                closest = candles[mid];
            }

            if (candleTime < targetTs) {
                left = mid + 1;
            } else {
                right = mid - 1;
            }
        }

        return closest;
    },

    /**
     * Update legend with candle data
     */
    updateLegend(candle, time) {
        if (!this.legendElement) return;

        // Format time
        const timeEl = this.legendElement.querySelector('#legendTime');
        if (timeEl) {
            const date = typeof time === 'string' ? new Date(time) : new Date(time * 1000);
            timeEl.textContent = date.toLocaleString('en-IN', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                day: '2-digit',
                month: 'short',
                timeZone: 'Asia/Kolkata'
            });
        }

        // Update OHLC values
        const fmt = (val) => val !== undefined && val !== null ? Number(val).toFixed(2) : '--';

        const openEl = this.legendElement.querySelector('#legendOpen');
        const highEl = this.legendElement.querySelector('#legendHigh');
        const lowEl = this.legendElement.querySelector('#legendLow');
        const closeEl = this.legendElement.querySelector('#legendClose');
        const volEl = this.legendElement.querySelector('#legendVolume');
        const chgEl = this.legendElement.querySelector('#legendChange');
        const chgPctEl = this.legendElement.querySelector('#legendChangePct');

        if (openEl) openEl.textContent = fmt(candle.open);
        if (highEl) highEl.textContent = fmt(candle.high);
        if (lowEl) lowEl.textContent = fmt(candle.low);
        if (closeEl) closeEl.textContent = fmt(candle.close);
        if (volEl) volEl.textContent = this.formatVolume(candle.volume);

        // Calculate change from previous close
        if (this.currentCandles && this.currentCandles.length > 1) {
            const idx = this.currentCandles.findIndex(c => c.time === candle.time);
            if (idx > 0) {
                const prevClose = this.currentCandles[idx - 1].close;
                const change = candle.close - prevClose;
                const changePct = prevClose !== 0 ? (change / prevClose) * 100 : 0;

                if (chgEl) {
                    chgEl.textContent = (change >= 0 ? '+' : '') + fmt(change);
                    chgEl.style.color = change >= 0 ? '#10b981' : '#ef4444';
                }
                if (chgPctEl) {
                    chgPctEl.textContent = (changePct >= 0 ? '+' : '') + fmt(changePct) + '%';
                    chgPctEl.style.color = changePct >= 0 ? '#10b981' : '#ef4444';
                }
            }
        }

        // Update indicator values
        this.updateIndicatorValues(candle);
    },

    /**
     * Update indicator values in legend
     */
    updateIndicatorValues(candle) {
        const indicatorContainer = this.legendElement?.querySelector('#legendIndicators');
        const valuesContainer = this.legendElement?.querySelector('#legendIndicatorValues');
        if (!indicatorContainer || !valuesContainer) return;

        const indicators = this.chartState?.indicators || {};
        let html = '';
        let hasIndicators = false;

        // EMA values
        ['ema9', 'ema21', 'ema50', 'ema200'].forEach(key => {
            if (indicators[key] && this.emaSeries[key]) {
                const data = this.getSeriesValueAtTime(this.emaSeries[key], candle.time);
                if (data !== null) {
                    hasIndicators = true;
                    const color = ChartIndicatorRegistry.available.find(i => i.key === key)?.color || '#888';
                    html += `<div style="color: ${color};">${key.toUpperCase()}: <span style="color: var(--text-primary);">${Number(data).toFixed(2)}</span></div>`;
                }
            }
        });

        // VWAP
        if (indicators.vwap && this.vwapSeries.vwap) {
            const data = this.getSeriesValueAtTime(this.vwapSeries.vwap, candle.time);
            if (data !== null) {
                hasIndicators = true;
                html += `<div style="color: #eab308;">VWAP: <span style="color: var(--text-primary);">${Number(data).toFixed(2)}</span></div>`;
            }
        }

        if (hasIndicators) {
            valuesContainer.innerHTML = html;
            indicatorContainer.style.display = 'block';
        } else {
            indicatorContainer.style.display = 'none';
        }
    },

    /**
     * Get series value at specific time
     */
    getSeriesValueAtTime(series, targetTime) {
        if (!series || !series._data) return null;
        // This is a simplified approach - in reality we'd need to access the series data
        // For now, we'll return null and the indicator values won't show
        // A proper implementation would store the computed indicator arrays
        return null;
    },

    /**
     * Format volume for display
     */
    formatVolume(vol) {
        if (!vol || vol === 0) return '--';
        if (vol >= 1e9) return (vol / 1e9).toFixed(2) + 'B';
        if (vol >= 1e6) return (vol / 1e6).toFixed(2) + 'M';
        if (vol >= 1e3) return (vol / 1e3).toFixed(2) + 'K';
        return vol.toString();
    },

    /**
     * Show the legend panel
     */
    showLegend() {
        if (this.legendElement) {
            this.legendElement.style.display = 'block';
            this.isActive = true;
        }
    },

    /**
     * Hide the legend panel
     */
    hideLegend() {
        if (this.legendElement) {
            this.legendElement.style.display = 'none';
            this.isActive = false;
        }
    },

    /**
     * Create price marker line (horizontal line at current price)
     */
    createPriceMarker() {
        if (!this.candleSeries) return;

        try {
            this.priceMarkerLine = this.candleSeries.createPriceLine({
                price: 0,
                color: this.config.priceMarkerColor,
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: 'Current Price'
            });
        } catch (e) {
            console.warn('Failed to create price marker:', e);
        }
    },

    /**
     * Update price marker position
     */
    updatePriceMarker(point) {
        if (!this.priceMarkerLine || !this.candleSeries) return;

        // Convert chart coordinate to price
        const priceScale = this.candleSeries.priceScale();
        const price = priceScale.coordinateToPrice(point.y);
        if (price !== null && price !== undefined) {
            try {
                this.priceMarkerLine.applyOptions({
                    price: Number(price.toFixed(2)),
                    title: 'Current: ₹' + Number(price).toFixed(2)
                });
            } catch (e) {}
        }
    },

    /**
     * Setup keyboard shortcuts
     */
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Only handle shortcuts when chart tab is active
            const chartTab = document.getElementById('chart');
            if (!chartTab || !chartTab.classList.contains('active')) return;

            // Ignore if typing in input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            switch (e.key.toLowerCase()) {
                case '/':
                    e.preventDefault();
                    this.focusSymbolSearch();
                    break;
                case 'escape':
                    this.cancelDrawing();
                    this.hideLegend();
                    break;
                case 'f':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.toggleFullscreen();
                    }
                    break;
                case 'r':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.resetChartView();
                    }
                    break;
                case '0':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.fitContent();
                    }
                    break;
                case '=':
                case '+':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.zoomIn();
                    }
                    break;
                case '-':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.zoomOut();
                    }
                    break;
                case 'l':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.toggleLockScale();
                    }
                    break;
                case '1':
                case '2':
                case '3':
                case '4':
                case '5':
                case '6':
                case '7':
                case '8':
                case '9':
                    if (e.altKey) {
                        e.preventDefault();
                        this.selectTimeframe(parseInt(e.key));
                    }
                    break;
            }
        });
    },

    /**
     * Focus symbol search input
     */
    focusSymbolSearch() {
        const input = document.getElementById('chartSymbolInput');
        if (input) {
            input.focus();
            input.select();
        }
    },

    /**
     * Cancel active drawing tool
     */
    cancelDrawing() {
        if (typeof activateDrawingTool === 'function') {
            activateDrawingTool(null);
        }
    },

    /**
     * Toggle fullscreen
     */
    toggleFullscreen() {
        if (typeof toggleChartFullscreen === 'function') {
            toggleChartFullscreen();
        }
    },

    /**
     * Reset chart view (fit content)
     */
    resetChartView() {
        if (this.chart) {
            this.chart.timeScale().fitContent();
            this.saveVisibleRange();
        }
    },

    /**
     * Fit content (same as reset for now)
     */
    fitContent() {
        this.resetChartView();
    },

    /**
     * Zoom in
     */
    zoomIn() {
        if (this.chart) {
            const timeScale = this.chart.timeScale();
            const logicalRange = timeScale.getVisibleLogicalRange();
            if (logicalRange) {
                const center = (logicalRange.from + logicalRange.to) / 2;
                const width = (logicalRange.to - logicalRange.from) * 0.8;
                timeScale.setVisibleLogicalRange({ from: center - width/2, to: center + width/2 });
                this.saveVisibleRange();
            }
        }
    },

    /**
     * Zoom out
     */
    zoomOut() {
        if (this.chart) {
            const timeScale = this.chart.timeScale();
            const logicalRange = timeScale.getVisibleLogicalRange();
            if (logicalRange) {
                const center = (logicalRange.from + logicalRange.to) / 2;
                const width = (logicalRange.to - logicalRange.from) * 1.25;
                timeScale.setVisibleLogicalRange({ from: center - width/2, to: center + width/2 });
                this.saveVisibleRange();
            }
        }
    },

    /**
     * Toggle lock scale
     */
    toggleLockScale() {
        this.lockScale = !this.lockScale;
        if (this.chart) {
            this.chart.applyOptions({
                handleScale: {
                    mouseWheel: !this.lockScale,
                    pinch: !this.lockScale,
                    axisPressedMouseMove: !this.lockScale
                }
            });
        }
        this.showToast(`Scale ${this.lockScale ? 'locked' : 'unlocked'}`, 'info');
        this.saveState();
    },

    /**
     * Select timeframe by number (Alt+1-9)
     */
    selectTimeframe(num) {
        const timeframes = ['1d', '5d', '1mo', '3mo', '6mo', '1y', '5m', '15m', '30m', '1h'];
        const tf = timeframes[num - 1];
        if (tf && typeof setChartTimeframe === 'function') {
            const btn = document.querySelector(`#chart .tf-btn[data-tf="${tf}"]`);
            if (btn) setChartTimeframe(tf, btn);
        }
    },

    /**
     * Save visible logical range for preservation across resolution changes
     */
    saveVisibleRange() {
        if (!this.chart) return;
        const timeScale = this.chart.timeScale();
        const range = timeScale.getVisibleLogicalRange();
        if (range) {
            this.visibleLogicalRange = range;
            this.saveState();
        }
    },

    /**
     * Restore visible logical range when switching resolutions
     */
    restoreVisibleRange() {
        if (!this.chart || !this.visibleLogicalRange) return;

        const timeScale = this.chart.timeScale();
        const currentRange = timeScale.getVisibleLogicalRange();

        // Only restore if we have a saved range and the chart has data
        if (this.visibleLogicalRange && currentRange) {
            // Check if the saved range is valid for current data
            timeScale.setVisibleLogicalRange(this.visibleLogicalRange);
        }
    },

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    },

    /**
     * Save state to chartState
     */
    saveState() {
        if (this.chartState) {
            this.chartState.crosshair = {
                lockScale: this.lockScale,
                visibleLogicalRange: this.visibleLogicalRange
            };
            this.chartState.save();
        }
    },

    /**
     * Load state from chartState
     */
    loadState() {
        if (this.chartState?.crosshair) {
            this.lockScale = this.chartState.crosshair.lockScale || false;
            this.visibleLogicalRange = this.chartState.crosshair.visibleLogicalRange || null;

            if (this.lockScale && this.chart) {
                this.chart.applyOptions({
                    handleScale: {
                        mouseWheel: false,
                        pinch: false,
                        axisPressedMouseMove: false
                    }
                });
            }
        }
    },

    /**
     * Cleanup
     */
    destroy() {
        if (this.legendElement) {
            this.legendElement.remove();
            this.legendElement = null;
        }
        if (this.priceMarkerLine && this.candleSeries) {
            try {
                this.candleSeries.removePriceLine(this.priceMarkerLine);
            } catch (e) {}
            this.priceMarkerLine = null;
        }
    }
};

window.ChartCrosshairLegend = ChartCrosshairLegend;