/**
 * StockPulse Pro — Indicator Registry & Configurable Picker System (Phase 4)
 */
const ChartIndicatorRegistry = {
    // Registry of available indicator types with default metadata
    definitions: {
        ema: {
            id: 'ema',
            name: 'Exponential Moving Average',
            shortName: 'EMA',
            category: 'Trend',
            type: 'overlay',
            defaultSettings: { period: 20, color: '#3b82f6', width: 2, style: 0 },
            calculate: (candles, opts) => window.Indicators ? window.Indicators.computeEma(candles, opts.period) : []
        },
        sma: {
            id: 'sma',
            name: 'Simple Moving Average',
            shortName: 'SMA',
            category: 'Trend',
            type: 'overlay',
            defaultSettings: { period: 50, color: '#f59e0b', width: 2, style: 0 },
            calculate: (candles, opts) => window.Indicators ? window.Indicators.computeSma(candles, opts.period) : []
        },
        vwap: {
            id: 'vwap',
            name: 'VWAP & Bands',
            shortName: 'VWAP',
            category: 'Volume',
            type: 'overlay',
            defaultSettings: { color: '#eab308', width: 2, showBands: true },
            calculate: (candles) => window.Indicators ? window.Indicators.computeVwap(candles) : null
        },
        bollinger: {
            id: 'bollinger',
            name: 'Bollinger Bands',
            shortName: 'BB',
            category: 'Volatility',
            type: 'overlay',
            defaultSettings: { period: 20, stdDev: 2, color: '#a855f7', width: 1 },
            calculate: (candles, opts) => window.Indicators ? window.Indicators.computeBollingerBands(candles, opts.period, opts.stdDev) : null
        },
        pivots: {
            id: 'pivots',
            name: 'Camarilla & Classic Pivots',
            shortName: 'Pivots',
            category: 'Support/Resistance',
            type: 'overlay',
            defaultSettings: { type: 'camarilla', color: '#ec4899' },
            calculate: (hlc) => window.Indicators ? window.Indicators.computePivots(hlc) : null
        },
        orb: {
            id: 'orb',
            name: 'ORB Strategy Levels',
            shortName: 'ORB',
            category: 'StockPulse Pro',
            type: 'overlay',
            defaultSettings: { color: '#3b82f6' }
        },
        rsi: {
            id: 'rsi',
            name: 'Relative Strength Index',
            shortName: 'RSI',
            category: 'Oscillators',
            type: 'subpane',
            defaultSettings: { period: 14, color: '#38bdf8', overbought: 70, oversold: 30 },
            calculate: (candles, opts) => window.Indicators ? window.Indicators.computeRsi(candles, opts.period) : []
        },
        macd: {
            id: 'macd',
            name: 'Moving Average Convergence Divergence',
            shortName: 'MACD',
            category: 'Oscillators',
            type: 'subpane',
            defaultSettings: { fast: 12, slow: 26, signal: 9, macdColor: '#3b82f6', signalColor: '#f59e0b' },
            calculate: (candles, opts) => window.Indicators ? window.Indicators.computeMacd(candles, opts.fast, opts.slow, opts.signal) : null
        },
        atr: {
            id: 'atr',
            name: 'Average True Range',
            shortName: 'ATR',
            category: 'Volatility',
            type: 'subpane',
            defaultSettings: { period: 14, color: '#ec4899' },
            calculate: (candles, opts) => window.Indicators ? window.Indicators.computeAtr(candles, opts.period) : []
        },
        adx: {
            id: 'adx',
            name: 'Average Directional Index',
            shortName: 'ADX',
            category: 'Trend',
            type: 'subpane',
            defaultSettings: { period: 14, color: '#f97316' },
            calculate: (candles, opts) => window.Indicators ? window.Indicators.computeAdx(candles, opts.period) : null
        }
    },

    // Presets / Templates
    templates: {
        Trend: ['ema9', 'ema21', 'ema50', 'ema200', 'volume'],
        Intraday: ['vwap', 'rsi', 'volume'],
        ORB: ['orb', 'vwap', 'ema9', 'rsi'],
        Minimal: ['sma50', 'volume']
    },

    // Active instances configured by user
    activeIndicators: [
        { id: 'ema9', type: 'ema', settings: { period: 9, color: '#38bdf8', width: 1 }, visible: true },
        { id: 'ema21', type: 'ema', settings: { period: 21, color: '#3b82f6', width: 2 }, visible: true },
        { id: 'ema50', type: 'ema', settings: { period: 50, color: '#f59e0b', width: 2 }, visible: true },
        { id: 'ema200', type: 'ema', settings: { period: 200, color: '#a855f7', width: 2 }, visible: true },
        { id: 'vwap', type: 'vwap', settings: { color: '#eab308', width: 2 }, visible: true },
        { id: 'pivots', type: 'pivots', settings: { type: 'camarilla', color: '#ec4899' }, visible: true },
        { id: 'orb', type: 'orb', settings: { color: '#3b82f6' }, visible: true }
    ],

    // Backward compatibility helper
    computeEma(candles, period) {
        return window.Indicators ? window.Indicators.computeEma(candles, period) : [];
    },
    computeVwap(candles) {
        return window.Indicators ? window.Indicators.computeVwap(candles) : null;
    },

    // Indicator Picker Modal Methods
    initPickerUI() {
        if (document.getElementById('indicatorPickerModal')) return;

        const modal = document.createElement('div');
        modal.id = 'indicatorPickerModal';
        modal.className = 'chart-modal-overlay';
        modal.style.cssText = 'position:fixed; inset:0; background:rgba(0,0,0,0.75); backdrop-filter:blur(4px); z-index:1000; display:none; align-items:center; justify-content:center; padding:16px;';

        modal.innerHTML = `
            <div class="chart-modal-content" style="background:var(--bg-card); border:1px solid var(--border); border-radius:12px; width:100%; max-width:640px; max-height:85vh; display:flex; flex-direction:column; overflow:hidden; box-shadow:0 20px 50px rgba(0,0,0,0.6);">
                <div class="modal-header" style="padding:16px 20px; border-bottom:1px solid var(--border); display:flex; align-items:center; justify-content:space-between;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 20V10M12 20V4M6 20v-6"/></svg>
                        <h3 style="margin:0; font-size:16px; font-weight:700; color:var(--text-primary);">Indicators & Strategies</h3>
                    </div>
                    <button onclick="ChartIndicatorRegistry.closePicker()" style="background:none; border:none; color:var(--text-muted); cursor:pointer; font-size:20px; line-height:1;">&times;</button>
                </div>

                <!-- Template bar -->
                <div style="padding:12px 20px; background:var(--bg-secondary); border-bottom:1px solid var(--border); display:flex; align-items:center; gap:8px; overflow-x:auto;">
                    <span style="font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px;">Templates:</span>
                    <button class="btn-sm" onclick="ChartIndicatorRegistry.applyTemplate('Trend')" style="padding:4px 10px; font-size:11px;">Trend Ribbon</button>
                    <button class="btn-sm" onclick="ChartIndicatorRegistry.applyTemplate('Intraday')" style="padding:4px 10px; font-size:11px;">Intraday Scalp</button>
                    <button class="btn-sm" onclick="ChartIndicatorRegistry.applyTemplate('ORB')" style="padding:4px 10px; font-size:11px;">ORB Day Trader</button>
                    <button class="btn-sm" onclick="ChartIndicatorRegistry.applyTemplate('Minimal')" style="padding:4px 10px; font-size:11px;">Minimalist</button>
                </div>

                <!-- Search & Filter bar -->
                <div style="padding:12px 20px; border-bottom:1px solid var(--border); display:flex; flex-direction:column; gap:10px;">
                    <input type="text" id="indicatorSearchInput" placeholder="Search indicators (e.g., RSI, EMA, Bollinger)..." oninput="ChartIndicatorRegistry.filterList()" style="width:100%; padding:8px 12px; background:var(--bg-primary); border:1px solid var(--border); border-radius:6px; color:var(--text-primary); font-size:13px;">
                    <div id="indicatorCategoryTabs" style="display:flex; gap:6px; overflow-x:auto;">
                        <button class="cat-tab active" data-cat="All" onclick="ChartIndicatorRegistry.selectCategory('All', this)">All</button>
                        <button class="cat-tab" data-cat="Trend" onclick="ChartIndicatorRegistry.selectCategory('Trend', this)">Trend</button>
                        <button class="cat-tab" data-cat="Oscillators" onclick="ChartIndicatorRegistry.selectCategory('Oscillators', this)">Oscillators</button>
                        <button class="cat-tab" data-cat="Volatility" onclick="ChartIndicatorRegistry.selectCategory('Volatility', this)">Volatility</button>
                        <button class="cat-tab" data-cat="Volume" onclick="ChartIndicatorRegistry.selectCategory('Volume', this)">Volume</button>
                        <button class="cat-tab" data-cat="StockPulse Pro" onclick="ChartIndicatorRegistry.selectCategory('StockPulse Pro', this)">StockPulse Pro</button>
                    </div>
                </div>

                <!-- Indicator List -->
                <div id="indicatorListContainer" style="flex:1; overflow-y:auto; padding:12px 20px; display:flex; flex-direction:column; gap:8px;">
                    <!-- Populated dynamically -->
                </div>

                <div style="padding:12px 20px; border-top:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; background:var(--bg-secondary);">
                    <span id="activeCountLabel" style="font-size:12px; color:var(--text-muted);">7 active indicators</span>
                    <button class="btn-primary" onclick="ChartIndicatorRegistry.closePicker()">Done</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
    },

    openPicker() {
        this.initPickerUI();
        const modal = document.getElementById('indicatorPickerModal');
        if (modal) {
            modal.style.display = 'flex';
            this.renderList();
        }
    },

    closePicker() {
        const modal = document.getElementById('indicatorPickerModal');
        if (modal) modal.style.display = 'none';
    },

    currentCategory: 'All',

    selectCategory(cat, btn) {
        this.currentCategory = cat;
        document.querySelectorAll('#indicatorCategoryTabs .cat-tab').forEach(b => b.classList.remove('active'));
        if (btn) btn.classList.add('active');
        this.renderList();
    },

    filterList() {
        this.renderList();
    },

    renderList() {
        const container = document.getElementById('indicatorListContainer');
        if (!container) return;

        const query = (document.getElementById('indicatorSearchInput')?.value || '').toLowerCase().trim();
        const cat = this.currentCategory;

        const list = Object.values(this.definitions).filter(def => {
            const matchesCat = cat === 'All' || def.category === cat;
            const matchesQuery = !query || def.name.toLowerCase().includes(query) || def.shortName.toLowerCase().includes(query);
            return matchesCat && matchesQuery;
        });

        if (list.length === 0) {
            container.innerHTML = '<div style="padding:24px; text-align:center; color:var(--text-muted); font-size:13px;">No matching indicators found</div>';
            return;
        }

        container.innerHTML = list.map(def => {
            const isActive = this.activeIndicators.some(a => a.type === def.id && a.visible);
            return `
                <div class="indicator-item-row" style="display:flex; items-center; justify-content:space-between; padding:10px 14px; background:var(--bg-primary); border:1px solid var(--border); border-radius:8px; transition:all 0.15s;">
                    <div>
                        <div style="font-weight:600; font-size:13px; color:var(--text-primary); display:flex; align-items:center; gap:8px;">
                            ${def.name}
                            <span style="font-size:10px; background:rgba(255,255,255,0.06); color:var(--text-muted); padding:2px 6px; border-radius:4px; font-weight:500;">${def.category}</span>
                        </div>
                        <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">Type: ${def.type === 'overlay' ? 'Overlay on Price Chart' : 'Sub-pane Oscillator'}</div>
                    </div>
                    <button class="btn-sm ${isActive ? 'btn-danger' : 'btn-primary'}" onclick="ChartIndicatorRegistry.toggleIndicator('${def.id}')" style="padding:4px 12px; font-size:12px;">
                        ${isActive ? 'Remove' : 'Add'}
                    </button>
                </div>
            `;
        }).join('');

        const activeCount = this.activeIndicators.filter(a => a.visible).length;
        const countLabel = document.getElementById('activeCountLabel');
        if (countLabel) countLabel.textContent = `${activeCount} active indicator${activeCount !== 1 ? 's' : ''}`;
    },

    toggleIndicator(defId) {
        const existingIdx = this.activeIndicators.findIndex(a => a.type === defId);
        if (existingIdx >= 0) {
            this.activeIndicators[existingIdx].visible = !this.activeIndicators[existingIdx].visible;
        } else {
            const def = this.definitions[defId];
            if (def) {
                this.activeIndicators.push({
                    id: defId + '_' + Date.now(),
                    type: defId,
                    settings: { ...def.defaultSettings },
                    visible: true
                });
            }
        }
        this.saveState();
        this.renderList();
        if (typeof loadChartChart === 'function') loadChartChart();
    },

    applyTemplate(name) {
        if (name === 'Trend') {
            this.activeIndicators = [
                { id: 'ema9', type: 'ema', settings: { period: 9, color: '#38bdf8', width: 1 }, visible: true },
                { id: 'ema21', type: 'ema', settings: { period: 21, color: '#3b82f6', width: 2 }, visible: true },
                { id: 'ema50', type: 'ema', settings: { period: 50, color: '#f59e0b', width: 2 }, visible: true },
                { id: 'ema200', type: 'ema', settings: { period: 200, color: '#a855f7', width: 2 }, visible: true }
            ];
        } else if (name === 'Intraday') {
            this.activeIndicators = [
                { id: 'vwap', type: 'vwap', settings: { color: '#eab308', width: 2 }, visible: true },
                { id: 'rsi', type: 'rsi', settings: { period: 14, color: '#38bdf8' }, visible: true }
            ];
        } else if (name === 'ORB') {
            this.activeIndicators = [
                { id: 'orb', type: 'orb', settings: { color: '#3b82f6' }, visible: true },
                { id: 'vwap', type: 'vwap', settings: { color: '#eab308', width: 2 }, visible: true },
                { id: 'ema9', type: 'ema', settings: { period: 9, color: '#38bdf8', width: 1 }, visible: true },
                { id: 'rsi', type: 'rsi', settings: { period: 14, color: '#38bdf8' }, visible: true }
            ];
        } else if (name === 'Minimal') {
            this.activeIndicators = [
                { id: 'sma50', type: 'sma', settings: { period: 50, color: '#f59e0b', width: 2 }, visible: true }
            ];
        }
        this.saveState();
        this.renderList();
        if (typeof loadChartChart === 'function') loadChartChart();
    },

    saveState() {
        if (window.ChartState) {
            ChartState.indicators = this.activeIndicators;
            ChartState.save();
        }
    }
};

window.ChartIndicatorRegistry = ChartIndicatorRegistry;
