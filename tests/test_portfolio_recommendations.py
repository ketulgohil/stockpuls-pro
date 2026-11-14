"""Tests for the daily portfolio recommendation scan engine.

All storage and portfolio state is sandboxed to tmp paths — the real
``data/portfolio.json`` and ``data/trading.db`` are never touched.
"""

import json
from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from core import portfolio_recommendations as pr
from core import recommendation_store as rec_store
from core.recommendation_store import RecommendationStore


def _df(closes, dates=None):
    """Synthetic daily OHLC DataFrame."""
    n = len(closes)
    if dates is None:
        dates = pd.bdate_range(end="2026-11-13", periods=n)
    df = pd.DataFrame(
        {
            "Open": closes,
            "High": [c * 1.02 for c in closes],
            "Low": [c * 0.98 for c in closes],
            "Close": closes,
            "Volume": [1000] * n,
        },
        index=pd.DatetimeIndex(dates),
    )
    return df


@pytest.fixture
def store(tmp_path, monkeypatch):
    s = RecommendationStore(str(tmp_path / "rec.db"))
    monkeypatch.setattr(rec_store, "_store", s)
    yield s
    monkeypatch.setattr(rec_store, "_store", None)


@pytest.fixture
def portfolio_file(tmp_path, monkeypatch):
    pf = tmp_path / "portfolio.json"
    pf.write_text(json.dumps({
        "holdings": [
            {"symbol": "TESTA.NS", "quantity": 10, "buyPrice": 100.0},
            {"symbol": "TESTB.NS", "quantity": 5, "buyPrice": 200.0},
        ]
    }))
    monkeypatch.setattr(pr, "PORTFOLIO_FILE", str(pf))
    return str(pf)


# ---------------------------------------------------------------------------
# Aggregation rules
# ---------------------------------------------------------------------------
def test_aggregate_buy_wins():
    signals = [
        {"type": "BUY", "strength": "Strong"},
        {"type": "BUY", "strength": "Moderate"},
        {"type": "SELL", "strength": "Moderate"},
    ]
    label, buy, sell = pr.aggregate_signals(signals)
    assert label == "BUY"
    assert buy == 3 and sell == 1


def test_aggregate_sell_strong_beats_moderate_buys():
    signals = [
        {"type": "SELL", "strength": "Strong"},
        {"type": "BUY", "strength": "Moderate"},
    ]
    assert pr.aggregate_signals(signals)[0] == "SELL"


def test_aggregate_tie_is_hold():
    signals = [
        {"type": "BUY", "strength": "Strong"},
        {"type": "SELL", "strength": "Strong"},
    ]
    assert pr.aggregate_signals(signals)[0] == "HOLD"


def test_aggregate_no_signals_is_hold():
    assert pr.aggregate_signals([])[0] == "HOLD"


# ---------------------------------------------------------------------------
# Daily recommendation data states
# ---------------------------------------------------------------------------
def test_daily_no_data_when_provider_none(store, portfolio_file):
    with patch.object(pr, "get_stock_data", return_value=None):
        rec = pr._daily_recommendation("TESTA.NS")
    assert rec["recommendation"] == "NO_DATA"
    assert rec["note"]


def test_daily_not_enough_data(store, portfolio_file):
    short_df = _df([100.0] * 10)
    with patch.object(pr, "get_stock_data", return_value=short_df):
        rec = pr._daily_recommendation("TESTA.NS")
    assert rec["recommendation"] == "NOT_ENOUGH_DATA"
    assert "10" in rec["note"]


def test_daily_buy_with_reference(store, portfolio_file):
    closes = [100 + i * 0.1 for i in range(80)]
    df = _df(closes)
    signals = [{"type": "BUY", "strength": "Strong", "indicator": "RSI", "message": "m", "price": 107.9}]
    with patch.object(pr, "get_stock_data", return_value=df), \
         patch.object(pr, "generate_signals", return_value=signals):
        rec = pr._daily_recommendation("TESTA.NS")
    assert rec["recommendation"] == "BUY"
    assert rec["buy_score"] == 2 and rec["sell_score"] == 0
    assert rec["reference_price"] == pytest.approx(closes[-1])
    assert rec["data_as_of"] == "2026-11-13"
    assert rec["reference_date"] == "2026-11-13"


def test_daily_hold_when_no_signals(store, portfolio_file):
    df = _df([100.0] * 80)
    with patch.object(pr, "get_stock_data", return_value=df), \
         patch.object(pr, "generate_signals", return_value=[]):
        rec = pr._daily_recommendation("TESTA.NS")
    assert rec["recommendation"] == "HOLD"


# ---------------------------------------------------------------------------
# Intraday recommendation (separate horizon, live engine data)
# ---------------------------------------------------------------------------
def test_intraday_no_data_when_engine_down(store, portfolio_file):
    with patch("core.upstox.stream.upstox_engine") as engine:
        engine.get_5m_candles.return_value = None
        rec = pr._intraday_recommendation("TESTA.NS")
    assert rec["recommendation"] == "NO_DATA"


