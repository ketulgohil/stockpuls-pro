"""Durable storage for portfolio recommendations and their outcomes.

Uses the app's existing SQLite persistence layer
(``core.trader_core.storage``: WAL-mode ``Database`` + versioned migrations)
so recommendation history survives restarts. One immutable row is appended
per (scan, symbol, horizon); outcomes live in ``rec_evaluations``.

The database path can be overridden with the STOCKPULSE_REC_DB env var
(used by tests); default is ``data/trading.db``.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.trader_core.storage.database import Database
from core.trader_core.storage.migrations import run_migrations

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/trading.db"


def _now_ist_iso() -> str:
    from core.trader_core import IST
    return datetime.now(IST).isoformat(timespec="seconds")


class RecommendationStore:
    """SQLite-backed repository for immutable recommendation records."""

    def __init__(self, db_path: Optional[str] = None):
        self.db = Database(db_path or os.environ.get("STOCKPULSE_REC_DB") or DEFAULT_DB_PATH)
        self.db_path = self.db.db_path
        applied = run_migrations(self.db)
        if applied:
            logger.info("Recommendation store migrations applied: %s", applied)

    # ------------------------------------------------------------------
    # Scans
    # ------------------------------------------------------------------
    def insert_scan(
        self,
        trade_date: str,
        trigger: str,
        status: str,
        scanned_at: Optional[str] = None,
        holdings_count: int = 0,
        scanned_count: int = 0,
        no_data_count: int = 0,
        not_enough_data_count: int = 0,
        error: Optional[str] = None,
    ) -> int:
        with self.db.transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO rec_scans
                    (trade_date, trigger, status, scanned_at, holdings_count,
                     scanned_count, no_data_count, not_enough_data_count, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade_date, trigger, status, scanned_at or _now_ist_iso(),
                    holdings_count, scanned_count, no_data_count,
                    not_enough_data_count, error,
                ),
            )
            return int(cur.lastrowid)

    def update_scan(self, scan_id: int, status: str, error: Optional[str] = None) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE rec_scans SET status = ?, error = ? WHERE id = ?",
                (status, error, scan_id),
            )

    def latest_completed_scan(self) -> Optional[Dict[str, Any]]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM rec_scans WHERE status = 'completed' "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def has_completed_scan(self, trade_date: str) -> bool:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM rec_scans WHERE trade_date = ? AND status = 'completed' "
                "LIMIT 1",
                (trade_date,),
            ).fetchone()
        return row is not None

    def latest_scan_any_status(self) -> Optional[Dict[str, Any]]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM rec_scans ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def scan_counts_today(self, trade_date: str) -> int:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM rec_scans WHERE trade_date = ?",
                (trade_date,),
            ).fetchone()
        return int(row["c"]) if row else 0

    # ------------------------------------------------------------------
    # Recommendations (append-only)
    # ------------------------------------------------------------------
    def insert_recommendation(self, rec: Dict[str, Any]) -> str:
        rec_id = rec.get("id") or uuid.uuid4().hex[:12]
        now = _now_ist_iso()
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO rec_recommendations
                    (id, trade_date, symbol, exchange, horizon, recommendation,
                     generated_at, data_as_of, stale_data, reference_price,
                     reference_date, buy_score, sell_score, signals_json,
                     strategy, strategy_version, holding_qty, holding_avg_price,
                     holding_weight_pct, scan_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec_id,
                    rec["trade_date"],
                    rec["symbol"],
                    rec.get("exchange", "NSE"),
                    rec["horizon"],
                    rec["recommendation"],
                    rec.get("generated_at") or now,
                    rec.get("data_as_of"),
                    1 if rec.get("stale_data") else 0,
                    rec.get("reference_price"),
                    rec.get("reference_date"),
                    rec.get("buy_score"),
                    rec.get("sell_score"),
                    json.dumps(rec.get("signals") or [], ensure_ascii=False),
                    rec.get("strategy", "tech_signals_vote"),
                    rec.get("strategy_version", "1.0"),
                    rec.get("holding_qty"),
                    rec.get("holding_avg_price"),
                    rec.get("holding_weight_pct"),
                    rec.get("scan_id"),
                    now,
                ),
            )
        return rec_id

    def _row_to_rec(self, row: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(row)
        try:
            d["signals"] = json.loads(d.get("signals_json") or "[]")
        except (TypeError, ValueError):
            d["signals"] = []
        d.pop("signals_json", None)
        d["stale_data"] = bool(d.get("stale_data"))
        return d

    def latest_recommendations(self) -> Dict[str, Dict[str, Any]]:
        """Latest record per (symbol, horizon) — map symbol -> {horizon: rec}."""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT r.* FROM rec_recommendations r
                JOIN (
                    SELECT symbol, horizon, MAX(rowid) AS max_rowid
                    FROM rec_recommendations
                    GROUP BY symbol, horizon
                ) m ON r.symbol = m.symbol AND r.horizon = m.horizon
                    AND r.rowid = m.max_rowid
                """
            ).fetchall()
        out: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            rec = self._row_to_rec(row)
            out.setdefault(rec["symbol"], {})[rec["horizon"]] = rec
        return out

    def history_for_symbol(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM rec_recommendations WHERE symbol = ?
                ORDER BY rowid DESC LIMIT ?
                """,
                (symbol, max(1, min(limit, 500))),
            ).fetchall()
        return [self._row_to_rec(r) for r in rows]

    def get_recommendation(self, rec_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM rec_recommendations WHERE id = ?", (rec_id,)
            ).fetchone()
        return self._row_to_rec(row) if row else None

    def count_recommendations(self) -> int:
        with self.db.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM rec_recommendations").fetchone()
        return int(row["c"]) if row else 0

    # ------------------------------------------------------------------
    # Evaluations
    # ------------------------------------------------------------------
    def insert_pending_evaluations(self, rec_id: str, horizons: Dict[str, str]) -> None:
        """horizons maps horizon_key -> ISO end date (computed at creation)."""
        with self.db.transaction() as conn:
            for key, end_date in horizons.items():
                conn.execute(
                    """
                    INSERT OR IGNORE INTO rec_evaluations
                        (recommendation_id, horizon_key, status, end_date)
                    VALUES (?, ?, 'PENDING', ?)
                    """,
                    (rec_id, key, end_date),
                )

    def due_pending_evaluations(self, today: str) -> List[Dict[str, Any]]:
        """PENDING evaluations whose horizon end date has arrived (<= today)."""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT e.*, r.symbol, r.horizon, r.recommendation,
                       r.reference_price, r.reference_date, r.generated_at,
                       r.trade_date, r.strategy, r.strategy_version
                FROM rec_evaluations e
                JOIN rec_recommendations r ON r.id = e.recommendation_id
                WHERE e.status = 'PENDING' AND e.end_date IS NOT NULL
                  AND e.end_date <= ?
                """,
                (today,),
            ).fetchall()
        return [dict(r) for r in rows]

    def all_pending_count(self) -> int:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM rec_evaluations WHERE status = 'PENDING'"
            ).fetchone()
        return int(row["c"]) if row else 0

    def update_evaluation(self, rec_id: str, horizon_key: str, fields: Dict[str, Any]) -> None:
        cols = {
            "status", "end_date", "ref_price", "end_price", "gross_return_pct",
            "cost_pct", "net_return_pct", "bench_return_pct", "excess_return_pct",
            "mfe_pct", "mae_pct", "days_used", "note", "evaluated_at",
        }
        sets, vals = [], []
        for key, value in fields.items():
            if key in cols:
                sets.append(f"{key} = ?")
                vals.append(value)
        if not sets:
            return
        vals.extend([rec_id, horizon_key])
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE rec_evaluations SET {', '.join(sets)} "
                "WHERE recommendation_id = ? AND horizon_key = ?",
                tuple(vals),
            )

    def evaluation_rows(
        self,
        horizon: Optional[str] = None,
        rec_type: Optional[str] = None,
        since_date: Optional[str] = None,
        strategy: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Evaluation rows joined with their recommendation, for dashboards."""
        sql = (
            "SELECT r.*, e.status AS eval_status, e.horizon_key, e.end_date, "
            "e.ref_price, e.end_price, e.gross_return_pct, e.cost_pct, "
            "e.net_return_pct, e.bench_return_pct, e.excess_return_pct, "
            "e.mfe_pct, e.mae_pct, e.days_used, e.note, e.evaluated_at "
            "FROM rec_evaluations e JOIN rec_recommendations r "
            "ON r.id = e.recommendation_id WHERE 1=1"
        )
        params: List[Any] = []
        if horizon:
            sql += " AND r.horizon = ?"
            params.append(horizon)
        if rec_type:
            sql += " AND r.recommendation = ?"
            params.append(rec_type)
        if since_date:
            sql += " AND r.trade_date >= ?"
            params.append(since_date)
        if strategy:
            sql += " AND r.strategy = ?"
            params.append(strategy)
        sql += " ORDER BY r.rowid DESC LIMIT 5000"
        with self.db.connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            try:
                d["signals"] = json.loads(d.get("signals_json") or "[]")
            except (TypeError, ValueError):
                d["signals"] = []
            d.pop("signals_json", None)
            d["stale_data"] = bool(d.get("stale_data"))
            out.append(d)
        return out


_store: Optional[RecommendationStore] = None


def get_store() -> RecommendationStore:
    """Process-wide store (created lazily so tests can swap the DB path)."""
    global _store
    if _store is None:
        _store = RecommendationStore()
    return _store


def set_store(store: Optional[RecommendationStore]) -> None:
    global _store
    _store = store
