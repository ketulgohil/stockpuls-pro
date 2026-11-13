/**
 * StockPulse Pro — Indicator Picker, Settings Modal & Templates Module
 */
const ChartIndicatorPicker = {
    modalEl: null,
    settingsModalEl: null,
    editingKey: null,
    controller: null,

    init(controller) {
        this.controller = controller;
        this.createPickerModal();
        this.createSettingsModal();
        this.createIndicatorsButton();
    },

    createIndicatorsButton() {
        const toolbar = document.querySelector('.chart-top-toolbar');
        if (!toolbar || document.getElementById('chartIndicatorsBtn')) return;

        const btn = document.createElement('button');
        btn.id = 'chartIndicatorsBtn';
        btn.className = 'tf-btn';
        btn.title = 'Indicators & Overlays (F2)';
        btn.style.cssText = 'display:flex; align-items:center; gap:4px; font-weight:600; color:var(--accent); border-color:var(--accent-glow);';
        btn.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
            </svg>
            <span>Indicators</span>
        `;
        btn.onclick = () => this.openPicker();

        // Insert before timeframe buttons
        const controls = toolbar.querySelector('.chart-controls');
        if (controls) {
            toolbar.insertBefore(btn, controls);
        } else {
            toolbar.appendChild(btn);
        }
    },

    createPickerModal() {
        if (document.getElementById('indicatorPickerModal')) return;

        const modal = document.createElement('div');
        modal.id = 'indicatorPickerModal';
        modal.className = 'modal-backdrop';
        modal.style.cssText = 'position:fixed; inset:0; background:rgba(0,0,0,0.7); backdrop-filter:blur(4px); z-index:1000; display:none; align-items:center; justify-content:center; padding:16px;';

        modal.innerHTML = `
            <div class="modal-card" style="background:var(--bg-card); border:1px solid var(--border); border-radius:12px; width:100%; max-width:640px; max-height:85vh; display:flex; flex-direction:column; overflow:hidden; box-shadow:0 20px 40px rgba(0,0,0,0.6);">
                <!-- Header -->
                <div style="padding:16px 20px; border-bottom:1px solid var(--border); display:flex; align-items:center; justify-content:space-between;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
                        <h3 style="font-size:16px; font-weight:700; color:var(--text-primary); margin:0;">Indicator Library & Templates</h3>
                    </div>
                    <button class="btn-sm icon-btn" onclick="ChartIndicatorPicker.closePicker()" style="width:28px; height:28px; border:none; background:transparent; color:var(--text-muted); cursor:pointer;">✕</button>
                </div>

                <!-- Templates Strip -->
                <div style="padding:12px 20px; background:var(--bg-secondary); border-bottom:1px solid var(--border); display:flex; align-items:center; gap:8px; overflow-x:auto;">
                    <span style="font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; white-space:nowrap;">Templates:</span>
                    <button class="btn-sm" onclick="ChartIndicatorPicker.applyTemplate('trend')" style="font-size:11px; padding:4px 8px; border-radius:6px; background:var(--bg-card); border:1px solid var(--border); color:var(--text-primary); cursor:pointer;">📈 Trend</button>
                    <button class="btn-sm" onclick="ChartIndicatorPicker.applyTemplate('intraday')" style="font-size:11px; padding:4px 8px; border-radius:6px; background:var(--bg-card); border:1px solid var(--border); color:var(--text-primary); cursor:pointer;">⚡ Intraday</button>
                    <button class="btn-sm" onclick="ChartIndicatorPicker.applyTemplate('orb')" style="font-size:11px; padding:4px 8px; border-radius:6px; background:var(--bg-card); border:1px solid var(--border); color:var(--text-primary); cursor:pointer;">🎯 ORB Breakout</button>
                    <button class="btn-sm" onclick="ChartIndicatorPicker.applyTemplate('minimal')" style="font-size:11px; padding:4px 8px; border-radius:6px; background:var(--bg-card); border:1px solid var(--border); color:var(--text-primary); cursor:pointer;">🧹 Minimal</button>
                </div>

                <!-- Search Input -->
                <div style="padding:12px 20px; border-bottom:1px solid var(--border);">
                    <input type="text" id="indicatorSearchInput" placeholder="Search indicators, oscillators, tools..." style="width:100%; padding:10px 14px; background:var(--bg-primary); border:1px solid var(--border); border-radius:8px; color:var(--text-primary); font-size:13px; outline:none;" oninput="ChartIndicatorPicker.filterIndicators(this.value)">
                </div>

                <!-- Category Tabs & List -->
                <div style="flex:1; overflow-y:auto; padding:16px 20px;" id="indicatorPickerList">
                    <!-- Dynamic categories populated by renderPickerList() -->
                </div>

                <!-- Footer -->
                <div style="padding:12px 20px; border-top:1px solid var(--border); background:var(--bg-secondary); display:flex; justify-content:space-between; align-items:center;">
                    <span id="activeIndicatorsCount" style="font-size:12px; color:var(--text-muted);">0 Active Indicators</span>
                    <button class="btn-sm danger" onclick="ChartIndicatorPicker.resetAll()" style="font-size:11px; padding:6px 12px; border-radius:6px; background:rgba(239,68,68,0.1); color:#ef4444; border:1px solid rgba(239,68,68,0.2); cursor:pointer;">Clear All</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        this.modalEl = modal;

        modal.addEventListener('click', (e) => {
            if (e.target === modal) this.closePicker();
        });
    },

    createSettingsModal() {
        if (document.getElementById('indicatorSettingsModal')) return;

        const modal = document.createElement('div');
        modal.id = 'indicatorSettingsModal';
        modal.className = 'modal-backdrop';
        modal.style.cssText = 'position:fixed; inset:0; background:rgba(0,0,0,0.7); backdrop-filter:blur(4px); z-index:1010; display:none; align-items:center; justify-content:center; padding:16px;';

        modal.innerHTML = `
            <div class="modal-card" style="background:var(--bg-card); border:1px solid var(--border); border-radius:12px; width:100%; max-width:400px; display:flex; flex-direction:column; overflow:hidden; box-shadow:0 20px 40px rgba(0,0,0,0.6);">
                <div style="padding:16px 20px; border-bottom:1px solid var(--border); display:flex; align-items:center; justify-content:space-between;">
                    <h3 id="settingsModalTitle" style="font-size:15px; font-weight:700; color:var(--text-primary); margin:0;">Indicator Settings</h3>
                    <button class="btn-sm icon-btn" onclick="ChartIndicatorPicker.closeSettings()" style="width:28px; height:28px; border:none; background:transparent; color:var(--text-muted); cursor:pointer;">✕</button>
                </div>

                <div id="settingsFormBody" style="padding:20px; display:flex; flex-direction:column; gap:16px;">
                    <!-- Dynamic form inputs -->
                </div>

                <div style="padding:12px 20px; border-top:1px solid var(--border); background:var(--bg-secondary); display:flex; justify-content:flex-end; gap:8px;">
                    <button class="btn-secondary" onclick="ChartIndicatorPicker.closeSettings()" style="padding:6px 14px; font-size:12px;">Cancel</button>
                    <button class="btn-primary" onclick="ChartIndicatorPicker.saveSettings()" style="padding:6px 14px; font-size:12px;">Save Changes</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        this.settingsModalEl = modal;

        modal.addEventListener('click', (e) => {
            if (e.target === modal) this.closeSettings();
        });
    },

    openPicker() {
        if (!this.modalEl) return;
        this.renderPickerList();
        this.modalEl.style.display = 'flex';
        const input = document.getElementById('indicatorSearchInput');
        if (input) {
            input.value = '';
            input.focus();
        }
    },

    closePicker() {
        if (this.modalEl) this.modalEl.style.display = 'none';
    },

    renderPickerList(query = '') {
        const container = document.getElementById('indicatorPickerList');
        if (!container || !window.ChartIndicatorRegistry || !window.ChartState) return;

        const activeMap = window.ChartState.indicators || {};
        const available = window.ChartIndicatorRegistry.available || [];
        const q = query.toLowerCase().trim();

        // Group by category
        const categories = {};
        available.forEach(ind => {
            if (q && !ind.name.toLowerCase().includes(q) && !ind.category.toLowerCase().includes(q) && !(ind.description || '').toLowerCase().includes(q)) {
                return;
            }
            if (!categories[ind.category]) categories[ind.category] = [];
            categories[ind.category].push(ind);
        });

        let activeCount = 0;
        let html = '';

        Object.keys(categories).forEach(cat => {
            html += `
                <div style="margin-bottom:16px;">
                    <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.6px; margin-bottom:8px;">${cat}</div>
                    <div style="display:flex; flex-direction:column; gap:6px;">
            `;

            categories[cat].forEach(ind => {
                const isActive = !!activeMap[ind.key];
                if (isActive) activeCount++;

                html += `
                    <div style="display:flex; align-items:center; justify-content:space-between; padding:10px 14px; background:var(--bg-secondary); border:1px solid ${isActive ? 'var(--accent)' : 'var(--border)'}; border-radius:8px; transition:all 0.15s;">
                        <div style="display:flex; align-items:center; gap:10px;">
                            <span style="width:12px; height:12px; border-radius:50%; background:${ind.color}; display:inline-block;"></span>
                            <div>
                                <div style="font-size:13px; font-weight:600; color:var(--text-primary);">${ind.name}</div>
                                <div style="font-size:11px; color:var(--text-muted);">${ind.description || ''}</div>
                            </div>
                        </div>
                        <div style="display:flex; align-items:center; gap:6px;">
                            <button class="btn-sm" onclick="ChartIndicatorPicker.openSettings('${ind.key}')" title="Configure indicator settings" style="padding:4px 8px; font-size:11px; background:var(--bg-card); border:1px solid var(--border); color:var(--text-secondary); border-radius:6px; cursor:pointer;">⚙️ Settings</button>
                            <button class="btn-sm ${isActive ? 'active' : ''}" onclick="ChartIndicatorPicker.toggleIndicator('${ind.key}')" style="padding:4px 12px; font-size:11px; font-weight:600; border-radius:6px; cursor:pointer; background:${isActive ? 'var(--accent)' : 'var(--bg-card)'}; color:${isActive ? 'white' : 'var(--text-primary)'}; border:1px solid ${isActive ? 'var(--accent)' : 'var(--border)'};">
                                ${isActive ? '✓ Added' : '+ Add'}
                            </button>
                        </div>
                    </div>
                `;
            });

            html += `</div></div>`;
        });

        if (html === '') {
            html = `<div style="text-align:center; padding:32px; color:var(--text-muted); font-size:13px;">No matching indicators found for "${query}"</div>`;
        }

        container.innerHTML = html;

        const countEl = document.getElementById('activeIndicatorsCount');
        if (countEl) countEl.textContent = `${activeCount} Active Indicator${activeCount === 1 ? '' : 's'}`;
    },

    filterIndicators(query) {
        this.renderPickerList(query);
    },

    toggleIndicator(key) {
        if (!window.ChartState) return;
        window.ChartState.indicators = window.ChartState.indicators || {};
        window.ChartState.indicators[key] = !window.ChartState.indicators[key];
        window.ChartState.save();

        this.renderPickerList();
        if (this.controller) {
            this.controller.renderActiveIndicators();
        }
    },

    openSettings(key) {
        if (!window.ChartIndicatorRegistry) return;
        const meta = window.ChartIndicatorRegistry.available.find(i => i.key === key);
        if (!meta) return;

        this.editingKey = key;
        const titleEl = document.getElementById('settingsModalTitle');
        if (titleEl) titleEl.textContent = `${meta.name} Settings`;

        const formBody = document.getElementById('settingsFormBody');
        if (!formBody) return;

        let html = '';
        if (meta.period !== undefined) {
            html += `
                <div style="display:flex; flex-direction:column; gap:6px;">
                    <label style="font-size:12px; font-weight:600; color:var(--text-secondary);">Period / Lookback Window</label>
                    <input type="number" id="settingPeriod" value="${meta.period}" min="1" max="500" style="padding:8px 12px; background:var(--bg-primary); border:1px solid var(--border); border-radius:6px; color:var(--text-primary); font-size:13px;">
                </div>
            `;
        }
        if (meta.color !== undefined) {
            html += `
                <div style="display:flex; flex-direction:column; gap:6px;">
                    <label style="font-size:12px; font-weight:600; color:var(--text-secondary);">Line Color</label>
                    <input type="color" id="settingColor" value="${meta.color}" style="width:100%; height:38px; padding:2px; background:var(--bg-primary); border:1px solid var(--border); border-radius:6px; cursor:pointer;">
                </div>
            `;
        }

        if (html === '') {
            html = `<div style="font-size:13px; color:var(--text-muted); text-align:center; padding:16px;">This indicator uses standard default parameters.</div>`;
        }

        formBody.innerHTML = html;
        if (this.settingsModalEl) this.settingsModalEl.style.display = 'flex';
    },

    closeSettings() {
        if (this.settingsModalEl) this.settingsModalEl.style.display = 'none';
        this.editingKey = null;
    },

    saveSettings() {
        if (!this.editingKey || !window.ChartIndicatorRegistry) return;
        const meta = window.ChartIndicatorRegistry.available.find(i => i.key === this.editingKey);
        if (meta) {
            const periodInput = document.getElementById('settingPeriod');
            if (periodInput && meta.period !== undefined) {
                meta.period = parseInt(periodInput.value, 10) || meta.period;
            }
            const colorInput = document.getElementById('settingColor');
            if (colorInput && meta.color !== undefined) {
                meta.color = colorInput.value;
            }
        }
        this.closeSettings();
        this.renderPickerList();
        if (this.controller) {
            this.controller.renderActiveIndicators();
        }
    },

    applyTemplate(templateName) {
        if (!window.ChartState || !window.ChartIndicatorRegistry) return;
        const templates = window.ChartIndicatorRegistry.templates || {};
        const activeKeys = templates[templateName] || [];

        const indicators = {};
        window.ChartIndicatorRegistry.available.forEach(ind => {
            indicators[ind.key] = activeKeys.includes(ind.key);
        });

        window.ChartState.indicators = indicators;
        window.ChartState.save();

        this.renderPickerList();
        if (this.controller) {
            this.controller.renderActiveIndicators();
        }
    },

    resetAll() {
        if (!window.ChartState) return;
        window.ChartState.indicators = {};
        window.ChartState.save();
        this.renderPickerList();
        if (this.controller) {
            this.controller.renderActiveIndicators();
        }
    }
};

window.ChartIndicatorPicker = ChartIndicatorPicker;
