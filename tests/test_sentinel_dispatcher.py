import unittest
import os
import json
from unittest.mock import patch, MagicMock, AsyncMock
from core.sentinel.types import SentinelAlert, BullBearReview, DeskFinding, MarketDigest
from core.sentinel.dispatcher import SentinelDispatcher

class TestSentinelDispatcher(unittest.TestCase):
    def setUp(self):
        self.test_alerts_file = "data/test_alerts.json"
        self.test_digests_file = "data/test_digests.json"
        self.dispatcher = SentinelDispatcher(
            storage_file=self.test_alerts_file,
            digest_file=self.test_digests_file
        )

    def tearDown(self):
        if os.path.exists(self.test_alerts_file):
            os.remove(self.test_alerts_file)
        if os.path.exists(self.test_digests_file):
            os.remove(self.test_digests_file)

    def test_deduplication_cooldown(self):
        symbol = "SBIN.NS"
        self.assertFalse(self.dispatcher.is_cooldown_active(symbol, "VOLUME_SPIKE"))
        self.dispatcher.record_alert_time(symbol, "VOLUME_SPIKE")
        self.assertTrue(self.dispatcher.is_cooldown_active(symbol, "VOLUME_SPIKE"))

    def test_save_and_retrieve_alerts(self):
        alert = SentinelAlert(
            id="test_1",
            symbol="SBIN.NS",
            title="SBIN Volume Breakout",
            summary="Strong surge with institutional footprint",
            severity="HIGH",
            findings=[],
            analysis=BullBearReview(
                bull_case="Bullish",
                bull_catalysts=[],
                bear_case="Bearish",
                bear_risks=[],
                consensus_bias="MODERATE_BULLISH",
                confidence_score=75
            ),
            created_at="2026-09-29 10:00:00",
            data_as_of="2026-09-29 10:00:00"
        )
        self.dispatcher.save_alert(alert)
        alerts = self.dispatcher.get_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["symbol"], "SBIN.NS")

        active_alerts = self.dispatcher.get_active_alerts()
        self.assertEqual(len(active_alerts), 1)

    def test_save_and_retrieve_digests(self):
        digest = MarketDigest(
            id="digest_1",
            routine_type="PRE_MARKET",
            title="Morning Market Setup",
            summary="Nifty bullish momentum expected",
            macro_cues=["GIFT Nifty up 50 pts"],
            top_stocks_in_focus=["RELIANCE.NS", "HDFCBANK.NS"],
            sector_leaders=["NIFTY IT"],
            sector_laggards=["NIFTY AUTO"],
            timestamp="2026-09-29 08:30:00"
        )
        self.dispatcher.save_digest(digest)
        digests = self.dispatcher.get_digests()
        self.assertEqual(len(digests), 1)
        self.assertEqual(digests[0]["routine_type"], "PRE_MARKET")

    async def _async_test_ws_broadcast(self):
        ws_mock = MagicMock()
        ws_mock.send_json = AsyncMock()
        self.dispatcher.register_ws(ws_mock)
        self.assertIn(ws_mock, self.dispatcher.ws_subscribers)

        await self.dispatcher.broadcast_ws({"type": "TEST"})
        ws_mock.send_json.assert_awaited_once_with({"type": "TEST"})

        # Test dead connection removal
        failing_ws = MagicMock()
        failing_ws.send_json = AsyncMock(side_effect=Exception("Connection closed"))
        self.dispatcher.register_ws(failing_ws)
        await self.dispatcher.broadcast_ws({"type": "TEST2"})
        self.assertNotIn(failing_ws, self.dispatcher.ws_subscribers)

        self.dispatcher.unregister_ws(ws_mock)
        self.assertNotIn(ws_mock, self.dispatcher.ws_subscribers)

    def test_ws_broadcast(self):
        import asyncio
        asyncio.run(self._async_test_ws_broadcast())

    @patch("urllib.request.urlopen")
    @patch("os.path.exists")
    @patch("builtins.open", create=True)
    def test_send_telegram(self, mock_open, mock_exists, mock_urlopen):
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
            "bot_token": "fake_token_123",
            "chat_id": "12345678"
        })

        alert = SentinelAlert(
            id="test_tg",
            symbol="TCS.NS",
            title="TCS Range Breakout",
            summary="High volume push",
            severity="CRITICAL",
            findings=[],
            analysis=BullBearReview(
                bull_case="Expanding margins",
                bull_catalysts=["Deal wins"],
                bear_case="High valuation",
                bear_risks=["Attrition"],
                consensus_bias="STRONG_BULLISH",
                confidence_score=85,
                target_resistance=4200.0,
                invalidation_level=3900.0
            ),
            created_at="2026-09-29 10:00:00",
            data_as_of="2026-09-29 10:00:00"
        )
        self.dispatcher.send_telegram(alert)
        self.assertTrue(mock_urlopen.called)

    async def _async_test_dispatch_alert(self):
        alert = SentinelAlert(
            id="test_dispatch",
            symbol="INFY.NS",
            title="INFY Alert",
            summary="INFY summary",
            severity="HIGH",
            findings=[],
            analysis=BullBearReview(
                bull_case="Bull",
                bear_case="Bear",
                consensus_bias="NEUTRAL",
                confidence_score=50
            ),
            created_at="2026-09-29 10:00:00",
            data_as_of="2026-09-29 10:00:00"
        )
        with patch.object(self.dispatcher, "send_telegram") as mock_tg:
            await self.dispatcher.dispatch_alert(alert)
            mock_tg.assert_called_once_with(alert)
            alerts = self.dispatcher.get_alerts()
            self.assertEqual(len(alerts), 1)
            self.assertEqual(alerts[0]["symbol"], "INFY.NS")

    def test_dispatch_alert(self):
        import asyncio
        asyncio.run(self._async_test_dispatch_alert())

if __name__ == "__main__":
    unittest.main()
