/**
 * StockPulse Pro — Indicator Registry & Calculation Helper (Unified Chart Engine)
 */
const ChartIndicatorRegistry = {
    available: [
        { key: 'ema9', name: 'EMA 9', category: 'Trend', color: '#38bdf8' },
        { key: 'ema21', name: 'EMA 21', category: 'Trend', color: '#3b82f6' },
        { key: 'ema50', name: 'EMA 50', category: 'Trend', color: '#f59e0b' },
        { key: 'ema200', name: 'EMA 200', category: 'Trend', color: '#a855f7' },
        { key: 'vwap', name: 'VWAP & Bands', category: 'Volume', color: '#eab308' },
        { key: 'pivots', name: 'Camarilla Pivots', category: 'Support/Resistance', color: '#ec4899' },
        { key: 'orb', name: 'ORB Strategy Levels', category: 'Intraday', color: '#3b82f6' }
    ],

    computeEma(candles, period) {
        if (!candles || candles.length === 0) return [];
        const k = 2 / (period + 1);
        let ema = candles[0].close;
        const result = [{ time: candles[0].time, value: ema }];
        for (let i = 1; i < candles.length; i++) {
            ema = (candles[i].close * k) + (ema * (1 - k));
            result.push({ time: candles[i].time, value: Number(ema.toFixed(2)) });
        }
        return result;
    },

    computeVwap(candles) {
        if (!candles || candles.length === 0) return [];
        let cumPv = 0;
        let cumVol = 0;
        return candles.map(c => {
            const typicalPrice = (c.high + c.low + c.close) / 3;
            cumPv += typicalPrice * (c.volume || 0);
            cumVol += (c.volume || 0);
            const vwap = cumVol > 0 ? cumPv / cumVol : c.close;
            return { time: c.time, value: Number(vwap.toFixed(2)) };
        });
    }
};

window.ChartIndicatorRegistry = ChartIndicatorRegistry;
