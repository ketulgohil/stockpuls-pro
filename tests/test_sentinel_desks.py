import unittest
from unittest.mock import patch
import pandas as pd
import numpy as np
from datetime import datetime

class TestSentinelDesks(unittest.TestCase):
    def setUp(self):
        # Create synthetic OHLCV dataframe with indicators
        dates = pd.date_range(end=datetime.now(), periods=50, freq='D')
        self.df = pd.DataFrame({
            'Open': np.linspace(100, 120, 50),
            'High': np.linspace(102, 122, 50),
            'Low': np.linspace(99, 118, 50),
            'Close': np.linspace(101, 121, 50),
            'Volume': [100000] * 49 + [300000],  # Volume burst on latest bar
            'EMA_20': np.linspace(98, 115, 50),
            'SMA_50': np.linspace(95, 110, 50),
            'RSI': [50] * 49 + [75],  # RSI overbought
            'ATR': [2.0] * 50
        }, index=dates)

    def test_activity_desk_volume_burst(self):
        from core.sentinel.desks.activity_desk import ActivityDesk
        findings = ActivityDesk.scan("RELIANCE.NS", self.df)
        self.assertTrue(any(f.metrics.get("volume_multiplier", 0) >= 2.5 for f in findings))
        self.assertTrue(all(f.desk == "ACTIVITY" for f in findings))

    def test_activity_desk_empty_or_insufficient_data(self):
        from core.sentinel.desks.activity_desk import ActivityDesk
        self.assertEqual(ActivityDesk.scan("RELIANCE.NS", None), [])
        short_df = self.df.iloc[:10]
        self.assertEqual(ActivityDesk.scan("RELIANCE.NS", short_df), [])

    def test_technical_desk_rsi_and_breakout(self):
        from core.sentinel.desks.technical_desk import TechnicalDesk
        findings = TechnicalDesk.scan("RELIANCE.NS", self.df)
        self.assertTrue(len(findings) > 0)
        self.assertTrue(any(f.desk == "TECHNICAL" for f in findings))

    def test_technical_desk_oversold_rsi(self):
        from core.sentinel.desks.technical_desk import TechnicalDesk
        oversold_df = self.df.copy()
        oversold_df.loc[oversold_df.index[-1], 'RSI'] = 20
        findings = TechnicalDesk.scan("TCS.NS", oversold_df)
        self.assertTrue(any("Oversold" in f.headline for f in findings))

    def test_news_desk_structure(self):
        from core.sentinel.desks.news_desk import NewsDesk
        findings = NewsDesk.scan_text("RELIANCE.NS", [
            {"title": "Reliance Q3 profit jumps 15% YoY", "publisher": "LiveMint", "published": "2026-09-29"}
        ])
        self.assertTrue(len(findings) > 0)
        self.assertEqual(findings[0].desk, "NEWS")

    def test_fundamentals_desk_scan(self):
        from core.sentinel.desks.fundamentals_desk import FundamentalsDesk
        with patch("core.sentinel.desks.fundamentals_desk.get_stock_info") as mock_info:
            mock_info.return_value = {
                "symbol": "RELIANCE.NS",
                "pe_ratio": 24.5,
                "eps": 110.2
            }
            findings = FundamentalsDesk.scan("RELIANCE.NS")
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].desk, "FUNDAMENTALS")
            self.assertEqual(findings[0].metrics["pe"], 24.5)

if __name__ == "__main__":
    unittest.main()
