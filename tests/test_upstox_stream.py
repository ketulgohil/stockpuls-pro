import pytest
import asyncio
from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock
from core.upstox.stream import UpstoxMarketEngine

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

def test_multiple_5m_buckets():
    engine = UpstoxMarketEngine(client=None)
    # Bucket 1: 09:15
    engine.record_tick("INFY", 100.0, 10, datetime(2026, 11, 2, 9, 15, 0))
    engine.record_tick("INFY", 105.0, 20, datetime(2026, 11, 2, 9, 19, 59))
    # Bucket 2: 09:20
    engine.record_tick("INFY", 104.0, 15, datetime(2026, 11, 2, 9, 20, 0))
    engine.record_tick("INFY", 110.0, 25, datetime(2026, 11, 2, 9, 24, 30))

    candles = engine.get_5m_candles("INFY")
    assert len(candles) == 2
    assert candles[0]["open"] == 100.0
    assert candles[0]["close"] == 105.0
    assert candles[0]["volume"] == 30
    assert candles[1]["open"] == 104.0
    assert candles[1]["close"] == 110.0
    assert candles[1]["volume"] == 40

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
    assert orb["locked"] is False

def test_opening_range_locked_after_0930():
    engine = UpstoxMarketEngine(client=None)
    # Ticks during ORB window
    engine.record_tick("TCS", 3000.0, 100, datetime(2026, 11, 2, 9, 15, 0))
    engine.record_tick("TCS", 3050.0, 200, datetime(2026, 11, 2, 9, 25, 0))

    # Tick after 09:30:00 (lock triggered, high must not expand to 3100)
    engine.record_tick("TCS", 3100.0, 50, datetime(2026, 11, 2, 9, 31, 0))

    orb = engine.get_opening_range("TCS")
    assert orb["locked"] is True
    assert orb["high"] == 3050.0
    assert orb["low"] == 3000.0

def test_latest_quotes_and_empty_defaults():
    engine = UpstoxMarketEngine(client=None)
    assert engine.get_latest_quotes() == {}
    assert engine.get_5m_candles("UNKNOWN") == []
    assert engine.get_opening_range("UNKNOWN") == {"high": 0.0, "low": 0.0, "locked": False, "spread_pct": 0.0}

    engine.record_tick("SBIN", 800.0, 500, datetime(2026, 11, 2, 10, 0, 0))
    quotes = engine.get_latest_quotes()
    assert "SBIN" in quotes
    assert quotes["SBIN"]["last_price"] == 800.0
    assert quotes["SBIN"]["volume"] == 500

@pytest.mark.asyncio
async def test_engine_lifecycle_and_poll():
    mock_client = MagicMock()
    mock_client.get_quotes = AsyncMock(return_value={
        "RELIANCE": {
            "symbol": "RELIANCE",
            "last_price": 1300.0,
            "vwap": 1290.0,
            "volume": 50000,
            "timestamp": "2026-11-02T09:16:00+05:30"
        }
    })

    engine = UpstoxMarketEngine(client=mock_client, symbols=["RELIANCE"])
    # Start engine
    engine.start()
    assert engine.is_running is True

    # Poll once explicitly or let loop cycle
    await engine.poll_once()
    quotes = engine.get_latest_quotes()
    assert "RELIANCE" in quotes
    assert quotes["RELIANCE"]["last_price"] == 1300.0

    # Stop engine
    engine.stop()
    assert engine.is_running is False

@pytest.mark.asyncio
async def test_engine_subscribers_and_broadcast():
    engine = UpstoxMarketEngine(client=None)
    received = []

    async def listener(data):
        received.append(data)

    engine.subscribe(listener)
    await engine.broadcast({"type": "TICK", "symbol": "RELIANCE", "price": 1250.0})
    assert len(received) == 1
    assert received[0]["symbol"] == "RELIANCE"

    engine.unsubscribe(listener)
    await engine.broadcast({"type": "TICK", "symbol": "RELIANCE", "price": 1260.0})
    assert len(received) == 1
