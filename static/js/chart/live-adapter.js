/**
 * StockPulse Pro — Live WebSocket Tick / Candle Adapter
 */
const ChartLiveAdapter = {
    normalizeTick(tick) {
        if (!tick) return null;
        return {
            symbol: tick.symbol || '',
            price: Number(tick.price || tick.last_price || 0),
            change: Number(tick.change || 0),
            changePercent: Number(tick.changePercent || tick.change_percent || 0),
            timestamp: tick.timestamp || new Date().toISOString()
        };
    },

    updateActiveCandle(candleSeries, candles, tick) {
        if (!candleSeries || !candles || candles.length === 0 || !tick) return candles;
        const lastCandle = candles[candles.length - 1];
        const price = tick.price;

        // Update high, low, close of current candle
        lastCandle.high = Math.max(lastCandle.high, price);
        lastCandle.low = Math.min(lastCandle.low, price);
        lastCandle.close = price;

        try {
            candleSeries.update(lastCandle);
        } catch (e) {
            console.error('Failed to update active candle series:', e);
        }

        return candles;
    }
};

window.ChartLiveAdapter = ChartLiveAdapter;
