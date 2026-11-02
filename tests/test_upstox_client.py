import os
import pytest
from core.upstox.client import UpstoxClient


def test_instrument_resolution():
    client = UpstoxClient(token="mock_token")
    assert client.resolve_instrument_key("RELIANCE") == "NSE_EQ|INE002A01018"
    assert client.resolve_instrument_key("TCS") == "NSE_EQ|INE467B01029"
    assert client.resolve_instrument_key("NIFTY 50") == "NSE_INDEX|Nifty 50"
    assert client.resolve_instrument_key("BANK NIFTY") == "NSE_INDEX|Nifty Bank"
    assert client.resolve_instrument_key("RELIANCE.NS") == "NSE_EQ|INE002A01018"
    assert client.resolve_instrument_key("NSE_EQ|INE002A01018") == "NSE_EQ|INE002A01018"


def test_client_token_loading(monkeypatch):
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "env_test_token_123")
    client = UpstoxClient()
    assert client.token == "env_test_token_123"
    assert client.is_authenticated is True

    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)
    client_empty = UpstoxClient(token=None)
    assert client_empty.token == ""
    assert client_empty.is_authenticated is False


@pytest.mark.asyncio
async def test_parse_quotes_and_depth(monkeypatch):
    client = UpstoxClient(token="mock_token")
    mock_payload = {
        "status": "success",
        "data": {
            "NSE_EQ:RELIANCE": {
                "last_price": 1300.0,
                "average_price": 1250.0,
                "volume": 5000000,
                "ohlc": {"open": 1240.0, "high": 1305.0, "low": 1235.0, "close": 1250.0},
                "depth": {
                    "buy": [{"quantity": 100, "price": 1299.5, "orders": 5}],
                    "sell": [{"quantity": 200, "price": 1300.0, "orders": 10}]
                }
            }
        }
    }

    class MockResponse:
        status_code = 200
        def json(self): return mock_payload

    async def mock_get(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    quotes = await client.get_quotes(["RELIANCE"])
    assert "RELIANCE" in quotes
    assert quotes["RELIANCE"]["last_price"] == 1300.0
    assert quotes["RELIANCE"]["vwap"] == 1250.0
    assert len(quotes["RELIANCE"]["depth"]["buy"]) == 1


@pytest.mark.asyncio
async def test_get_market_depth(monkeypatch):
    client = UpstoxClient(token="mock_token")
    mock_payload = {
        "status": "success",
        "data": {
            "NSE_EQ:RELIANCE": {
                "last_price": 1300.0,
                "average_price": 1250.0,
                "volume": 5000000,
                "depth": {
                    "buy": [{"quantity": 100, "price": 1299.5, "orders": 5}],
                    "sell": [{"quantity": 200, "price": 1300.0, "orders": 10}]
                }
            }
        }
    }

    class MockResponse:
        status_code = 200
        def json(self): return mock_payload

    async def mock_get(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    depth = await client.get_market_depth("RELIANCE")
    assert "buy" in depth
    assert "sell" in depth
    assert len(depth["buy"]) == 1
    assert depth["buy"][0]["price"] == 1299.5


@pytest.mark.asyncio
async def test_get_candles(monkeypatch):
    client = UpstoxClient(token="mock_token")
    mock_candle_payload = {
        "status": "success",
        "data": {
            "candles": [
                ["2026-11-02T09:15:00+05:30", 1250.0, 1260.0, 1245.0, 1255.0, 10000, 0],
                ["2026-11-02T09:20:00+05:30", 1255.0, 1265.0, 1250.0, 1262.0, 15000, 0]
            ]
        }
    }

    class MockResponse:
        status_code = 200
        def json(self): return mock_candle_payload

    async def mock_get(self_cli, url, *args, **kwargs):
        return MockResponse()

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    candles = await client.get_candles("RELIANCE", interval="5minute", to_date="2026-11-02")
    assert len(candles) == 2
    assert candles[0]["timestamp"] == "2026-11-02T09:15:00+05:30"
    assert candles[0]["open"] == 1250.0
    assert candles[0]["high"] == 1260.0
    assert candles[0]["low"] == 1245.0
    assert candles[0]["close"] == 1255.0
    assert candles[0]["volume"] == 10000
