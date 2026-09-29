import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import pandas as pd
import numpy as np
from datetime import datetime
from core.sentinel.engine import SentinelEngine, DEFAULT_TRACKED
from core.sentinel.scheduler import ISTScheduler
from core.sentinel.types import SentinelAlert, DeskFinding, BullBearReview, MarketDigest

class TestSentinelEngine(unittest.TestCase):
    def setUp(self):
        # Create synthetic OHLCV dataframe with indicators for positive scan
        dates = pd.date_range(end=datetime.now(), periods=50, freq='D')
        self.df = pd.DataFrame({
            'Open': np.linspace(100, 120, 50),
            'High': np.linspace(102, 122, 50),
            'Low': np.linspace(99, 118, 50),
            'Close': np.linspace(101, 121, 50),
            'Volume': [100000] * 49 + [300000],  # Volume burst on latest bar (>2.5x)
            'EMA_20': np.linspace(98, 115, 50),
            'SMA_50': np.linspace(95, 110, 50),
            'RSI': [50] * 49 + [75],
            'ATR': [2.0] * 50
        }, index=dates)

    def test_engine_initialization(self):
        engine = SentinelEngine()
        self.assertFalse(engine.is_running)
        self.assertTrue(len(engine.tracked_symbols) > 0)
        self.assertEqual(engine.tracked_symbols, list(DEFAULT_TRACKED))

    def test_single_symbol_scan_no_anomaly(self):
        engine = SentinelEngine()
        with patch("core.sentinel.engine.get_stock_data", return_value=None):
            alert = engine.scan_symbol("RELIANCE.NS")
            self.assertIsNone(alert)

    def test_single_symbol_scan_with_anomaly(self):
        engine = SentinelEngine()
        with patch("core.sentinel.engine.get_stock_data", return_value=self.df), \
             patch("core.sentinel.engine.add_all_indicators", return_value=self.df), \
             patch("core.sentinel.engine.dispatcher.is_cooldown_active", return_value=False), \
             patch("core.sentinel.engine.dispatcher.record_alert_time") as mock_record:
            alert = engine.scan_symbol("RELIANCE.NS")
            self.assertIsNotNone(alert)
            self.assertIsInstance(alert, SentinelAlert)
            self.assertEqual(alert.symbol, "RELIANCE.NS")
            self.assertTrue(len(alert.findings) > 0)
            self.assertTrue(mock_record.called)

    def test_single_symbol_scan_cooldown_active(self):
        engine = SentinelEngine()
        with patch("core.sentinel.engine.get_stock_data", return_value=self.df), \
             patch("core.sentinel.engine.add_all_indicators", return_value=self.df), \
             patch("core.sentinel.engine.dispatcher.is_cooldown_active", return_value=True):
            alert = engine.scan_symbol("RELIANCE.NS")
            self.assertIsNone(alert)

    def test_engine_start_and_stop(self):
        engine = SentinelEngine()
        self.assertFalse(engine.is_running)

        created_coros = []
        def mock_create_task(coro):
            created_coros.append(coro)
            mock_task = MagicMock()
            return mock_task

        with patch("asyncio.create_task", side_effect=mock_create_task):
            engine.start()
            self.assertTrue(engine.is_running)
            self.assertEqual(len(created_coros), 1)

            engine.stop()
            self.assertFalse(engine.is_running)

        for coro in created_coros:
            coro.close()

    async def _async_test_run_routine(self):
        engine = SentinelEngine()
        with patch("core.sentinel.engine.dispatcher.save_digest") as mock_save, \
             patch("core.sentinel.engine.dispatcher.broadcast_ws", new_callable=AsyncMock) as mock_broadcast:
            await engine.run_routine("PRE_MARKET")
            mock_save.assert_called_once()
            mock_broadcast.assert_awaited_once()

    def test_run_routine(self):
        import asyncio
        asyncio.run(self._async_test_run_routine())

    def test_ist_scheduler(self):
        now = ISTScheduler.get_ist_now()
        self.assertIsNotNone(now)
        # Verify is_market_hours boolean return
        is_open = ISTScheduler.is_market_hours()
        self.assertIsInstance(is_open, bool)

if __name__ == "__main__":
    unittest.main()
