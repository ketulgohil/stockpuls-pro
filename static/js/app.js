let chart = null;
let candleSeries = null;
let volumeSeries = null;
let currentSymbol = 'RELIANCE.NS';
let currentTimeframe = '1d';
let liveInterval = null;

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

// API Helper
async function api(url, options = {}) {
    try {
        const res = await fetch(url, {
            headers: { 'Content-Type': 'application/json' },
            ...options
        });
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

// Tab Navigation
function showTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    
    document.getElementById(tabName).classList.add('active');
    document.querySelector(`.nav-item[data-tab="${tabName}"]`).classList.add('active');
    
    localStorage.setItem('lastTab', tabName);
    
    // Load data for specific tabs
    switch(tabName) {
        case 'dashboard': loadChart(); loadDashboardGainersLosers(); break;
        case 'market': loadMarket(); setTimeout(loadOptionChain, 500); break;
        case 'signals': loadSignals(); break;
        case 'sector': loadSectors(); break;
        case 'news': loadNews(); break;
        case 'ai': loadAiTab(); break;
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
        case 'portfolio': loadPortfolio(); loadPortfolioAnalytics(); break;
        case 'watchlist': loadWatchlist(); break;
        case 'analysis': loadAlerts(); break;
    }
}

// Chart Functions
function initChart() {
    const container = document.getElementById('chartContainer');
    if (!container) return;
    
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
        wickUpColor: '#10b981'
    });

    volumeSeries = chart.addHistogramSeries({
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume'
    });

    chart.priceScale('volume').applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 }
    });

    new ResizeObserver(() => {
        chart.applyOptions({ width: container.clientWidth });
    }).observe(container);
}

async function loadChart() {
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

        if (data.data && data.data.length > 0) {
            const candles = data.data.map(d => ({
                time: d.date,
                open: d.open,
                high: d.high,
                low: d.low,
                close: d.close
            }));

            const volumes = data.data.map(d => ({
                time: d.date,
                value: d.volume,
                color: d.close >= d.open ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'
            }));

            candleSeries.setData(candles);
            volumeSeries.setData(volumes);
            chart.timeScale().fitContent();
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
                            <tr onclick="selectStock('${s.symbol}')" style="cursor:pointer">
                                <td><strong>${s.name}</strong></td>
                                <td>${fmtPrice(s.price)}</td>
                                <td class="positive">+${fmtPct(s.changePercent)}</td>
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
                            <tr onclick="selectStock('${s.symbol}')" style="cursor:pointer">
                                <td><strong>${s.name}</strong></td>
                                <td>${fmtPrice(s.price)}</td>
                                <td class="negative">${fmtPct(s.changePercent)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }
    } catch (err) {
        console.error('Dashboard gainers/losers error:', err);
    }
}

// Stock Selection
function selectStock(symbol) {
    currentSymbol = symbol;
    document.getElementById('currentStockName').textContent = symbol.replace('.NS', '');
    const ss = document.getElementById('stockSearch');
    if (ss) ss.value = symbol;
    localStorage.setItem('lastStock', symbol);
    loadChart();
}

// Search
document.getElementById('searchInput')?.addEventListener('input', async (e) => {
    const q = e.target.value.trim();
    if (q.length < 2) {
        document.getElementById('searchResults').classList.remove('active');
        return;
    }
    
    const data = await api(`/api/stocks/search?q=${encodeURIComponent(q)}`);
    const container = document.getElementById('searchResults');
    
    if (data.results && data.results.length > 0) {
        container.innerHTML = data.results.slice(0, 10).map(r => `
            <div class="search-item" onclick="selectStock('${r.symbol}')">
                <strong>${r.symbol.replace('.NS', '')}</strong>
                <small style="color: var(--text-muted); margin-left: 8px;">${r.name || ''}</small>
            </div>
        `).join('');
        container.classList.add('active');
    } else {
        container.classList.remove('active');
    }
});

