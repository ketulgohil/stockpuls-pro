"""Tests for recommendation outcome evaluation: horizons, look-ahead
prevention, cost model, HOLD band, corporate-action flagging, pending states
and performance aggregation. All storage is sandboxed to tmp paths."""

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from core import recommendation_store as rec_store
from core.recommendation_evaluator import (
    evaluate_row,
    horizon_end_dates,
    next_trading_dates,
    run_pending_evaluations,
    summarize_performance,
)
from core.recommendation_store import RecommendationStore


@pytest.fixture
def store(tmp_path, monkeypatch):
    s = RecommendationStore(str(tmp_path / "rec.db"))
    monkeypatch.setattr(rec_store, "_store", s)
    yield s
    monkeypatch.setattr(rec_store, "_store", None)


def _candles(mapping):
    """{date_str: close} -> full candle dict."""
    return {d: {"open": c * 0.995, "high": c * 1.01, "low": c * 0.99, "close": c}
            for d, c in mapping.items()}


# ---------------------------------------------------------------------------
# Calendar arithmetic
# ---------------------------------------------------------------------------
def test_next_trading_dates_skip_weekend_and_holiday():
    # After Fri 2026-11-06: Sun 8 (Diwali Muhurat special session — the
    # provider returns a daily candle for it), Mon 9, Wed 11 (Tue 10 = holiday)
    dates = next_trading_dates(date(2026, 11, 6), 3)
    assert [d.isoformat() for d in dates] == ["2026-11-08", "2026-11-09", "2026-11-11"]


def test_horizon_end_dates_complete():
    ends = horizon_end_dates(date(2026, 11, 2))  # Monday
    assert set(ends) == {"t1", "t5", "t20", "intraday_next"}
    assert ends["t1"] == "2026-11-03"
    assert ends["intraday_next"] == "2026-11-03"
    # t5 = 5th trading session after Nov 2: 3,4,5,6,8(muhurat)
    assert ends["t5"] == "2026-11-08"
    # t20 crosses Diwali (Nov 10) and Gurunanak Jayanti (Nov 24) weekends etc.
    assert ends["t20"] == "2026-12-01"


# ---------------------------------------------------------------------------
# evaluate_row — direction, cost model, HOLD band
# ---------------------------------------------------------------------------
BASE = {"horizon_key": "t1", "recommendation": "BUY",
        "reference_date": "2026-11-02", "trade_date": "2026-11-02",
        "end_date": "2026-11-03", "reference_price": 100.0}


def test_buy_worked_after_cost():
    candles = _candles({"2026-11-02": 100.0, "2026-11-03": 105.0})
    fields = evaluate_row(dict(BASE), candles, candles, "2026-11-03")
    assert fields["status"] == "WORKED"
    assert fields["gross_return_pct"] == pytest.approx(5.0)
    assert fields["net_return_pct"] == pytest.approx(5.0 - 0.30, abs=0.01)
    assert fields["mfe_pct"] >= fields["gross_return_pct"]


def test_buy_fails_when_gross_below_cost():
    candles = _candles({"2026-11-02": 100.0, "2026-11-03": 100.1})
    fields = evaluate_row(dict(BASE), candles, candles, "2026-11-03")
    assert fields["status"] == "NOT_WORKED"   # +0.1% gross < 0.30% cost


def test_sell_worked_when_price_falls():
    row = dict(BASE, recommendation="SELL")
    candles = _candles({"2026-11-02": 100.0, "2026-11-03": 95.0})
    fields = evaluate_row(row, candles, candles, "2026-11-03")
    assert fields["status"] == "WORKED"
    assert fields["net_return_pct"] == pytest.approx(5.0 - 0.30, abs=0.01)


def test_sell_fails_when_price_rises():
    row = dict(BASE, recommendation="SELL")
    candles = _candles({"2026-11-02": 100.0, "2026-11-03": 101.0})
    fields = evaluate_row(row, candles, candles, "2026-11-03")
    assert fields["status"] == "NOT_WORKED"


def test_hold_within_band_works():
    row = dict(BASE, recommendation="HOLD")
    candles = _candles({"2026-11-02": 100.0, "2026-11-03": 101.0})
    fields = evaluate_row(row, candles, candles, "2026-11-03")
    assert fields["status"] == "WORKED"
    assert "neutral band" in fields["note"]


def test_hold_outside_band_fails():
    row = dict(BASE, recommendation="HOLD")
    candles = _candles({"2026-11-02": 100.0, "2026-11-03": 104.0})
    fields = evaluate_row(row, candles, candles, "2026-11-03")
    assert fields["status"] == "NOT_WORKED"


