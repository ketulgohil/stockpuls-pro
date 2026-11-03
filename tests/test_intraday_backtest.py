import pytest
from core.intraday.backtest import IntradayBacktester

def test_backtest_orb_run():
    backtester = IntradayBacktester()
    # Mock a 1-day series of 5m candles (9:15 to 15:30)
    mock_candles = [
        # 09:15, 09:20, 09:25 (Opening Range: High 1000, Low 990)
        {"timestamp": "2026-11-02T09:15:00+05:30", "open": 995, "high": 1000, "low": 992, "close": 998, "volume": 10000},
        {"timestamp": "2026-11-02T09:20:00+05:30", "open": 998, "high": 999, "low": 990, "close": 993, "volume": 12000},
        {"timestamp": "2026-11-02T09:25:00+05:30", "open": 993, "high": 997, "low": 991, "close": 995, "volume": 11000},
        # 09:30 Breakout candle (Close 1005 > 1000, High 1008)
        {"timestamp": "2026-11-02T09:30:00+05:30", "open": 995, "high": 1008, "low": 995, "close": 1005, "volume": 25000},
        # 09:35 Target hit (High 1025 >= Target 1020)
        {"timestamp": "2026-11-02T09:35:00+05:30", "open": 1005, "high": 1025, "low": 1004, "close": 1022, "volume": 30000},
    ]

    result = backtester.run_orb_backtest("TEST_STOCK", mock_candles)
    assert result["total_trades"] == 1
    assert result["winning_trades"] == 1
    assert result["win_rate"] == 100.0
    assert result["total_profit"] > 0

def test_backtest_orb_stop_loss():
    backtester = IntradayBacktester()
    mock_candles = [
        {"timestamp": "2026-11-02T09:15:00+05:30", "open": 995, "high": 1000, "low": 990, "close": 998, "volume": 10000},
        {"timestamp": "2026-11-02T09:20:00+05:30", "open": 998, "high": 999, "low": 990, "close": 993, "volume": 12000},
        {"timestamp": "2026-11-02T09:25:00+05:30", "open": 993, "high": 997, "low": 990, "close": 995, "volume": 11000},
        # Breakout at 09:30
        {"timestamp": "2026-11-02T09:30:00+05:30", "open": 995, "high": 1008, "low": 995, "close": 1005, "volume": 25000},
        # Stop loss hit at 09:35 (Low <= stop_loss 990)
        {"timestamp": "2026-11-02T09:35:00+05:30", "open": 1005, "high": 1006, "low": 985, "close": 988, "volume": 30000},
    ]
    result = backtester.run_orb_backtest("TEST_STOCK", mock_candles)
    assert result["total_trades"] == 1
    assert result["winning_trades"] == 0
    assert result["losing_trades"] == 1
    assert result["win_rate"] == 0.0
    assert result["total_profit"] < 0
