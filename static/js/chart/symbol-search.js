/**
 * StockPulse Pro — TradingView-style Symbol Search & Header Module
 */
const ChartSymbolSearch = {
    recentSymbols: ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS'],

    init() {
        const input = document.getElementById('chartSymbolInput');
        if (!input) return;

        // Ensure container is relative for popover positioning
        const parent = input.parentElement;
        if (parent) parent.style.position = 'relative';

        // Create autocomplete suggestions dropdown if not exists
        let dropdown = document.getElementById('chartSymbolPopover');
        if (!dropdown) {
            dropdown = document.createElement('div');
            dropdown.id = 'chartSymbolPopover';
            dropdown.className = 'symbol-search-popover';
            dropdown.style.cssText = 'position:absolute; top:100%; left:0; right:0; background:var(--bg-card); border:1px solid var(--border); border-radius:8px; box-shadow:0 12px 32px rgba(0,0,0,0.5); z-index:100; display:none; max-height:280px; overflow-y:auto; margin-top:4px;';
            parent.appendChild(dropdown);
        }

        input.addEventListener('input', async (e) => {
            const query = e.target.value.trim();
            if (query.length < 1) {
                this.renderRecent(dropdown);
                return;
            }
            try {
                const results = await api(`/api/stocks/search?query=${encodeURIComponent(query)}`);
                this.renderResults(dropdown, results || []);
            } catch (err) {
                dropdown.style.display = 'none';
            }
        });

        input.addEventListener('focus', () => {
            this.renderRecent(dropdown);
        });

        document.addEventListener('click', (e) => {
            if (!parent.contains(e.target)) {
                dropdown.style.display = 'none';
            }
        });
    },

    renderRecent(dropdown) {
        dropdown.innerHTML = `
            <div style="padding:8px 12px; font-size:10px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; border-bottom:1px solid var(--border);">Recent Symbols</div>
            ${this.recentSymbols.map(sym => `
                <div class="popover-item" onclick="ChartSymbolSearch.selectSymbol('${sym}')" style="padding:8px 12px; cursor:pointer; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); transition:background 0.15s;">
                    <span style="font-weight:600; font-family:'JetBrains Mono',monospace; font-size:12px; color:var(--text-primary);">${displaySymbol(sym)}</span>
                    <span style="font-size:10px; color:var(--text-muted);">NSE</span>
                </div>
            `).join('')}
        `;
        dropdown.style.display = 'block';
    },

    renderResults(dropdown, results) {
        if (results.length === 0) {
            dropdown.innerHTML = '<div style="padding:12px; font-size:12px; color:var(--text-muted); text-align:center;">No symbols found</div>';
            dropdown.style.display = 'block';
            return;
        }
        dropdown.innerHTML = results.slice(0, 8).map(s => `
            <div class="popover-item" onclick="ChartSymbolSearch.selectSymbol('${s.symbol}')" style="padding:8px 12px; cursor:pointer; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); transition:background 0.15s;">
                <div>
                    <div style="font-weight:600; font-family:'JetBrains Mono',monospace; font-size:12px; color:var(--text-primary);">${displaySymbol(s.symbol)}</div>
                    <div style="font-size:10px; color:var(--text-muted);">${s.name || ''}</div>
                </div>
                <span style="font-size:10px; color:var(--accent); background:rgba(59,130,246,0.1); padding:2px 6px; border-radius:4px;">NSE</span>
            </div>
        `).join('');
        dropdown.style.display = 'block';
    },

    selectSymbol(symbol) {
        const input = document.getElementById('chartSymbolInput');
        if (input) input.value = normalizeSymbol(symbol);
        const dropdown = document.getElementById('chartSymbolPopover');
        if (dropdown) dropdown.style.display = 'none';

        if (!this.recentSymbols.includes(symbol)) {
            this.recentSymbols.unshift(symbol);
            if (this.recentSymbols.length > 5) this.recentSymbols.pop();
        }

        if (typeof selectStock === 'function') {
            selectStock(symbol);
        }
    }
};

window.ChartSymbolSearch = ChartSymbolSearch;
document.addEventListener('DOMContentLoaded', () => {
    ChartSymbolSearch.init();
});
