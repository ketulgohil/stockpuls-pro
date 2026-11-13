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
        this.currentCandles = [];
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
                scaleMargins: { top: 0.08, bottom: 0.08 },
                autoScale: true
            },
            timeScale: {
                borderColor: 'rgba(255,255,255,0.06)',
                timeVisible: true,
                secondsVisible: false,
                rightOffset: 5,
                barSpacing: 6
            },
            handleScale: {
                mouseWheel: true,
                pinch: true,
                axisPressedMouseMove: true
            },
            handleScroll: {
                mouseWheel: true,
                pressedMouseMove: true,
                horzTouchDrag: true,
                vertTouchDrag: true
            }
        });

        this.candleSeries = this.chart.addCandlestickSeries({
            upColor: '#10b981',
            downColor: '#ef4444',
            borderDownColor: '#ef4444',
            borderUpColor: '#10b981',
            wickDownColor: '#ef4444',
            wickUpColor: '#10b981',
            lastValueVisible: true,
            priceLineVisible: false,
            priceFormat: {
                type: 'price',
                precision: 2,
                minMove: 0.01
            }
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

        // Force initial resize after a brief delay to ensure container has dimensions
        setTimeout(() => {
            if (this.chart && this.container) {
                this.chart.resize(this.container.clientWidth, this.container.clientHeight);
            }
        }, 50);

        // Create zoom control buttons
        this.createZoomControls();

        // Initialize crosshair legend if available
        if (window.ChartCrosshairLegend && window.ChartState) {
            window.ChartCrosshairLegend.init(this, window.ChartState);
        }
    }

    createZoomControls() {
        if (!this.container) return;

        // Create zoom control panel (bottom-right of chart)
        this.zoomControls = document.createElement('div');
        this.zoomControls.id = 'chartZoomControls';
        this.zoomControls.className = 'chart-zoom-controls';
        this.zoomControls.style.cssText = `
            position: absolute;
            bottom: 8px;
            right: 8px;
            display: flex;
            flex-direction: column;
            gap: 4px;
            z-index: 50;
            pointer-events: auto;
        `;
        this.zoomControls.innerHTML = `
            <button class="zoom-btn" data-action="zoom-in" title="Zoom In (Ctrl++)" aria-label="Zoom in" style="width: 32px; height: 32px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text-primary); transition: all 0.15s;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line><line x1="11" y1="8" x2="11" y2="14"></line><line x1="8" y1="11" x2="14" y2="11"></line></svg>
            </button>
            <button class="zoom-btn" data-action="zoom-out" title="Zoom Out (Ctrl+-)" aria-label="Zoom out" style="width: 32px; height: 32px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text-primary); transition: all 0.15s;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line><line x1="8" y1="11" x2="14" y2="11"></line></svg>
            </button>
            <button class="zoom-btn" data-action="reset" title="Reset View (Ctrl+0)" aria-label="Reset chart view" style="width: 32px; height: 32px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text-primary); transition: all 0.15s;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
            </button>
            <button class="zoom-btn" data-action="lock-scale" title="Lock Scale (Ctrl+L)" aria-label="Lock chart scale" style="width: 32px; height: 32px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text-primary); transition: all 0.15s;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="20" height="12" rx="2"></rect><path d="M6 6v4M18 6v4M6 14v4M18 14v4"></path></svg>
            </button>
        `;
        this.container.style.position = 'relative';
        this.container.appendChild(this.zoomControls);

        // Add event listeners
        this.zoomControls.querySelectorAll('.zoom-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = btn.dataset.action;
                this.handleZoomAction(action);
            });

            // Hover effects
            btn.addEventListener('mouseenter', () => {
                btn.style.background = 'var(--bg-hover)';
                btn.style.borderColor = 'var(--accent)';
            });
            btn.addEventListener('mouseleave', () => {
                btn.style.background = 'var(--bg-card)';
                btn.style.borderColor = 'var(--border)';
            });
        });
    }

    handleZoomAction(action) {
        if (!this.chart) return;
        const timeScale = this.chart.timeScale();
        const logicalRange = timeScale.getVisibleLogicalRange();

        switch (action) {
            case 'zoom-in':
                if (logicalRange) {
                    const center = (logicalRange.from + logicalRange.to) / 2;
                    const width = (logicalRange.to - logicalRange.from) * 0.8;
                    timeScale.setVisibleLogicalRange({ from: center - width/2, to: center + width/2 });
                    this.saveVisibleRange();
                }
                break;
            case 'zoom-out':
                if (logicalRange) {
                    const center = (logicalRange.from + logicalRange.to) / 2;
                    const width = (logicalRange.to - logicalRange.from) * 1.25;
                    timeScale.setVisibleLogicalRange({ from: center - width/2, to: center + width/2 });
                    this.saveVisibleRange();
                }
                break;
            case 'reset':
                timeScale.fitContent();
                this.saveVisibleRange();
                break;
            case 'lock-scale':
                if (window.ChartCrosshairLegend) {
                    window.ChartCrosshairLegend.toggleLockScale();
                    // Update button appearance
                    const btn = this.zoomControls.querySelector('[data-action="lock-scale"]');
                    if (btn) {
                        btn.style.opacity = window.ChartCrosshairLegend.lockScale ? '1' : '0.5';
                        btn.title = window.ChartCrosshairLegend.lockScale ? 'Unlock Scale (Ctrl+L)' : 'Lock Scale (Ctrl+L)';
                    }
                }
                break;
        }
    }

    saveVisibleRange() {
        if (this.chart && window.ChartCrosshairLegend) {
            window.ChartCrosshairLegend.saveVisibleRange();
        }
    }

    restoreVisibleRange() {
        if (window.ChartCrosshairLegend) {
            window.ChartCrosshairLegend.restoreVisibleRange();
        }
    }

    setData(candles, volumes) {
        if (!this.candleSeries || !this.volumeSeries) return;
        const normCandles = ChartDataAdapter.normalizeCandles(candles);
        const normVolumes = volumes || ChartDataAdapter.normalizeVolumes(normCandles);
        this.candleSeries.setData(normCandles);
        this.volumeSeries.setData(normVolumes);

        // Store candles for crosshair legend
        this.currentCandles = normCandles;

        // Update crosshair legend with current candles
        if (window.ChartCrosshairLegend) {
            window.ChartCrosshairLegend.setCurrentCandles(normCandles);
        }

        // Add marker for live daily candle (last candle if isLive)
        this.addLiveCandleMarker(normCandles);


        if (this.chart) {
            this.chart.timeScale().fitContent();
        }

        // Render active indicators from registry
        this.updateIndicators(normCandles);
    }


    addLiveCandleMarker(candles) {
        if (!this.chart) return;
        // Remove existing live markers
        if (this.liveMarker) {
            try { this.chart.removeTimeScaleMarker(this.liveMarker); } catch(e) {}
            this.liveMarker = null;
        }
        // Find last live candle
        const liveCandle = [...candles].reverse().find(c => c.isLive);
        if (liveCandle) {
            try {
                this.liveMarker = this.chart.addTimeScaleMarker({
                    time: liveCandle.time,
                    position: "aboveBar",
                    color: "#f59e0b",
                    shape: "arrowDown",
                    text: "LIVE",
                    fontSize: 10,
                    fontWeight: "bold"
                });
            } catch(e) {
                console.warn("Could not add live candle marker:", e);
            }
        }
    },
    updateIndicators(candles) {
        if (!candles || !candles.length || !window.ChartIndicatorRegistry) return;
        const active = window.ChartIndicatorRegistry.activeIndicators;
        if (!active) return;

        // Compute and update overlay indicators (EMA, SMA, VWAP, BB, Pivots, ORB)
        active.forEach(ind => {
            if (!ind.visible) return;
            const def = window.ChartIndicatorRegistry.definitions[ind.type];
            if (!def) return;

            if (ind.type === 'ema' || ind.type === 'sma') {
                const data = def.calculate(candles, ind.settings);
                if (!this.emaSeries[ind.id] && this.chart) {
                    this.emaSeries[ind.id] = this.chart.addLineSeries({
                        color: ind.settings.color || '#3b82f6',
                        lineWidth: ind.settings.width || 2,
                        priceLineVisible: false,
                        lastValueVisible: false,
                        crosshairMarkerVisible: false
                    });
                }
                if (this.emaSeries[ind.id]) {
                    this.emaSeries[ind.id].setData(data || []);
                }
            }
        });
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
        if (this.zoomControls) {
            this.zoomControls.remove();
            this.zoomControls = null;
        }
        if (this.chart) {
            this.chart.remove();
            this.chart = null;
        }
    }
}

window.ChartController = ChartController;
