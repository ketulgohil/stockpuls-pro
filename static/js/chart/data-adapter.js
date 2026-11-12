/**
 * StockPulse Pro — Chart Data Adapter
 */
const ChartDataAdapter = {
    normalizeCandles(rawCandles) {
        if (!Array.isArray(rawCandles)) return [];
        return rawCandles.map(d => ({
            time: d.date || d.time,
            open: Number(d.open),
            high: Number(d.high),
            low: Number(d.low),
            close: Number(d.close),
            volume: Number(d.volume || 0)
        })).sort((a, b) => new Date(a.time) - new Date(b.time));
    },

    normalizeVolumes(candles) {
        return candles.map(d => ({
            time: d.time,
            value: d.volume,
            color: d.close >= d.open ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'
        }));
    }
};

window.ChartDataAdapter = ChartDataAdapter;