// Market
async function loadMarket() {
    const data = await api('/api/market');
    const container = document.getElementById('marketData');
    
    if (data.indices) {
        container.innerHTML = data.indices.map(idx => `
            <div class="index-card">
                <div class="name">${idx.name}</div>
                <div class="value">${fmtPrice(idx.price)}</div>
                <div class="change ${idx.change >= 0 ? 'positive' : 'negative'}">
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
                        <tr onclick="selectStock('${s.symbol}'); showTab('dashboard')" style="cursor:pointer">
                            <td><strong>${s.name}</strong></td>
                            <td>${fmtPrice(s.price)}</td>
                            <td class="positive">+${fmtPct(s.changePercent)}</td>
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
                        <tr onclick="selectStock('${s.symbol}'); showTab('dashboard')" style="cursor:pointer">
                            <td><strong>${s.name}</strong></td>
                            <td>${fmtPrice(s.price)}</td>
                            <td class="negative">${fmtPct(s.changePercent)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }
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
                        <tr>
                            <td><strong>${s.name || s.symbol.replace('.NS', '')}</strong></td>
                            <td><span class="badge ${s.type === 'BUY' ? 'positive' : s.type === 'SELL' ? 'negative' : ''}">${s.type}</span></td>
                            <td>${s.indicator || '-'}</td>
                            <td>${s.strength || '-'}</td>
                            <td>₹${s.price}</td>
                            <td><button class="btn-primary" onclick="selectStock('${s.symbol}'); showTab('dashboard')">View</button></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }
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
                            <tr>
                                <td><strong>${s.name}</strong></td>
                            <td>${fmtPrice(s.price)}</td>
                                <td class="${s.changePercent >= 0 ? 'positive' : 'negative'}">${fmtPct(s.changePercent)}</td>
                                <td>${s.rsi?.toFixed(2) || '-'}</td>
                                <td>${s.macd?.toFixed(2) || '-'}</td>
                                <td><button class="btn-primary" onclick="selectStock('${s.symbol}'); showTab('dashboard')">View</button></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } else {
        container.innerHTML = '<div class="card"><p class="placeholder">No stocks match your criteria</p></div>';
    }
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
    
    if (data.news && data.news.length > 0) {
        container.innerHTML = data.news.map(n => `
            <div class="news-item">
                <h4>${n.title}</h4>
                <p>${n.summary || ''}</p>
                <div class="news-meta">${n.publisher || ''} • ${n.published || ''}</div>
            </div>
        `).join('');
    }
}

async function loadStockNews() {
    const symbol = document.getElementById('newsSymbol').value;
    const data = await api(`/api/news/${symbol}`);
    const container = document.getElementById('stockNews');
    
    if (data.news && data.news.length > 0) {
        container.innerHTML = data.news.map(n => `
            <div class="news-item">
                <h4>${n.title}</h4>
                <p>${n.summary || ''}</p>
                <div class="news-meta">${n.publisher || ''} • ${n.published || ''}</div>
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
    
    if (data.holdings && data.holdings.length > 0) {
        container.innerHTML = `
            <table>
                <thead><tr><th>Symbol</th><th>Qty</th><th>Buy Price</th><th>P&L</th><th>Action</th></tr></thead>
                <tbody>
                    ${data.holdings.map(h => `
                        <tr>
                            <td><strong>${h.symbol.replace('.NS', '')}</strong></td>
                            <td>${h.quantity}</td>
                            <td>₹${h.buyPrice}</td>
                            <td class="${h.pnl >= 0 ? 'positive' : 'negative'}">${h.pnl >= 0 ? '+' : ''}₹${h.pnl?.toFixed(2) || '0'}</td>
                            <td><button class="btn-danger" onclick="removePortfolio('${h.symbol}')">Remove</button></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        container.innerHTML = '<p class="placeholder">No holdings yet</p>';
    }
}

async function addPortfolio() {
    const symbol = document.getElementById('portfolioSymbol').value;
    const qty = parseInt(document.getElementById('portfolioQty').value);
    const price = parseFloat(document.getElementById('portfolioPrice').value);
    
    if (!symbol || !qty || !price) return showToast('Fill all fields', 'warning');
    
    await api('/api/portfolio', {
        method: 'POST',
        body: JSON.stringify({ symbol, quantity: qty, buyPrice: price })
    });
    
    loadPortfolio();
}

async function removePortfolio(symbol) {
    await api(`/api/portfolio/${symbol}`, { method: 'DELETE' });
    loadPortfolio();
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
                        <tr>
                            <td><strong>${w.symbol.replace('.NS', '')}</strong></td>
                            <td>${fmtPrice(w.price)}</td>
                            <td class="${(w.changePercent || 0) >= 0 ? 'positive' : 'negative'}">${fmtPct(w.changePercent || 0)}</td>
                            <td>
                                <button class="btn-primary" onclick="selectStock('${w.symbol}'); showTab('dashboard')">View</button>
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
        const data = await api(`/api/stocks/search?q=${query}`);
        if (data.results && data.results.length > 0) {
            container.innerHTML = data.results.map(s => `
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
        const data = await api(`/api/stocks/search?q=${query}`);
        if (data.results && data.results.length > 0) {
            container.innerHTML = data.results.map(s => `
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

// Stock search for main topbar
let mainSearchTimeout = null;
async function searchStockForMain(query) {
    const container = document.getElementById('stockSearchSuggestions');
    if (!container) return;
    
    if (query.length < 1) {
        container.innerHTML = '';
        container.style.display = 'none';
        return;
    }
    
    clearTimeout(mainSearchTimeout);
    mainSearchTimeout = setTimeout(async () => {
        const data = await api(`/api/stocks/search?q=${query}`);
        if (data.results && data.results.length > 0) {
            container.innerHTML = data.results.map(s => `
                <div class="suggestion-item" onclick="selectMainStock('${s.symbol}', '${s.name}')">
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

function selectMainStock(symbol, name) {
    selectStock(symbol);
    document.getElementById('stockSearch').value = '';
    document.getElementById('stockSearchSuggestions').innerHTML = '';
    document.getElementById('stockSearchSuggestions').style.display = 'none';
}

// Close suggestions when clicking outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.stock-selector') && !e.target.closest('.watchlist-form') && !e.target.closest('.portfolio-form')) {
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
                        <div class="trending-item" onclick="selectStock('${s.symbol}'); showTab('dashboard')" style="cursor:pointer">
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

// Live Updates
function startLiveUpdates() {
    if (liveInterval) clearInterval(liveInterval);
    liveInterval = setInterval(async () => {
        const data = await api(`/api/stocks/${currentSymbol}/live`);
        if (data && data.price) {
            document.getElementById('livePrice').textContent = `₹${data.price}`;
            document.getElementById('chartPrice').textContent = `₹${data.price}`;
        }
    }, 30000);
}

// Keyboard Shortcuts
document.addEventListener('keydown', (e) => {
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
                                 onclick="selectStock('${stock.symbol}'); showTab('dashboard')"
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
    
    if (data.error) {
        container.innerHTML = `<p class="placeholder">${data.error}</p>`;
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
async function loadPortfolioAnalytics() {
    const container = document.getElementById('portfolioAnalytics');
    container.innerHTML = '<p class="placeholder">Loading analytics...</p>';
    
    const data = await api('/api/analytics/portfolio');
    
    if (data.error) {
        container.innerHTML = `<p class="placeholder">${data.error}</p>`;
        return;
    }
    
    const summary = data.summary;
    
    container.innerHTML = `
        <div class="analytics-summary">
            <div class="analytics-card">
                <span class="label">Invested</span>
                <span class="value">₹${summary.totalInvested.toLocaleString()}</span>
            </div>
            <div class="analytics-card">
                <span class="label">Current Value</span>
                <span class="value">₹${summary.totalCurrentValue.toLocaleString()}</span>
            </div>
            <div class="analytics-card">
                <span class="label">P&L</span>
                <span class="value ${summary.totalPnL >= 0 ? 'positive' : 'negative'}">${summary.totalPnL >= 0 ? '+' : ''}₹${summary.totalPnL.toLocaleString()}</span>
            </div>
            <div class="analytics-card">
                <span class="label">Return</span>
                <span class="value ${summary.totalReturn >= 0 ? 'positive' : 'negative'}">${summary.totalReturn >= 0 ? '+' : ''}${summary.totalReturn}%</span>
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
                ${data.topPerformers.map(p => `
                    <div class="performer-item positive">
                        <span>${p.name}</span>
                        <span>+${p.returnPercent}%</span>
                    </div>
                `).join('')}
                
                <h4 class="mt-2">Worst Performers</h4>
                ${data.worstPerformers.map(p => `
                    <div class="performer-item negative">
                        <span>${p.name}</span>
                        <span>${p.returnPercent}%</span>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
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

// ===== TOAST NOTIFICATION SYSTEM =====
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    requestAnimationFrame(() => { toast.classList.add('show'); });
    setTimeout(() => {
        toast.classList.remove('show');
        toast.classList.add('hide');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
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

function connectWebSocket() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/live-prices`;
    ws = new WebSocket(wsUrl);

    ws.onopen = function() {
        console.log('[WS] Connected to live prices');
        wsReconnectAttempts = 0;
        updateConnectionStatus('connected');

        // Send symbols to track
        ws.send(JSON.stringify({
            symbols: ['^NSEI', '^BSESN', '^NSEBANK', '^CNXIT', '^NSEMDCP50']
        }));
    };

    ws.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            if (data.prices) {
                updateMarketOverviewLive(data.prices);
            }
        } catch (e) {
            console.error('[WS] Parse error:', e);
        }
    };

    ws.onclose = function() {
        console.log('[WS] Disconnected');
        updateConnectionStatus('disconnected');
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
    };
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
            changeEl.className = priceData.change >= 0 ? 'positive' : 'negative';
        }
    }

    // Also update the topbar live price for the currently selected stock if we have data
    // (This is a bonus - the main chart still uses its own polling)
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
async function updateMarketPulse() {
    try {
        const data = await api('/api/market/pulse');
        const score = document.getElementById('pulseValue');
        const gaugeScore = document.getElementById('gaugeScore');
        const gaugeText = document.getElementById('gaugeText');
        const needle = document.getElementById('gaugeNeedle');

        if (score) score.textContent = `${data.score} - ${data.label}`;
        if (gaugeScore) gaugeScore.textContent = data.score;
        if (gaugeText) {
            gaugeText.textContent = data.label;
            gaugeText.style.color = data.color || '#ffaa00';
        }
        if (needle) {
            // Rotate needle: -90deg (bearish) to +90deg (bullish)
            const rotation = (data.score / 100) * 90;
            needle.style.transform = `rotate(${rotation}deg)`;
        }
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

async function loadOptionChain() {
    try {
        const response = await fetch('/api/options/chain');
        const data = await response.json();

        if (data.error) {
            console.error('Option chain error:', data.error);
            const tbody = document.getElementById('optionChainBody');
            if (tbody) tbody.innerHTML = `<tr><td colspan="11" class="loading-cell" style="color:var(--red);">Error: ${data.error}</td></tr>`;
            return;
        }

        // Update PCR badge
        const pcrBadge = document.getElementById('pcrBadge');
        if (pcrBadge) {
            pcrBadge.textContent = `PCR: ${data.putCallRatio}`;
            pcrBadge.className = `pcr-badge ${data.putCallRatio > 1.2 ? 'bullish' : (data.putCallRatio < 0.8 ? 'bearish' : 'neutral')}`;
        }

        // Update expiry dropdown
        const expirySelect = document.getElementById('optionExpiry');
        if (expirySelect && data.availableExpiries) {
            expirySelect.innerHTML = data.availableExpiries.map(e =>
                `<option value="${e}" ${e === data.expiry ? 'selected' : ''}>${e}</option>`
            ).join('');
        }

        // Build option chain table
        const tbody = document.getElementById('optionChainBody');
        if (!tbody) return;

        // Merge calls and puts by strike
        const strikes = [...new Set([
            ...data.calls.map(c => c.strike),
            ...data.puts.map(p => p.strike)
        ])].sort((a, b) => b - a);

        const currentPrice = data.currentPrice;
        const atmStrike = Math.round(currentPrice / 50) * 50;

        tbody.innerHTML = strikes.map(strike => {
            const call = data.calls.find(c => c.strike === strike) || {};
            const put = data.puts.find(p => p.strike === strike) || {};
            const isITMCall = strike <= currentPrice;
            const isITMPut = strike >= currentPrice;
            const isATM = strike === atmStrike;

            return `
                <tr class="${isITMCall ? 'itm-row' : ''}">
                    <td class="oi-cell">${call.openInterest ? call.openInterest.toLocaleString() : '-'}</td>
                    <td class="vol-cell">${call.volume ? call.volume.toLocaleString() : '-'}</td>
                    <td class="iv-cell">${call.impliedVolatility ? (call.impliedVolatility * 100).toFixed(1) + '%' : '-'}</td>
                    <td class="ltp-cell ${call.change > 0 ? 'positive' : (call.change < 0 ? 'negative' : '')}">
                        ${call.lastPrice || '-'}
                    </td>
                    <td class="change-cell ${call.change > 0 ? 'positive' : (call.change < 0 ? 'negative' : '')}">
                        ${call.change ? (call.change > 0 ? '+' : '') + call.change.toFixed(2) : '-'}
                    </td>
                    <td class="strike-cell ${isATM ? 'atm' : ''}">
                        ${strike}
                    </td>
                    <td class="change-cell ${put.change > 0 ? 'positive' : (put.change < 0 ? 'negative' : '')}">
                        ${put.change ? (put.change > 0 ? '+' : '') + put.change.toFixed(2) : '-'}
                    </td>
                    <td class="ltp-cell ${put.change > 0 ? 'positive' : (put.change < 0 ? 'negative' : '')}">
                        ${put.lastPrice || '-'}
                    </td>
                    <td class="iv-cell">${put.impliedVolatility ? (put.impliedVolatility * 100).toFixed(1) + '%' : '-'}</td>
                    <td class="vol-cell">${put.volume ? put.volume.toLocaleString() : '-'}</td>
                    <td class="oi-cell">${put.openInterest ? put.openInterest.toLocaleString() : '-'}</td>
                </tr>
            `;
        }).join('');

    } catch (error) {
        console.error('Error loading option chain:', error);
    }
}

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
                <div class="volume-alert-item ${alert.signal.toLowerCase()}">
                    <div class="alert-left">
                        <span class="alert-symbol" onclick="selectStock('${alert.symbol}.NS'); showTab('dashboard')" style="cursor:pointer">${alert.symbol}</span>
                        <span class="alert-price">₹${alert.price}</span>
                    </div>
                    <div class="alert-center">
                        <span class="alert-change ${alert.change >= 0 ? 'positive' : 'negative'}">
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
    } catch (error) {
        console.error('Error loading volume alerts:', error);
    }
}

// ===== AUTO-REFRESH GAINERS/LOSERS =====
let gainersLosersInterval = null;

function startAutoRefreshGainersLosers() {
    // Refresh every 60 seconds
    gainersLosersInterval = setInterval(async () => {
        const activeTab = document.querySelector('.nav-item.active');
        if (activeTab) {
            const tabName = activeTab.getAttribute('data-tab');
            if (tabName === 'dashboard') {
                await loadDashboardGainersLosers();
            } else if (tabName === 'market') {
                await loadMarket();
            }
        }
    }, 60000);
}

// ===== PORTFOLIO LIVE P&L TICKER =====
let portfolioTickerInterval = null;

async function loadPortfolioTicker() {
    try {
        const response = await fetch('/api/portfolio/live-pnl');
        const data = await response.json();

        const ticker = document.getElementById('tickerContent');
        if (!ticker || !data.holdings || data.holdings.length === 0) return;

        // Create scrolling ticker content
        const tickerItems = data.holdings.map(h => `
            <span class="ticker-item" onclick="selectStock('${h.symbol}'); showTab('dashboard')" style="cursor:pointer">
                <span class="ticker-symbol">${h.symbol.replace('.NS', '')}</span>
                <span class="ticker-price">₹${h.currentPrice}</span>
                <span class="ticker-pnl ${h.pnl >= 0 ? 'positive' : 'negative'}">
                    ${h.pnl >= 0 ? '▲' : '▼'} ₹${Math.abs(h.pnl)} (${h.pnlPercent}%)
                </span>
            </span>
        `).join('');

        // Duplicate for seamless scroll
        ticker.innerHTML = tickerItems + tickerItems;
    } catch (error) {
        console.error('Error loading portfolio ticker:', error);
    }
}

function startPortfolioTicker() {
    loadPortfolioTicker();
    portfolioTickerInterval = setInterval(loadPortfolioTicker, 30000); // Every 30 seconds
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    // Theme auto-detection
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light') { document.body.classList.add('light-theme'); }
    else if (savedTheme === 'dark') { document.body.classList.remove('light-theme'); }
    else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
        document.body.classList.add('light-theme');
    }

    initChart();
    
    const lastStock = localStorage.getItem('lastStock');
    const lastTab = localStorage.getItem('lastTab');
    
    if (lastStock) {
        currentSymbol = lastStock;
        document.getElementById('currentStockName').textContent = lastStock.replace('.NS', '');
        const ss = document.getElementById('stockSearch');
        if (ss) ss.value = lastStock;
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
    startPortfolioTicker();

    // Refresh volume alerts every 5 minutes
    setTimeout(() => {
        loadVolumeAlerts();
        setInterval(loadVolumeAlerts, 300000);
    }, 2000);

    // Load option chain after a short delay
    setTimeout(loadOptionChain, 2000);
    // Refresh option chain every 2 minutes
    setInterval(loadOptionChain, 120000);

    // Connect WebSocket for live index prices
    setTimeout(connectWebSocket, 1000);
});
