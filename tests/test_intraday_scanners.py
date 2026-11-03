import pytest
from core.intraday.orb import ORBScanner
from core.intraday.signals import ConfluenceSignalEngine
from core.upstox.stream import UpstoxMarketEngine

def test_orb_breakout_detection():
    scanner = ORBScanner()
    orb_range = {"high": 1000.0, "low": 980.0, "locked": True}
    current_candle = {
        "open": 995.0,
        "high": 1010.0,
        "low": 992.0,
        "close": 1008.0,
        "volume": 50000
    }
    avg_volume = 30000
    vwap = 998.0

    breakout = scanner.evaluate_breakout("INFY", orb_range, current_candle, avg_volume, vwap)
    assert breakout is not None
    assert breakout["status"] == "BULLISH_ORB_BREAKOUT"
    assert breakout["entry_price"] == 1008.0
    assert breakout["stop_loss"] == 980.0
    assert breakout["target_1"] > 1008.0

def test_orb_no_breakout_below_high():
    scanner = ORBScanner()
    orb_range = {"high": 1000.0, "low": 980.0, "locked": True}
    current_candle = {
        "open": 990.0,
        "high": 999.0,
        "low": 985.0,
        "close": 995.0,
        "volume": 50000
    }
    breakout = scanner.evaluate_breakout("INFY", orb_range, current_candle, 30000, 990.0)
    assert breakout is None

def test_orb_unlocked_range():
    scanner = ORBScanner()
    orb_range = {"high": 1000.0, "low": 980.0, "locked": False}
    current_candle = {
        "open": 995.0,
        "high": 1010.0,
        "low": 992.0,
        "close": 1008.0,
        "volume": 50000
    }
    breakout = scanner.evaluate_breakout("INFY", orb_range, current_candle, 30000, 998.0)
    assert breakout is None

def test_confluence_buy_signal():
    engine = ConfluenceSignalEngine()
    signal = engine.evaluate_signal(
        symbol="TCS",
        ltp=3500.0,
        vwap=3480.0,
        ema9=3495.0,
        ema20=3485.0,
        rsi=62.0,
        current_volume=120000,
        avg_volume=70000
    )
    assert signal is not None
    assert signal["qualified"] is True
    assert signal["confluence_score"] >= 80
    assert signal["invalidation_sl"] == 3480.0

def test_confluence_signal_unqualified():
    engine = ConfluenceSignalEngine()
    signal = engine.evaluate_signal(
        symbol="TCS",
        ltp=3450.0,  # Below VWAP and EMA9
        vwap=3480.0,
        ema9=3495.0,
        ema20=3485.0,
        rsi=42.0,    # Weak RSI
        current_volume=50000,
        avg_volume=70000
    )
    assert signal is not None
    assert signal["qualified"] is False
    assert signal["confluence_score"] < 80

def test_scanner_engine_integration():
    engine = UpstoxMarketEngine(symbols=["RELIANCE"])
    # Seed opening range and 5m candles
    engine._opening_ranges["RELIANCE"] = {"high": 2500.0, "low": 2450.0, "locked": True}
    engine._candles_5m["RELIANCE"] = [
        {"timestamp": "2026-11-03T09:15:00+05:30", "open": 2460, "high": 2500, "low": 2450, "close": 2480, "volume": 10000},
        {"timestamp": "2026-11-03T09:20:00+05:30", "open": 2480, "high": 2490, "low": 2470, "close": 2485, "volume": 12000},
        {"timestamp": "2026-11-03T09:30:00+05:30", "open": 2485, "high": 2530, "low": 2485, "close": 2520, "volume": 40000}
    ]
    engine._quotes["RELIANCE"] = {"symbol": "RELIANCE", "last_price": 2520.0, "vwap": 2490.0}

    orb_scanner = ORBScanner()
    res = orb_scanner.scan("RELIANCE", engine=engine)
    assert res is not None
    assert res["status"] == "BULLISH_ORB_BREAKOUT"
    assert res["entry_price"] == 2520.0

    signal_engine = ConfluenceSignalEngine()
    # Add more candles so len >= 20 for evaluate()
    for i in range(25):
        engine._candles_5m["RELIANCE"].append({
            "timestamp": f"2026-11-03T09:{35+i*5:02d}:00+05:30",
            "open": 2520, "high": 2530, "low": 2510, "close": 2525, "volume": 50000
        })
    sig = signal_engine.evaluate("RELIANCE", engine=engine)
    assert sig is not None
