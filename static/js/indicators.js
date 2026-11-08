/**
 * trader-dashboard/static/indicators.js
 *
 * Dalal Street Pro Technical Analysis & Mathematical Indicators Library
 * Pure JavaScript, zero-dependency mathematical analysis module for:
 * - Multi-period Exponential Moving Average (EMA)
 * - Session-Anchored VWAP with Standard Deviation Bands (±1σ, ±2σ)
 * - Daily Camarilla (R4, R3, S3, S4) and Classic (PP, R1, S1, R2, S2) Pivots
 * - Wilder's Smoothed Relative Strength Index (RSI)
 * - Moving Average Convergence Divergence (MACD, Signal, Histogram)
 *
 * UMD pattern: exports to CommonJS / Node.js and window.Indicators in browsers.
 */

(function (root, factory) {
  "use strict";

  const exportsObj = factory();

  if (typeof module === "object" && module && module.exports) {
    module.exports = exportsObj;
  }
  if (root) {
    root.Indicators = exportsObj;
  }
}(typeof self !== "undefined" ? self : (typeof window !== "undefined" ? window : (typeof globalThis !== "undefined" ? globalThis : this)), function () {
  "use strict";

  // --- Helper Utilities ---

  function round2(num) {
    if (!Number.isFinite(num)) return 0;
    return Math.round((num + Number.EPSILON) * 100) / 100;
  }

  function getBarClose(bar) {
    if (!bar) return 0;
    if (bar.close !== undefined) return Number(bar.close);
    if (bar.value !== undefined) return Number(bar.value);
    if (bar.open !== undefined) return Number(bar.open);
    return 0;
  }

  /**
   * Helper: convert Unix timestamp (seconds) to IST date key "YYYY-MM-DD"
   * Offset: +05:30 = +19800 seconds
   */
  function toIstDateKey(seconds) {
    const d = new Date((seconds + 19800) * 1000);
    const y = d.getUTCFullYear();
    const m = String(d.getUTCMonth() + 1).padStart(2, "0");
    const day = String(d.getUTCDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  /**
   * Helper: get seconds elapsed within the current IST day (0 to 86399)
   * 09:15:00 IST = 9 * 3600 + 15 * 60 = 33300 seconds
   */
  function toIstSecondsInDay(seconds) {
    const rem = (seconds + 19800) % 86400;
    return rem < 0 ? rem + 86400 : rem;
  }

  // --- 1. Multi-Period Exponential Moving Average (EMA) ---

  /**
   * Compute EMA over an array of bars.
   * Requires at least `length` bars before emitting values.
   * Initial seed is Simple Moving Average (SMA) of first `length` bars.
   * Smoothing factor: alpha = 2 / (length + 1)
   *
   * @param {Array<Object>} bars - Array of { time, close, ... }
   * @param {number} length - Moving average window length (e.g. 9, 21, 50, 200)
   * @returns {Array<{time: number, value: number}>}
   */
  function computeEma(bars, length) {
    if (!Array.isArray(bars) || !length || length <= 0 || bars.length < length) {
      return [];
    }

    const n = Math.floor(length);
    const alpha = 2 / (n + 1);
    const result = [];

    // 1. Initial SMA seed of first `n` bars
    let sum = 0;
    for (let i = 0; i < n; i++) {
      sum += getBarClose(bars[i]);
    }
    let currentEma = sum / n;
    result.push({
      time: bars[n - 1].time,
      value: round2(currentEma),
    });

    // 2. Iterative EMA for remaining bars
    for (let i = n; i < bars.length; i++) {
      const close = getBarClose(bars[i]);
      currentEma = (close * alpha) + (currentEma * (1 - alpha));
      result.push({
        time: bars[i].time,
        value: round2(currentEma),
      });
    }

    return result;
  }

  // --- 2. Anchored Session VWAP with Standard Deviation Bands ---

  /**
   * Compute Session-Anchored VWAP with ±1σ and ±2σ volatility bands.
   * Resets session accumulators at `09:15:00 IST` boundary (timestamp + 19800 ≡ 33300)
   * or when the IST calendar date transitions.
   *
   * @param {Array<Object>} bars - Array of { time, high, low, close, volume }
   * @returns {{
   *   vwap: Array<{time: number, value: number}>,
   *   upper1: Array<{time: number, value: number}>,
   *   lower1: Array<{time: number, value: number}>,
   *   upper2: Array<{time: number, value: number}>,
   *   lower2: Array<{time: number, value: number}>
   * }}
   */
  function computeVwap(bars) {
    const emptyResult = {
      vwap: [],
      upper1: [],
      lower1: [],
      upper2: [],
      lower2: [],
    };

    if (!Array.isArray(bars) || bars.length === 0) {
      return emptyResult;
    }

    const vwap = [];
    const upper1 = [];
    const lower1 = [];
    const upper2 = [];
    const lower2 = [];

    const MARKET_OPEN_SECONDS = 33300; // 09:15:00 IST

    let cumPv = 0;
    let cumVol = 0;
    let sessionBars = [];
    let lastIstDate = null;
    let lastSecInDay = null;

    for (let i = 0; i < bars.length; i++) {
      const bar = bars[i];
      const time = bar.time;
      const istDate = toIstDateKey(time);
      const secInDay = toIstSecondsInDay(time);

      // Session reset detection:
      // 1. First bar
      // 2. Transition to a new IST calendar day
      // 3. Reaching or crossing market open 09:15:00 IST after pre-market
      const isNewDay = lastIstDate !== null && istDate !== lastIstDate;
      const isMarketOpenCrossing = lastSecInDay !== null &&
        lastSecInDay < MARKET_OPEN_SECONDS && secInDay >= MARKET_OPEN_SECONDS;

      if (isNewDay || isMarketOpenCrossing) {
        cumPv = 0;
        cumVol = 0;
        sessionBars = [];
      }

      lastIstDate = istDate;
      lastSecInDay = secInDay;

      // Typical Price = (High + Low + Close) / 3
      const close = getBarClose(bar);
      const high = bar.high !== undefined ? Number(bar.high) : close;
      const low = bar.low !== undefined ? Number(bar.low) : close;
      const tp = (high + low + close) / 3;
      const vol = Math.max(0, Number(bar.volume) || 0);

      cumPv += tp * vol;
      cumVol += vol;
      sessionBars.push({ tp, vol });

      let currentVwap = tp;
      let sigma = 0;

      if (cumVol > 0) {
        currentVwap = cumPv / cumVol;

        // Weighted standard deviation:
        // sigma = sqrt( sum(vol_j * (tp_j - vwap)^2) / sum(vol_j) )
        let weightedVarianceSum = 0;
        for (let j = 0; j < sessionBars.length; j++) {
          const diff = sessionBars[j].tp - currentVwap;
          weightedVarianceSum += sessionBars[j].vol * diff * diff;
        }
        const variance = weightedVarianceSum / cumVol;
        sigma = Math.sqrt(Math.max(0, variance));
      }

      const vwapVal = round2(currentVwap);
      const u1Val = round2(currentVwap + sigma);
      const l1Val = round2(currentVwap - sigma);
      const u2Val = round2(currentVwap + (2 * sigma));
      const l2Val = round2(currentVwap - (2 * sigma));

      vwap.push({ time, value: vwapVal });
      upper1.push({ time, value: u1Val });
      lower1.push({ time, value: l1Val });
      upper2.push({ time, value: u2Val });
      lower2.push({ time, value: l2Val });
    }

    return { vwap, upper1, lower1, upper2, lower2 };
  }

  // --- 3. Daily Classic & Camarilla Pivot Points ---

  /**
   * Compute Camarilla and Classic Pivot Points based on previous trading day's HLC.
   *
   * Camarilla:
   *   R4 = C + (H - L) * 1.1 / 2
   *   R3 = C + (H - L) * 1.1 / 4
   *   S3 = C - (H - L) * 1.1 / 4
   *   S4 = C - (H - L) * 1.1 / 2
   *
   * Classic:
   *   PP = (H + L + C) / 3
   *   R1 = 2 * PP - L
   *   S1 = 2 * PP - H
   *   R2 = PP + (H - L)
   *   S2 = PP - (H - L)
   *
   * @param {{high: number, low: number, close: number}} previousDayHlc
   * @returns {{r4: number, r3: number, s3: number, s4: number, pp: number, r1: number, s1: number, r2: number, s2: number} | null}
   */
  function computePivots(previousDayHlc) {
    if (!previousDayHlc || typeof previousDayHlc !== "object") {
      return null;
    }

    const high = Number(previousDayHlc.high);
    const low = Number(previousDayHlc.low);
    const close = Number(previousDayHlc.close);

    if (!Number.isFinite(high) || !Number.isFinite(low) || !Number.isFinite(close)) {
      return null;
    }

    const range = high - low;

    // Camarilla Levels
    const r4 = round2(close + (range * 1.1 / 2));
    const r3 = round2(close + (range * 1.1 / 4));
    const s3 = round2(close - (range * 1.1 / 4));
    const s4 = round2(close - (range * 1.1 / 2));

    // Classic Levels
    const pp = round2((high + low + close) / 3);
    const r1 = round2((2 * pp) - low);
    const s1 = round2((2 * pp) - high);
    const r2 = round2(pp + range);
    const s2 = round2(pp - range);

    return {
      r4,
      r3,
      s3,
      s4,
      pp,
      r1,
      s1,
      r2,
      s2,
    };
  }

  // --- 4. Relative Strength Index (RSI) ---

  /**
   * Compute Wilder's smoothed 14-period RSI bounded in [0, 100].
   * Requires at least `length + 1` bars to generate the first RSI value.
   *
   * @param {Array<Object>} bars - Array of { time, close }
   * @param {number} [length=14] - Period length
   * @returns {Array<{time: number, value: number}>}
   */
  function computeRsi(bars, length = 14) {
    const period = Math.floor(length) || 14;

    if (!Array.isArray(bars) || period <= 0 || bars.length <= period) {
      return [];
    }

    const result = [];

    // Helper: calculate RSI from average gain and loss
    function rsiFromAverages(avgGain, avgLoss) {
      if (avgLoss === 0) {
        return avgGain === 0 ? 50 : 100;
      }
      if (avgGain === 0) {
        return 0;
      }
      const rs = avgGain / avgLoss;
      const rsi = 100 - (100 / (1 + rs));
      return Math.max(0, Math.min(100, rsi));
    }

    // 1. Initial SMA seed over first `period` changes (indices 1 to period)
    let sumGain = 0;
    let sumLoss = 0;

    for (let i = 1; i <= period; i++) {
      const diff = getBarClose(bars[i]) - getBarClose(bars[i - 1]);
      if (diff > 0) {
        sumGain += diff;
      } else if (diff < 0) {
        sumLoss += -diff;
      }
    }

    let avgGain = sumGain / period;
    let avgLoss = sumLoss / period;

    result.push({
      time: bars[period].time,
      value: round2(rsiFromAverages(avgGain, avgLoss)),
    });

    // 2. Wilder's smoothing for subsequent bars
    for (let i = period + 1; i < bars.length; i++) {
      const diff = getBarClose(bars[i]) - getBarClose(bars[i - 1]);
      const gain = diff > 0 ? diff : 0;
      const loss = diff < 0 ? -diff : 0;

      avgGain = ((avgGain * (period - 1)) + gain) / period;
      avgLoss = ((avgLoss * (period - 1)) + loss) / period;

      result.push({
        time: bars[i].time,
        value: round2(rsiFromAverages(avgGain, avgLoss)),
      });
    }

    return result;
  }

  // --- 5. Moving Average Convergence Divergence (MACD) ---

  /**
   * Compute MACD line (fast EMA - slow EMA), Signal line (EMA of MACD), and Histogram.
   * Default: fast = 12, slow = 26, signal = 9
   *
   * @param {Array<Object>} bars - Array of { time, close }
   * @param {number} [fast=12]
   * @param {number} [slow=26]
   * @param {number} [signal=9]
   * @returns {{
   *   macd: Array<{time: number, value: number}>,
   *   signal: Array<{time: number, value: number}>,
   *   histogram: Array<{time: number, value: number}>
   * }}
   */
  function computeMacd(bars, fast = 12, slow = 26, signal = 9) {
    const emptyResult = { macd: [], signal: [], histogram: [] };

    const f = Math.floor(fast) || 12;
    const s = Math.floor(slow) || 26;
    const sig = Math.floor(signal) || 9;

    if (!Array.isArray(bars) || f <= 0 || s <= 0 || sig <= 0 || f >= s || bars.length < s) {
      return emptyResult;
    }

    // 1. Fast and Slow EMAs
    const fastEma = computeEma(bars, f);
    const slowEma = computeEma(bars, s);

    if (slowEma.length === 0) {
      return emptyResult;
    }

    // 2. MACD Line = Fast EMA - Slow EMA
    // Slow EMA starts at bar index s - 1
    // Fast EMA starts at bar index f - 1
    // Offset between slowEma[k] and fastEma: (s - 1) - (f - 1) = s - f
    const macdLine = [];
    const offset = s - f;

    for (let k = 0; k < slowEma.length; k++) {
      const slowPt = slowEma[k];
      const fastPt = fastEma[k + offset];
      const macdVal = round2(fastPt.value - slowPt.value);
      macdLine.push({
        time: slowPt.time,
        value: macdVal,
      });
    }

    // 3. Signal Line = EMA of MACD Line with window `signal`
    if (macdLine.length < sig) {
      return { macd: macdLine, signal: [], histogram: [] };
    }

    const signalLine = computeEma(macdLine, sig);

    // 4. Histogram = MACD Line - Signal Line
    // Signal line starts at index sig - 1 of macdLine
    const histogram = [];
    const sigOffset = sig - 1;

    for (let m = 0; m < signalLine.length; m++) {
      const sigPt = signalLine[m];
      const macdPt = macdLine[m + sigOffset];
      const histVal = round2(macdPt.value - sigPt.value);
      histogram.push({
        time: sigPt.time,
        value: histVal,
      });
    }

    return {
      macd: macdLine,
      signal: signalLine,
      histogram: histogram,
    };
  }

  // --- 6. Candlestick Pattern Recognition Engine ---

  /**
   * Identifies high-probability candlestick reversal and continuation patterns
   * on completed, closed candles.
   *
   * Supported patterns:
   * 1. [BE] Bullish Engulfing: Prior red, current green engulfing prior body.
   *    Position: 'belowBar', Color: '#10b981', Shape: 'arrowUp'
   * 2. [SE] Bearish Engulfing: Prior green, current red engulfing prior body.
   *    Position: 'aboveBar', Color: '#ef4444', Shape: 'arrowDown'
   * 3. [HM] Hammer: Lower shadow >= 2 * body, upper shadow <= 0.1 * range.
   *    Position: 'belowBar', Color: '#38bdf8', Shape: 'arrowUp'
   * 4. [SS] Shooting Star: Upper shadow >= 2 * body, lower shadow <= 0.1 * range.
   *    Position: 'aboveBar', Color: '#f43f5e', Shape: 'arrowDown'
   * 5. [MS] Morning Star / [ES] Evening Star: 3-bar reversal sequence.
   *    [MS] Position: 'belowBar', Color: '#34d399', Shape: 'arrowUp'
   *    [ES] Position: 'aboveBar', Color: '#fb7185', Shape: 'arrowDown'
   * 6. [DJ] Doji: |close - open| <= 0.05 * (high - low).
   *    Position: 'aboveBar', Color: '#eab308', Shape: 'circle'
   *
   * Collision Priority: Engulfing (1) > Star (2) > Hammer/Shooting Star (3) > Doji (4)
   *
   * @param {Array<Object>} bars - Array of { time, open, high, low, close, is_complete? }
   * @returns {Array<{time: number, position: 'aboveBar'|'belowBar', color: string, shape: string, text: string}>}
   */
  function detectCandlestickPatterns(bars) {
    if (!Array.isArray(bars) || bars.length === 0) {
      return [];
    }

    const EPSILON = 1e-9;
    const markers = [];

    function parseBar(b) {
      if (!b || typeof b !== "object") return null;
      const open = Number(b.open);
      const high = Number(b.high);
      const low = Number(b.low);
      const close = b.close !== undefined ? Number(b.close) : (b.value !== undefined ? Number(b.value) : open);
      const time = b.time;
      if (!Number.isFinite(open) || !Number.isFinite(high) || !Number.isFinite(low) || !Number.isFinite(close) || time === undefined) {
        return null;
      }
      return {
        time,
        open,
        high,
        low,
        close,
        is_complete: b.is_complete !== false,
      };
    }

    for (let i = 0; i < bars.length; i++) {
      const curr = parseBar(bars[i]);
      if (!curr) continue;

      // Only evaluate completed bars (skip forming candles if marked is_complete: false)
      if (curr.is_complete === false) {
        continue;
      }

      const open = curr.open;
      const high = curr.high;
      const low = curr.low;
      const close = curr.close;
      const time = curr.time;

      const range = high - low;
      const body = Math.abs(close - open);
      const upperShadow = high - Math.max(open, close);
      const lowerShadow = Math.min(open, close) - low;

      const candidates = [];

      // 1. Engulfing Patterns (Priority 1)
      if (i >= 1) {
        const prev = parseBar(bars[i - 1]);
        if (prev && prev.is_complete !== false) {
          // Bullish Engulfing: Prior bearish, current bullish, engulfing prior body
          if (
            prev.close < prev.open &&
            close > open &&
            open <= prev.close + EPSILON &&
            close >= prev.open - EPSILON
          ) {
            candidates.push({
              priority: 1,
              marker: {
                time,
                position: "belowBar",
                color: "#10b981",
                shape: "arrowUp",
                text: "[BE]",
              },
            });
          }

          // Bearish Engulfing: Prior bullish, current bearish, engulfing prior body
          if (
            prev.close > prev.open &&
            close < open &&
            open >= prev.close - EPSILON &&
            close <= prev.open + EPSILON
          ) {
            candidates.push({
              priority: 1,
              marker: {
                time,
                position: "aboveBar",
                color: "#ef4444",
                shape: "arrowDown",
                text: "[SE]",
              },
            });
          }
        }
      }

      // 2. Morning / Evening Star Patterns (Priority 2)
      if (i >= 2) {
        const b0 = parseBar(bars[i - 2]);
        const b1 = parseBar(bars[i - 1]);
        if (b0 && b1 && b0.is_complete !== false && b1.is_complete !== false) {
          const body0 = Math.abs(b0.close - b0.open);
          const body1 = Math.abs(b1.close - b1.open);

          // Morning Star: b0 bearish, b1 small body indecision star, curr strong bullish confirmation
          if (
            b0.close < b0.open &&
            body0 > 0 &&
            body1 <= (0.35 * body0) + EPSILON &&
            Math.max(b1.open, b1.close) <= ((b0.open + b0.close) / 2) + EPSILON &&
            close > open &&
            close >= ((b0.open + b0.close) / 2) - EPSILON
          ) {
            candidates.push({
              priority: 2,
              marker: {
                time,
                position: "belowBar",
                color: "#34d399",
                shape: "arrowUp",
                text: "[MS]",
              },
            });
          }

          // Evening Star: b0 bullish, b1 small body indecision star, curr strong bearish confirmation
          if (
            b0.close > b0.open &&
            body0 > 0 &&
            body1 <= (0.35 * body0) + EPSILON &&
            Math.min(b1.open, b1.close) >= ((b0.open + b0.close) / 2) - EPSILON &&
            close < open &&
            close <= ((b0.open + b0.close) / 2) + EPSILON
          ) {
            candidates.push({
              priority: 2,
              marker: {
                time,
                position: "aboveBar",
                color: "#fb7185",
                shape: "arrowDown",
                text: "[ES]",
              },
            });
          }
        }
      }

      // 3. Hammer & Shooting Star Patterns (Priority 3)
      if (range > 0) {
        // Hammer: lower shadow >= 2 * body, upper shadow <= 0.1 * range
        const isHammerLower = (open - low) >= (2 * body) - EPSILON && (close - low) >= (2 * body) - EPSILON;
        const isHammerUpper = upperShadow <= (0.1 * range) + EPSILON;
        if (isHammerLower && isHammerUpper) {
          candidates.push({
            priority: 3,
            marker: {
              time,
              position: "belowBar",
              color: "#38bdf8",
              shape: "arrowUp",
              text: "[HM]",
            },
          });
        }

        // Shooting Star: upper shadow >= 2 * body, lower shadow <= 0.1 * range
        const isStarUpper = upperShadow >= (2 * body) - EPSILON;
        const isStarLower = lowerShadow <= (0.1 * range) + EPSILON;
        if (isStarUpper && isStarLower) {
          candidates.push({
            priority: 3,
            marker: {
              time,
              position: "aboveBar",
              color: "#f43f5e",
              shape: "arrowDown",
              text: "[SS]",
            },
          });
        }
      }

      // 4. Doji Pattern (Priority 4)
      if (range > 0 && body <= (0.05 * range) + EPSILON) {
        candidates.push({
          priority: 4,
          marker: {
            time,
            position: "aboveBar",
            color: "#eab308",
            shape: "circle",
            text: "[DJ]",
          },
        });
      }

      // Priority resolution: Engulfing (1) > Star (2) > Hammer/Shooting Star (3) > Doji (4)
      if (candidates.length > 0) {
        candidates.sort((a, b) => a.priority - b.priority);
        markers.push(candidates[0].marker);
      }
    }

    return markers;
  }

  // --- Public API Export ---
  return {
    computeEma,
    computeVwap,
    computePivots,
    computeRsi,
    computeMacd,
    detectCandlestickPatterns,
  };
}));