def test_no_data_records_not_evaluated():
    row = dict(BASE, recommendation="NO_DATA")
    candles = _candles({"2026-11-02": 100.0, "2026-11-03": 101.0})
    fields = evaluate_row(row, candles, candles, "2026-11-03")
    assert fields["status"] == "NEUTRAL"


# ---------------------------------------------------------------------------
# Look-ahead prevention
# ---------------------------------------------------------------------------
def test_window_excludes_data_before_reference_date():
    """A pump before the recommendation must not influence the outcome."""
    candles = _candles({
        "2026-10-30": 150.0,   # pre-recommendation spike — must be ignored
        "2026-11-01": 145.0,
        "2026-11-02": 100.0,   # reference day (excluded from window)
        "2026-11-03": 101.0,
    })
    fields = evaluate_row(dict(BASE), candles, candles, "2026-11-03")
    assert fields["gross_return_pct"] == pytest.approx(1.0, abs=0.05)
    assert fields["days_used"] == 1


# ---------------------------------------------------------------------------
# Corporate action flag
# ---------------------------------------------------------------------------
def test_suspected_corporate_action_flagged():
    candles = _candles({
        "2026-11-02": 100.0,
        "2026-11-03": 130.0,   # +30% single day -> suspect split/bonus
        "2026-11-04": 131.0,
    })
    row = dict(BASE, end_date="2026-11-04")
    fields = evaluate_row(row, candles, candles, "2026-11-04")
    assert fields["status"] == "SUSPECTED_CORP_ACTION"
    assert "corporate action" in fields["note"]


# ---------------------------------------------------------------------------
# Pending / unavailable data
# ---------------------------------------------------------------------------
def test_pending_when_horizon_end_candle_missing():
    # Use a horizon near the real current date so the data grace period
    # has not elapsed (e.g. Friday ref -> Monday end, candle not yet present).
    candles = _candles({"2026-11-13": 100.0})
    row = dict(BASE, reference_date="2026-11-13", end_date="2026-11-16")
    fields = evaluate_row(row, candles, candles, "2026-11-16")
    assert fields["status"] == "PENDING"


def test_data_unavailable_when_end_never_arrives():
    candles = _candles({"2026-11-02": 100.0})
    row = dict(BASE, end_date="2026-10-01")     # long past, grace exhausted
    fields = evaluate_row(row, candles, candles, "2026-11-14")
    assert fields["status"] == "DATA_UNAVAILABLE"


def test_data_unavailable_when_gap_skips_end_date():
    candles = _candles({"2026-11-02": 100.0, "2026-11-04": 101.0})  # no Nov 3
    fields = evaluate_row(dict(BASE), candles, candles, "2026-11-04")
    assert fields["status"] == "DATA_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Intraday horizon
# ---------------------------------------------------------------------------
def test_intraday_buy_next_session():
    row = dict(BASE, horizon_key="intraday_next", recommendation="BUY")
    candles = _candles({"2026-11-02": 100.0, "2026-11-03": 106.0})
    # open = 106 * 0.995 = 105.47 -> close 106.00: ~+0.50% session return,
    # above the 0.30% estimated cost -> WORKED
    fields = evaluate_row(row, candles, candles, "2026-11-03")
    assert fields["status"] == "WORKED"
    assert fields["gross_return_pct"] == pytest.approx(0.503, abs=0.05)


def test_intraday_none_neutral():
    row = dict(BASE, horizon_key="intraday_next", recommendation="NONE")
    candles = _candles({"2026-11-02": 100.0, "2026-11-03": 101.0})
    fields = evaluate_row(row, candles, candles, "2026-11-03")
    assert fields["status"] == "NEUTRAL"


# ---------------------------------------------------------------------------
# Full pending-evaluation run against the store
# ---------------------------------------------------------------------------
def _seed_rec(store, symbol="TESTA.NS", rec_type="BUY", ref="2026-11-02",
              ref_price=100.0, horizon="daily_swing"):
    rec_id = store.insert_recommendation({
        "trade_date": "2026-11-02", "symbol": symbol, "horizon": horizon,
        "recommendation": rec_type, "reference_price": ref_price,
        "reference_date": ref, "buy_score": 2.0, "sell_score": 0.0,
        "signals": [], "strategy": "tech_signals_vote", "strategy_version": "1.0",
    })
    ends = horizon_end_dates(ref)
    keys = {k: ends[k] for k in ("t1", "t5", "t20") if ends.get(k)}
    store.insert_pending_evaluations(rec_id, keys)
    return rec_id, ends


