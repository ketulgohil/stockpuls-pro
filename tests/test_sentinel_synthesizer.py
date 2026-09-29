import unittest
from unittest.mock import MagicMock, patch
import json
from core.sentinel.types import DeskFinding, BullBearReview, MarketDigest
from core.sentinel.synthesizer import GeminiSynthesizer

class TestSentinelSynthesizer(unittest.TestCase):
    def setUp(self):
        self.findings = [
            DeskFinding(
                desk="ACTIVITY",
                symbol="RELIANCE.NS",
                headline="Volume Surge: 3.0x average",
                metrics={"volume_multiplier": 3.0},
                significance="HIGH",
                timestamp="2026-09-29 10:00:00"
            ),
            DeskFinding(
                desk="TECHNICAL",
                symbol="RELIANCE.NS",
                headline="Bullish 20 EMA Reclaim at ₹2950",
                metrics={"price": 2950.0},
                significance="MEDIUM",
                timestamp="2026-09-29 10:00:00"
            )
        ]

    def test_rule_based_fallback_synthesis(self):
        review = GeminiSynthesizer.fallback_synthesis("RELIANCE.NS", 2950.0, self.findings)
        self.assertIsNotNone(review.bull_case)
        self.assertIsNotNone(review.bear_case)
        self.assertEqual(review.invalidation_level, round(2950.0 * 0.98, 2))
        self.assertEqual(review.target_resistance, round(2950.0 * 1.04, 2))
        self.assertEqual(review.key_support, round(2950.0 * 0.97, 2))
        self.assertEqual(review.consensus_bias, "MODERATE_BULLISH")
        self.assertTrue(review.confidence_score >= 50)

    def test_synthesize_alert_fallback_when_no_client(self):
        with patch("core.gemini.client", None):
            review = GeminiSynthesizer.synthesize_alert("RELIANCE.NS", 2950.0, self.findings)
            self.assertIsInstance(review, BullBearReview)
            self.assertEqual(review.invalidation_level, round(2950.0 * 0.98, 2))

    def test_synthesize_alert_with_gemini_client(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "bull_case": "Strong momentum breakout confirmed by volume.",
            "bull_catalysts": ["Institutional inflows", "Moving average crossover"],
            "bear_case": "Approaching major psychological resistance at ₹3000.",
            "bear_risks": ["Overhead supply", "Broader Nifty consolidation"],
            "invalidation_level": 2910.0,
            "target_resistance": 3050.0,
            "key_support": 2930.0,
            "consensus_bias": "STRONG_BULLISH",
            "confidence_score": 85
        })
        mock_client.models.generate_content.return_value = mock_response

        with patch("core.gemini.client", mock_client):
            review = GeminiSynthesizer.synthesize_alert("RELIANCE.NS", 2950.0, self.findings)
            self.assertIsInstance(review, BullBearReview)
            self.assertEqual(review.consensus_bias, "STRONG_BULLISH")
            self.assertEqual(review.confidence_score, 85)
            self.assertEqual(review.invalidation_level, 2910.0)

    def test_synthesize_alert_gemini_exception_fallback(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("API quota exceeded")

        with patch("core.gemini.client", mock_client):
            review = GeminiSynthesizer.synthesize_alert("RELIANCE.NS", 2950.0, self.findings)
            self.assertIsInstance(review, BullBearReview)
            self.assertEqual(review.invalidation_level, round(2950.0 * 0.98, 2))

    def test_synthesize_market_digest(self):
        digest = GeminiSynthesizer.synthesize_market_digest(
            routine_type="PRE_MARKET",
            macro_cues=["Gift Nifty +45 pts", "Brent crude down 1.2%"],
            stocks_in_focus=["RELIANCE.NS", "INFY.NS"],
            sector_leaders=["NIFTY IT", "NIFTY METAL"]
        )
        self.assertIsInstance(digest, MarketDigest)
        self.assertEqual(digest.routine_type, "PRE_MARKET")
        self.assertEqual(digest.title, "Pre-Market Intelligence Briefing")
        self.assertEqual(len(digest.macro_cues), 2)
        self.assertEqual(len(digest.top_stocks_in_focus), 2)
        self.assertEqual(len(digest.sector_leaders), 2)

if __name__ == "__main__":
    unittest.main()
