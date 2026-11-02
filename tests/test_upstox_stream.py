import pytest
from core.upstox.stream import UpstoxMarketEngine
from datetime import datetime

def test_candle_aggregation():
    engine = UpstoxMarketEngine(client=None)
    # Feed simulated ticks for RELIANCE
    t1 = datetime(2026, 11, 2, 9, 15, 30)
    engine.record_tick("RELIANCE", 1250.0, 1000, t1)
    engine.record_tick("RELIANCE", 1260.0, 2000, datetime(2026, 11, 2, 9, 16, 0))
    engine.record_tick("RELIANCE", 1245.0, 3000, datetime(2026, 11, 2, 9, 17, 0))
    engine.record_tick("RELIANCE", 1255.0, 4000, datetime(2026, 11, 2, 9, 19, 59))

    candles = engine.get_5m_candles("RELIANCE")
    assert len(candles) >= 1
    c = candles[-1]
    assert c["open"] == 1250.0
    assert c["high"] == 1260.0
    assert c["low"] == 1245.0
    assert c["close"] == 1255.0
    assert c["volume"] == 10000

def test_opening_range_lock():
    engine = UpstoxMarketEngine(client=None)
    # Ticks between 09:15 and 09:30
    engine.record_tick("RELIANCE", 1250.0, 100, datetime(2026, 11, 2, 9, 15, 10))
    engine.record_tick("RELIANCE", 1280.0, 100, datetime(2026, 11, 2, 9, 22, 0))
    engine.record_tick("RELIANCE", 1240.0, 100, datetime(2026, 11, 2, 9, 28, 0))

    orb = engine.get_opening_range("RELIANCE")
    assert orb["high"] == 1280.0
    assert orb["low"] == 1240.0
    assert round(orb["spread_pct"], 2) == round(((1280 - 1240) / 1240) * 100, 2)