def test_intraday_not_enough_data(store, portfolio_file):
    with patch("core.upstox.stream.upstox_engine") as engine:
        engine.get_5m_candles.return_value = [{"close": 1}] * 5
        rec = pr._intraday_recommendation("TESTA.NS")
    assert rec["recommendation"] == "NOT_ENOUGH_DATA"


def test_intraday_qualified_buy(store, portfolio_file):
    result = {"qualified": True, "confluence_score": 100, "ltp": 105.5,
              "factors": {"ltp_above_vwap": True, "ema9_above_ema20": True}}
    with patch("core.upstox.stream.upstox_engine") as engine, \
         patch("core.intraday.signals.ConfluenceSignalEngine") as engine_cls:
        engine.get_5m_candles.return_value = [{"close": 1}] * 30
        engine_cls.return_value.evaluate.return_value = result
        rec = pr._intraday_recommendation("TESTA.NS")
    assert rec["recommendation"] == "BUY"
    assert rec["buy_score"] == 100
    assert rec["reference_price"] == 105.5


def test_intraday_unqualified_is_none(store, portfolio_file):
    result = {"qualified": False, "confluence_score": 40, "ltp": 100.0,
              "factors": {"ltp_above_vwap": False}}
    with patch("core.upstox.stream.upstox_engine") as engine, \
         patch("core.intraday.signals.ConfluenceSignalEngine") as engine_cls:
        engine.get_5m_candles.return_value = [{"close": 1}] * 30
        engine_cls.return_value.evaluate.return_value = result
        rec = pr._intraday_recommendation("TESTA.NS")
    assert rec["recommendation"] == "NONE"


# ---------------------------------------------------------------------------
# Full scan: persistence, immutability, duplicates, concurrent changes
# ---------------------------------------------------------------------------
import contextlib
from unittest.mock import MagicMock


def _engine_mock():
    """Context manager yielding a patched upstox engine (no 5m candles)."""
    engine = MagicMock()
    engine.get_5m_candles.return_value = []
    return patch("core.upstox.stream.upstox_engine", engine), engine


def test_scan_persists_immutable_records(store, portfolio_file):
    closes = [100 + i * 0.1 for i in range(80)]
    df = _df(closes)
    p_engine, engine = _engine_mock()
    with patch.object(pr, "get_stock_data", return_value=df), \
         patch.object(pr, "generate_signals", return_value=[]), p_engine:
        result = pr.scan_portfolio_recommendations(trigger="scheduled")
    assert result["status"] == "completed"
    assert result["scanned"] == 2
    assert store.count_recommendations() == 4  # 2 symbols x 2 horizons

    latest = store.latest_recommendations()
    assert latest["TESTA.NS"]["daily_swing"]["recommendation"] == "HOLD"
    assert latest["TESTA.NS"]["intraday"]["recommendation"] == "NOT_ENOUGH_DATA"
    rec = latest["TESTA.NS"]["daily_swing"]
    assert rec["holding_qty"] == 10
    assert rec["holding_avg_price"] == 100.0
    assert rec["strategy"] == "tech_signals_vote"

    # Second scheduled scan same day is a duplicate and must be skipped
    with patch.object(pr, "get_stock_data", return_value=df), \
         patch.object(pr, "generate_signals", return_value=[]), p_engine:
        again = pr.scan_portfolio_recommendations(trigger="scheduled")
    assert again["status"] == "already_scanned"
    assert store.count_recommendations() == 4


def test_manual_rescan_creates_new_records(store, portfolio_file):
    df = _df([100.0] * 80)
    p_engine, engine = _engine_mock()
    with patch.object(pr, "get_stock_data", return_value=df), \
         patch.object(pr, "generate_signals", return_value=[]), p_engine:
        pr.scan_portfolio_recommendations(trigger="manual")
        pr.scan_portfolio_recommendations(trigger="manual")
    assert store.count_recommendations() == 8   # immutable history, nothing overwritten
    assert len(store.history_for_symbol("TESTA.NS")) == 4
    scans = store.scan_counts_today(datetime.now(pr.IST).date().isoformat())
    assert scans == 2


def test_scan_survives_concurrent_portfolio_change(store, portfolio_file):
    """A holding removed mid-scan must not receive records; the reload after
    provider calls must not clobber the concurrent change."""
    p_engine, engine = _engine_mock()

    base = _df([100.0] * 80)
    calls = {"n": 0}

    def data_side_effect(symbol, period="6mo", interval="1d"):
        # While the provider calls run, the user removes TESTB and adds TESTC.
        if calls["n"] == 0:
            with open(pr.PORTFOLIO_FILE, "w") as f:
                json.dump({"holdings": [
                    {"symbol": "TESTA.NS", "quantity": 10, "buyPrice": 100.0},
                    {"symbol": "TESTC.NS", "quantity": 2, "buyPrice": 50.0},
                ]}, f)
        calls["n"] += 1
        return base

    with patch.object(pr, "get_stock_data", side_effect=data_side_effect), \
         patch.object(pr, "generate_signals", return_value=[]), p_engine:
        result = pr.scan_portfolio_recommendations(trigger="scheduled")

    assert result["status"] == "completed"
    latest = store.latest_recommendations()
    assert "TESTB.NS" not in latest           # removed mid-scan: no record
    assert "TESTA.NS" in latest
    assert "TESTC.NS" not in latest           # added mid-scan: next scan picks it up
    with open(pr.PORTFOLIO_FILE) as f:        # portfolio not clobbered
        assert [h["symbol"] for h in json.load(f)["holdings"]] == ["TESTA.NS", "TESTC.NS"]