def _patch_prices(mapping, bench=None):
    def fake(symbol, period="6mo", interval="1d"):
        data = mapping if symbol != "^NSEI" else (bench or mapping)
        if data is None:
            return None
        dates = sorted(data)
        return pd.DataFrame(
            {"Open": [data[d] * 0.995 for d in dates],
             "High": [data[d] * 1.01 for d in dates],
             "Low": [data[d] * 0.99 for d in dates],
             "Close": [data[d] for d in dates],
             "Volume": [1000] * len(dates)},
            index=pd.DatetimeIndex(dates),
        )
    return patch("core.data_fetcher.get_stock_data", side_effect=fake)


def test_run_pending_evaluates_t1_only(store):
    rec_id, ends = _seed_rec(store)
    prices = {d: 100.0 + 0.5 * i for i, d in enumerate(
        ["2026-11-02", "2026-11-03", "2026-11-04"])}
    with _patch_prices(prices):
        evaluated = run_pending_evaluations(store, "2026-11-03")
    assert evaluated == 1
    rows = store.evaluation_rows()
    by_key = {r["horizon_key"]: r for r in rows}
    assert by_key["t1"]["eval_status"] == "WORKED"
    assert by_key["t5"]["eval_status"] == "PENDING"   # horizon not complete
    assert by_key["t20"]["eval_status"] == "PENDING"
    assert by_key["t1"]["excess_return_pct"] is not None  # benchmark recorded


def test_run_pending_respects_look_ahead(store):
    """Prices before the reference date must not leak into the outcome."""
    rec_id, ends = _seed_rec(store, rec_type="HOLD")
    prices = {
        "2026-10-30": 200.0,          # wild pre-recommendation data
        "2026-11-02": 100.0,
        "2026-11-03": 100.5,          # +0.5% -> within HOLD band
    }
    with _patch_prices(prices):
        run_pending_evaluations(store, "2026-11-03")
    row = [r for r in store.evaluation_rows() if r["horizon_key"] == "t1"][0]
    assert row["eval_status"] == "WORKED"
    assert row["gross_return_pct"] == pytest.approx(0.5, abs=0.1)


def test_pending_stays_pending_when_provider_lags(store):
    """A horizon whose end candle has not arrived yet (and is still inside the
    data grace window) must remain PENDING, not become a failure."""
    _seed_rec(store, ref="2026-11-13")          # Friday -> t1 ends Monday Nov 16
    with _patch_prices({"2026-11-13": 100.0}):
        evaluated = run_pending_evaluations(store, "2026-11-14")
    assert evaluated == 0
    assert store.all_pending_count() == 3


# ---------------------------------------------------------------------------
# Performance aggregation
# ---------------------------------------------------------------------------
def test_summarize_rates_carry_denominators():
    rows = []
    for i, (rec, status, net) in enumerate([
        ("BUY", "WORKED", 2.0), ("BUY", "NOT_WORKED", -1.0),
        ("BUY", "WORKED", 3.0), ("SELL", "NOT_WORKED", -2.0),
        ("HOLD", "WORKED", 0.5), ("HOLD", "PENDING", None),
    ]):
        rows.append({
            "recommendation": rec, "horizon_key": "t1", "eval_status": status,
            "net_return_pct": net, "excess_return_pct": None,
            "note": None,
        })
    summary = summarize_performance(rows)
    assert summary["counts"]["total"] == 6
    assert summary["counts"]["pending"] == 1
    buy = [b for b in summary["buckets"] if b["recommendation"] == "BUY"][0]
    assert buy["successRatio"] == "2/3"
    assert buy["successRate"] == pytest.approx(66.7, abs=0.1)
    assert buy["avgNetReturnPct"] == pytest.approx((2.0 - 1.0 + 3.0) / 3, abs=0.1)
    assert buy["medianNetReturnPct"] == pytest.approx(2.0, abs=0.1)
    hold = [b for b in summary["buckets"] if b["recommendation"] == "HOLD"][0]
    assert hold["successRatio"] == "1/1"


def test_summarize_excludes_suspected_and_neutral():
    rows = [
        {"recommendation": "BUY", "horizon_key": "t1", "eval_status": "SUSPECTED_CORP_ACTION",
         "net_return_pct": 30.0, "note": None},
        {"recommendation": "BUY", "horizon_key": "t1", "eval_status": "WORKED",
         "net_return_pct": 2.0, "note": None},
        {"recommendation": "NO_DATA", "horizon_key": "t1", "eval_status": "NEUTRAL",
         "net_return_pct": None, "note": None},
    ]
    summary = summarize_performance(rows)
    assert summary["counts"]["suspected_corp_action"] == 1
    assert summary["counts"]["neutral"] == 1
    buy = [b for b in summary["buckets"] if b["recommendation"] == "BUY"][0]
    assert buy["successRatio"] == "1/1"      # corp-action row excluded from rate
