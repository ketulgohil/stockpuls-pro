import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app
from core.sentinel.dispatcher import dispatcher
from core.sentinel.engine import sentinel_engine
from core.auth import get_api_key

class TestSentinelAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_get_feed(self):
        response = self.client.get("/api/sentinel/feed")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("alerts", data)
        self.assertIsInstance(data["alerts"], list)

    def test_get_digests(self):
        response = self.client.get("/api/sentinel/digests")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("digests", data)
        self.assertIsInstance(data["digests"], list)

    def test_analyze_stock(self):
        response = self.client.post("/api/sentinel/analyze/RELIANCE.NS")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("symbol", data)
        self.assertEqual(data["symbol"], "RELIANCE.NS")
        self.assertIn("analysis", data)
        self.assertIn("bull_case", data["analysis"])
        self.assertIn("bear_case", data["analysis"])

    def test_trigger_routine_valid(self):
        response = self.client.post("/api/sentinel/routine/PRE_MARKET", headers={"X-API-Key": get_api_key()})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("message", data)
        self.assertIn("PRE_MARKET", data["message"])

    def test_trigger_routine_invalid(self):
        response = self.client.post("/api/sentinel/routine/UNKNOWN_ROUTINE", headers={"X-API-Key": get_api_key()})
        self.assertEqual(response.status_code, 400)

    def test_get_config(self):
        response = self.client.get("/api/sentinel/config")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("is_running", data)
        self.assertIn("tracked_symbols", data)
        self.assertIsInstance(data["tracked_symbols"], list)

    def test_websocket_sentinel(self):
        initial_sub_count = len(dispatcher.ws_subscribers)
        with self.client.websocket_connect("/ws/sentinel") as websocket:
            self.assertEqual(len(dispatcher.ws_subscribers), initial_sub_count + 1)
            websocket.send_text("ping")
        self.assertEqual(len(dispatcher.ws_subscribers), initial_sub_count)

if __name__ == "__main__":
    unittest.main()
