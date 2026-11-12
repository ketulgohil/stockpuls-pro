/**
 * StockPulse Pro — Chart Toolbar & Panel Manager (Phase 1 Completion)
 */
const ChartToolbarManager = {
    init() {
        this.injectToolbarEnhancements();
    },

    injectToolbarEnhancements() {
        const toolbar = document.querySelector('.chart-top-toolbar');
        if (!toolbar) return;

        // Check if toolbar actions already injected
        if (document.getElementById('chartToolbarExtras')) return;

        const extras = document.createElement('div');
        extras.id = 'chartToolbarExtras';
        extras.style.cssText = 'display:flex; align-items:center; gap:8px; margin-left:auto;';
        extras.innerHTML = `
            <button class="btn-secondary btn-sm" onclick="ChartToolbarManager.toggleStrategyOverlay()" title="Toggle ORB & Strategy Levels" id="stratToggleBtn" style="font-size:11px; padding:4px 8px;">
                ⚡ Strategy: ON
            </button>
            <button class="btn-secondary btn-sm" onclick="ChartToolbarManager.toggleRightPanel()" title="Toggle Right Panel" id="rightPanelToggleBtn" style="font-size:11px; padding:4px 8px;">
                sidebar ☰
            </button>
        `;
        toolbar.appendChild(extras);

        // Inject Bottom Status Bar if not exists
        const mainColumn = document.querySelector('.chart-main-column');
        if (mainColumn && !document.getElementById('chartStatusBar')) {
            const statusBar = document.createElement('div');
            statusBar.id = 'chartStatusBar';
            statusBar.style.cssText = 'display:flex; justify-content:space-between; align-items:center; padding:6px 14px; background:var(--bg-surface); border-top:1px solid var(--border); font-size:11px; color:var(--text-muted); font-family:var(--font-mono);';
            statusBar.innerHTML = `
                <div style="display:flex; gap:16px; align-items:center;">
                    <span>Session: <strong style="color:var(--emerald);">NSE Live</strong></span>
                    <span>Interval: <strong id="statusInterval">1D</strong></span>
                    <span>Status: <strong id="statusLiveState" style="color:var(--emerald);">Connected</strong></span>
                </div>
                <div>
                    Last Update: <span id="statusLastUpdate">--:--:--</span>
                </div>
            `;
            mainColumn.appendChild(statusBar);
        }
    },

    toggleStrategyOverlay() {
        const badges = document.getElementById('chartStrategyBadgesChart');
        const btn = document.getElementById('stratToggleBtn');
        if (!badges || !btn) return;
        if (badges.style.display === 'none') {
            badges.style.display = 'flex';
            btn.textContent = '⚡ Strategy: ON';
            btn.style.borderColor = 'var(--accent)';
        } else {
            badges.style.display = 'none';
            btn.textContent = '⚡ Strategy: OFF';
            btn.style.borderColor = 'var(--border)';
        }
    },

    toggleRightPanel() {
        const watchlist = document.querySelector('.chart-sidebar-watchlist');
        if (!watchlist) return;
        if (watchlist.style.display === 'none') {
            watchlist.style.display = 'flex';
        } else {
            watchlist.style.display = 'none';
        }
    }
};

window.ChartToolbarManager = ChartToolbarManager;
document.addEventListener('DOMContentLoaded', () => {
    ChartToolbarManager.init();
});
