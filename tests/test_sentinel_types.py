import unittest
from datetime import datetime

class TestSentinelTypes(unittest.TestCase):
    def test_desk_finding_creation(self):
        from core.sentinel.types import DeskFinding
        finding = DeskFinding(
            desk="ACTIVITY",
            symbol="RELIANCE.NS",
            headline="Volume burst 3.2x normal",
            metrics={"volume_ratio": 3.2, "current_volume": 1500000},
            significance="HIGH",
            timestamp="2026-09-29 10:30:00"
        )
        self.assertEqual(finding.desk, "ACTIVITY")
        self.assertEqual(finding.significance, "HIGH")

    def test_bull_bear_review_creation(self):
        from core.sentinel.types import BullBearReview
        review = BullBearReview(
            bull_case="Strong breakout above 20 EMA with rising volume",
            bull_catalysts=["Q3 margin expansion", "Institutional block deals"],
            bear_case="RSI near overbought (68) and overhead resistance at 3000",
            bear_risks=["Broader market weakness", "Crude oil volatility"],
            invalidation_level=2880.0,
            target_resistance=3050.0,
            key_support=2900.0,
            consensus_bias="MODERATE_BULLISH",
            confidence_score=78
        )
        self.assertEqual(review.consensus_bias, "MODERATE_BULLISH")
        self.assertEqual(review.confidence_score, 78)

    def test_sentinel_alert_creation(self):
        from core.sentinel.types import DeskFinding, BullBearReview, SentinelAlert
        finding = DeskFinding(
            desk="TECHNICAL",
            symbol="TCS.NS",
            headline="RSI Oversold Rebound",
            metrics={"rsi": 28.5},
            significance="MEDIUM",
            timestamp="2026-09-29 11:00:00"
        )
        review = BullBearReview(
            bull_case="Mean reversion setup",
            bull_catalysts=["Oversold bounce"],
            bear_case="Downtrend continuation",
            bear_risks=["IT sector weakness"],
            invalidation_level=3800.0,
            target_resistance=4000.0,
            key_support=3850.0,
            consensus_bias="NEUTRAL",
            confidence_score=60
        )
        alert = SentinelAlert(
            id="alert_1",
            symbol="TCS.NS",
            title="TCS: RSI Oversold Reversal Setup",
            summary="Technical rebound with stabilizing volume",
            severity="HIGH",
            findings=[finding],
            analysis=review,
            created_at="2026-09-29 11:00:00",
            data_as_of="2026-09-29 11:00:00"
        )
        self.assertEqual(len(alert.findings), 1)
        self.assertEqual(alert.severity, "HIGH")

    def test_market_digest_and_config_creation(self):
        from core.sentinel.types import MarketDigest, SentinelConfig
        digest = MarketDigest(
            id="digest_1",
            routine_type="PRE_MARKET",
            title="Morning Brief",
            summary="Gift Nifty indicates positive opening",
            macro_cues=["US markets gained", "Crude oil fell"],
            top_stocks_in_focus=["RELIANCE.NS", "HDFCBANK.NS"],
            sector_leaders=["NIFTY IT"],
            sector_laggards=["NIFTY AUTO"],
            timestamp="2026-09-29 08:30:00"
        )
        self.assertEqual(digest.routine_type, "PRE_MARKET")
        self.assertEqual(len(digest.macro_cues), 2)

        config = SentinelConfig(
            enabled=True,
            scan_interval_seconds=30,
            volume_threshold_multiplier=2.5,
            tracked_symbols=["TCS.NS"],
            telegram_alerts_enabled=True,
            audio_chime_enabled=True
        )
        self.assertTrue(config.enabled)
        self.assertEqual(config.scan_interval_seconds, 30)

if __name__ == "__main__":
    unittest.main()