def test_manual_rescan_allowed_on_fresh_process_then_cooldown(store, portfolio_file, monkeypatch):
    """Regression: a fresh process (no scan yet) must allow an immediate
    manual rescan; only after a completed scan does the 10-min cooldown apply."""
    monkeypatch.setattr(pr, "_last_rescan_monotonic", None)
    df = _df([100.0] * 80)
    p_engine, engine = _engine_mock()
    with patch.object(pr, "get_stock_data", return_value=df), \
         patch.object(pr, "generate_signals", return_value=[]), p_engine:
        result = pr.run_manual_rescan()
    assert result["status"] == "completed"
    again = pr.run_manual_rescan()
    assert again["status"] == "cooldown"


def test_scan_records_no_data_count(store, portfolio_file):
    with patch.object(pr, "get_stock_data", return_value=None), \
         patch("core.upstox.stream.upstox_engine") as engine:
        engine.get_5m_candles.return_value = None
        result = pr.scan_portfolio_recommendations(trigger="manual")
    assert result["noData"] == 2
    scan = store.latest_completed_scan()
    assert scan["no_data_count"] == 2
    assert scan["status"] == "completed"


def test_scan_marks_stale_provider_data(store, portfolio_file):
    """Provider has no candle for the scan day -> record is flagged stale.
    (On non-trading days the last session's candle is expected, not stale.)"""
    old_df = _df([100.0] * 80, dates=pd.bdate_range(end="2026-11-05", periods=80))
    with patch.object(pr, "get_stock_data", return_value=old_df), \
         patch.object(pr, "generate_signals", return_value=[]), \
         patch.object(pr, "is_trading_day", return_value=True), \
         patch("core.upstox.stream.upstox_engine") as engine:
        engine.get_5m_candles.return_value = []
        pr.scan_portfolio_recommendations(trigger="manual")
    rec = store.latest_recommendations()["TESTA.NS"]["daily_swing"]
    assert rec["stale_data"] is True


def test_no_stale_flag_on_non_trading_day(store, portfolio_file):
    old_df = _df([100.0] * 80, dates=pd.bdate_range(end="2026-11-13", periods=80))
    with patch.object(pr, "get_stock_data", return_value=old_df), \
         patch.object(pr, "generate_signals", return_value=[]), \
         patch.object(pr, "is_trading_day", return_value=False), \
         patch("core.upstox.stream.upstox_engine") as engine:
        engine.get_5m_candles.return_value = []
        pr.scan_portfolio_recommendations(trigger="manual")
    rec = store.latest_recommendations()["TESTA.NS"]["daily_swing"]
    assert rec["stale_data"] is False


# ---------------------------------------------------------------------------
# Scheduler time boundaries (IST)
# ---------------------------------------------------------------------------
def test_next_scan_same_day_before_slot():
    now = datetime(2026, 11, 12, 10, 0, tzinfo=pr.IST)   # Thursday
    secs = pr._seconds_until_next_scan(now)
    assert 0 < secs <= (15 * 60 + 45) * 60


def test_next_scan_friday_evening_goes_to_monday():
    now = datetime(2026, 11, 13, 16, 0, tzinfo=pr.IST)   # Friday after close
    secs = pr._seconds_until_next_scan(now)
    days = secs / 86400
    assert 2.9 < days < 3.1   # Fri 16:00 -> Mon 15:45 IST


def test_next_scan_skips_diwali_holiday():
    # Mon 2026-11-09 16:00 -> Tue Nov 10 is Diwali (holiday) -> Wed Nov 11 15:45
    now = datetime(2026, 11, 9, 16, 0, tzinfo=pr.IST)
    secs = pr._seconds_until_next_scan(now)
    from datetime import timedelta
    target = now + timedelta(seconds=secs)
    assert target.date().isoformat() == "2026-11-11"
    assert target.hour == 15 and target.minute == 45


def test_weekend_scan_skipped_by_loop_guard(store, portfolio_file):
    """On a non-trading day the scheduled trigger must not create a scan —
    the loop checks the calendar before calling (documented limitation:
    bundled holiday calendar covers 2026 only)."""
    from core.trader_core import is_trading_day
    assert is_trading_day(datetime(2026, 11, 14).date()) is False    # Saturday
    assert is_trading_day(datetime(2026, 11, 10).date()) is False    # Diwali
    assert is_trading_day(datetime(2026, 11, 13).date()) is True
