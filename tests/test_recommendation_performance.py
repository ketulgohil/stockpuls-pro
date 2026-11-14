"""Tests for the recommendation performance dashboard: store filters,
statistics payload and the authenticated API endpoints. Storage is sandboxed;
the real data/portfolio.json and data/trading.db are never touched."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core import recommendation_store as rec_store
from core.recommendation_evaluator import summarize_performance
from core.recommendation_store import RecommendationStore
from core.auth import get_api_key


@pytest.fixture
def store(tmp_path, monkeypatch):
    s = RecommendationStore(str(tmp_path / "rec.db"))
    monkeypatch.setattr(rec_store, "_store", s)
    yield s
    monkeypatch.setattr(rec_store, "_store", None)


def _seed_outcome(store, symbol, rec_type, trade_date, status, net, horizon_key="t1",
                  horizon="daily_swing", strategy="tech_signals_vote"):
    rec_id = store.insert_recommendation({
        "trade_date": trade_date, "symbol": symbol, "horizon": horizon,
        "recommendation": rec_type, "reference_price": 100.0,
        "reference_date": trade_date, "signals": [],
        "strategy": strategy, "strategy_version": "1.0",
    })
    store.insert_pending_evaluations(rec_id, {horizon_key: trade_date})
    store.update_evaluation(rec_id, horizon_key, {
        "status": status, "net_return_pct": net, "gross_return_pct": net,
        "evaluated_at": trade_date,
    })
    return rec_id


# ---------------------------------------------------------------------------
# Store filters
# ---------------------------------------------------------------------------
def test_evaluation_rows_filters(store):
    _seed_outcome(store, "A.NS", "BUY", "2026-11-02", "WORKED", 2.0)
    _seed_outcome(store, "B.NS", "SELL", "2026-11-05", "NOT_WORKED", -1.0)
    _seed_outcome(store, "C.NS", "BUY", "2026-11-05", "PENDING", None)

    assert len(store.evaluation_rows()) == 3
    assert len(store.evaluation_rows(rec_type="BUY")) == 2
    assert len(store.evaluation_rows(rec_type="BUY", since_date="2026-11-04")) == 1
    assert len(store.evaluation_rows(horizon="intraday")) == 0
    rows = store.evaluation_rows(strategy="other_strategy")
    assert rows == []


def test_summarize_benchmark_fields():
    _rows = [
        {"recommendation": "BUY", "horizon_key": "t1", "eval_status": "WORKED",
         "net_return_pct": 3.0, "excess_return_pct": 1.0, "note": None},
    ]
    summary = summarize_performance(_rows)
    bucket = summary["buckets"][0]
    assert bucket["avgExcessVsNiftyPct"] == pytest.approx(1.0)
    assert summary["definitions"]["daily_swing"]["BUY"]


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    from main import app
    return TestClient(app)


HEADERS = {"X-API-Key": get_api_key()}


def test_api_requires_auth(client):
    res = client.get("/api/portfolio/recommendations/latest")
    assert res.status_code == 401


def test_api_latest_shape(store, client, monkeypatch):
    monkeypatch.setattr(
        "api.portfolio_recommendations.get_portfolio",
        lambda: [{"symbol": "TESTA.NS", "quantity": 10, "buyPrice": 100.0}])
    store.insert_recommendation({
        "trade_date": "2026-11-13", "symbol": "TESTA.NS", "horizon": "daily_swing",
        "recommendation": "HOLD", "reference_price": 100.0,
        "reference_date": "2026-11-13", "signals": [],
        "strategy": "tech_signals_vote", "strategy_version": "1.0",
    })
    res = client.get("/api/portfolio/recommendations/latest", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "TESTA.NS" in data["recommendations"]
    assert data["recommendations"]["TESTA.NS"]["daily_swing"]["recommendation"] == "HOLD"
    assert data["scan"] is None          # no scan recorded yet in sandbox
    assert "nextScanAt" in data


def test_api_performance_payload(store, client):
    _seed_outcome(store, "A.NS", "BUY", "2026-11-02", "WORKED", 2.0)
    _seed_outcome(store, "A.NS", "BUY", "2026-11-05", "NOT_WORKED", -1.0)
    res = client.get("/api/portfolio/recommendations/performance?days=90", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["counts"]["total"] == 2
    buy = [b for b in data["buckets"] if b["recommendation"] == "BUY"][0]
    assert buy["successRatio"] == "1/2"
    assert data["definitions"]["daily_swing"]["BUY"]   # exact definition exposed


def test_api_history_unknown_symbol_404(store, client):
    res = client.get("/api/portfolio/recommendations/history?symbol=ZZZZZ.NS", headers=HEADERS)
    assert res.status_code == 404


def test_api_history_returns_immutable_rows(store, client):
    store.insert_recommendation({
        "trade_date": "2026-11-12", "symbol": "TESTA.NS", "horizon": "daily_swing",
        "recommendation": "BUY", "reference_price": 100.0, "reference_date": "2026-11-12",
        "signals": [{"indicator": "RSI", "type": "BUY", "strength": "Strong",
                     "message": "RSI oversold at 28.0"}],
        "strategy": "tech_signals_vote", "strategy_version": "1.0",
    })
    store.insert_recommendation({
        "trade_date": "2026-11-13", "symbol": "TESTA.NS", "horizon": "daily_swing",
        "recommendation": "HOLD", "reference_price": 101.0, "reference_date": "2026-11-13",
        "signals": [], "strategy": "tech_signals_vote", "strategy_version": "1.0",
    })
    res = client.get("/api/portfolio/recommendations/history?symbol=TESTA", headers=HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 2
    recs = [r["recommendation"] for r in data["records"]]
    assert recs == ["HOLD", "BUY"]      # newest first, both preserved


def test_api_rescan_cooldown_429(store, client, monkeypatch):
    from core import portfolio_recommendations as pr
    monkeypatch.setattr(pr, "run_manual_rescan",
                        lambda: {"status": "cooldown", "error": "Manual rescan available in 9m 59s"})
    res = client.post("/api/portfolio/recommendations/rescan", headers=HEADERS)
    assert res.status_code == 429
