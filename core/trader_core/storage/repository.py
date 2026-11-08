"""trader_core.storage.repository - Domain Persistence Repositories.

Provides repository abstractions for:
- AlertRepository: Alert rule management with JSON migration support.
- DecisionRepository: Trade decision provenance recording.
- OutboxRepository: Transactional outbox event enqueueing and dispatch tracking.
- AuditRepository: Immutable audit trail logging.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
import sqlite3
import tempfile
import time
from typing import Any, Dict, List, Optional, Union
import uuid

from .database import Database

logger = logging.getLogger(__name__)

# Keys strictly forbidden from database rows and event payloads (THR-07
# credential hygiene)
SENSITIVE_KEY_SUBSTRINGS = {"access_token", "api_key", "secret", "password", "token"}


def sanitize_storage_data(data: Any) -> Any:
    """Recursively strip credential or secret fields from dictionaries and lists."""
    if isinstance(data, dict):
        clean: Dict[str, Any] = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if k_lower in ("instrument_key", "key") and isinstance(v, str) and (
                "|" in v or len(v) < 15
            ):
                clean[k] = sanitize_storage_data(v)
                continue
            if any(bad in k_lower for bad in SENSITIVE_KEY_SUBSTRINGS):
                continue
            clean[k] = sanitize_storage_data(v)
        return clean
    elif isinstance(data, list):
        return [sanitize_storage_data(item) for item in data]
    return data


class AlertRepository:
    """Repository for user price alert rules with SQLite persistence and JSON
    migration support."""

    def __init__(self, db: Database):
        self.db = db

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        triggered = bool(row["triggered"])
        triggered_at = row["triggered_at"]
        direction = row["direction"]
        return {
            "id": row["id"],
            "symbol": row["symbol"],
            "price": float(row["price"]),
            "direction": direction,
            "type": direction,
            "note": row["note"] or "",
            "triggered": triggered,
            "rung": triggered,
            "triggered_at": triggered_at,
            "rung_at": triggered_at,
            "created_at": row["created_at"],
        }

    def add_alert(
        self,
        symbol: str,
        price: float,
        direction: str = "above",
        note: str = "",
        alert_id: Optional[str] = None,
        created_at: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Add a price alert rule."""
        sym = symbol.strip().upper()
        p = float(price)
        d = str(direction).strip().lower()
        if d in ("above", "target", "high", ">", ">="):
            dir_norm = "above"
        elif d in ("below", "stop", "low", "<", "<="):
            dir_norm = "below"
        else:
            dir_norm = "above"

        if not alert_id:
            price_tag = str(int(p)) if p.is_integer() else f"{p:.2f}"
            alert_id = (
                f"{sym.lower()}-{dir_norm}-{price_tag}"
                f"-{int(time.time() * 1000) % 100000}"
            )

        now_iso = created_at or datetime.now(timezone.utc).isoformat()

        def _execute(c: sqlite3.Connection) -> None:
            c.execute(
                """
                INSERT INTO alerts
                (id, symbol, price, direction, note, triggered, triggered_at, created_at)
                VALUES (?, ?, ?, ?, ?, 0, NULL, ?);
                """,
                (alert_id, sym, p, dir_norm, note or "", now_iso),
            )

        if conn is not None:
            _execute(conn)
        else:
            with self.db.transaction() as c:
                _execute(c)

        return {
            "id": alert_id,
            "symbol": sym,
            "price": p,
            "direction": dir_norm,
            "type": dir_norm,
            "note": note or "",
            "triggered": False,
            "rung": False,
            "triggered_at": None,
            "rung_at": None,
            "created_at": now_iso,
        }

    def get_alerts(
        self,
        symbol: Optional[str] = None,
        active_only: bool = False,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve stored alert rules, optionally filtered by symbol or active status."""
        query = (
            "SELECT id, symbol, price, direction, note, triggered, "
            "triggered_at, created_at FROM alerts WHERE 1=1"
        )
        params: List[Any] = []
        if symbol:
            query += " AND UPPER(symbol) = UPPER(?)"
            params.append(symbol.strip())
        if active_only:
            query += " AND triggered = 0"
        query += " ORDER BY created_at ASC;"

        def _execute(c: sqlite3.Connection) -> List[Dict[str, Any]]:
            cursor = c.cursor()
            cursor.execute(query, params)
            return [self._row_to_dict(row) for row in cursor.fetchall()]

        if conn is not None:
            return _execute(conn)
        with self.db.connect() as c:
            return _execute(c)

    def get_alert(
        self, alert_id: str, conn: Optional[sqlite3.Connection] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a single alert rule by ID."""
        def _execute(c: sqlite3.Connection) -> Optional[Dict[str, Any]]:
            cursor = c.cursor()
            cursor.execute(
                "SELECT id, symbol, price, direction, note, triggered, "
                "triggered_at, created_at FROM alerts WHERE id = ?;",
                (alert_id,),
            )
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None

        if conn is not None:
            return _execute(conn)
        with self.db.connect() as c:
            return _execute(c)

    def delete_alert(
        self, alert_id: str, conn: Optional[sqlite3.Connection] = None
    ) -> bool:
        """Delete an alert rule by ID."""
        def _execute(c: sqlite3.Connection) -> bool:
            cursor = c.cursor()
            cursor.execute("DELETE FROM alerts WHERE id = ?;", (alert_id,))
            return cursor.rowcount > 0

        if conn is not None:
            return _execute(conn)
        with self.db.transaction() as c:
            return _execute(c)

    def mark_triggered(
        self,
        alert_id: str,
        triggered_at: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> bool:
        """Mark an alert rule as triggered/rung."""
        now_iso = triggered_at or datetime.now(timezone.utc).isoformat()

        def _execute(c: sqlite3.Connection) -> bool:
            cursor = c.cursor()
            cursor.execute(
                "UPDATE alerts SET triggered = 1, triggered_at = ? "
                "WHERE id = ? AND triggered = 0;",
                (now_iso, alert_id),
            )
            return cursor.rowcount > 0

        if conn is not None:
            return _execute(conn)
        with self.db.transaction() as c:
            return _execute(c)

    def reset_alert(
        self, alert_id: str, conn: Optional[sqlite3.Connection] = None
    ) -> bool:
        """Reset an alert rule back to untriggered state."""
        def _execute(c: sqlite3.Connection) -> bool:
            cursor = c.cursor()
            cursor.execute(
                "UPDATE alerts SET triggered = 0, triggered_at = NULL WHERE id = ?;",
                (alert_id,),
            )
            return cursor.rowcount > 0

        if conn is not None:
            return _execute(conn)
        with self.db.transaction() as c:
            return _execute(c)

    def import_from_json(self, json_path: str) -> int:
        """Import legacy alert rules from JSON file into SQLite.

        Returns count of imported rules.
        """
        if not os.path.isfile(json_path):
            return 0

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(
                "Failed to read legacy alerts JSON at %s: %s", json_path, e
            )
            return 0

        rules: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            rules = data.get("rules", [])
        elif isinstance(data, list):
            rules = data

        if not rules:
            return 0

        imported = 0
        with self.db.transaction() as conn:
            for r in rules:
                if not isinstance(r, dict):
                    continue
                aid = str(r.get("id") or uuid.uuid4().hex)
                sym = str(r.get("symbol", "")).strip().upper()
                if not sym:
                    continue
                price = float(r.get("price", 0.0))
                direction = str(
                    r.get("direction") or r.get("type", "above")
                ).strip().lower()
                note = str(r.get("note", ""))
                triggered = 1 if (r.get("triggered") or r.get("rung")) else 0
                triggered_at = r.get("triggered_at") or r.get("rung_at")
                created_at = r.get("created_at") or datetime.now(timezone.utc).isoformat()

                conn.execute(
                    """
                    INSERT OR REPLACE INTO alerts
                    (id, symbol, price, direction, note, triggered, triggered_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (aid, sym, price, direction, note, triggered, triggered_at, created_at),
                )
                imported += 1

        logger.info(
            "Imported %d alert rules from %s into SQLite.", imported, json_path
        )
        return imported

    def export_to_json(self, json_path: str) -> int:
        """Export current SQLite alert rules to legacy JSON format atomically."""
        alerts = self.get_alerts()
        parent_dir = os.path.dirname(os.path.abspath(json_path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        payload = {"rules": alerts}
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix="alerts_export_", suffix=".json", dir=parent_dir
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, json_path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        return len(alerts)


class DecisionRepository:
    """Repository for trade decision records and provenance tracking."""

    def __init__(self, db: Database):
        self.db = db

    def record_decision(
        self,
        decision_id: str,
        symbol: str,
        strategy: str,
        status: str,
        provenance: Union[Dict[str, Any], str],
        created_at: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Record trade decision provenance."""
        sym = symbol.strip().upper()
        now_iso = created_at or datetime.now(timezone.utc).isoformat()

        if isinstance(provenance, dict):
            clean_prov = sanitize_storage_data(provenance)
            prov_json = json.dumps(clean_prov)
        else:
            prov_json = str(provenance)

        def _execute(c: sqlite3.Connection) -> None:
            c.execute(
                """
                INSERT INTO decisions
                (decision_id, symbol, strategy, status, provenance_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (decision_id, sym, strategy, status, prov_json, now_iso),
            )

        if conn is not None:
            _execute(conn)
        else:
            with self.db.transaction() as c:
                _execute(c)

        return {
            "decision_id": decision_id,
            "symbol": sym,
            "strategy": strategy,
            "status": status,
            "provenance_json": prov_json,
            "created_at": now_iso,
        }

    def get_decision(
        self, decision_id: str, conn: Optional[sqlite3.Connection] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a recorded decision by ID."""
        def _execute(c: sqlite3.Connection) -> Optional[Dict[str, Any]]:
            cursor = c.cursor()
            cursor.execute(
                "SELECT decision_id, symbol, strategy, status, provenance_json, "
                "created_at FROM decisions WHERE decision_id = ?;",
                (decision_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            prov_raw = row["provenance_json"]
            try:
                prov_dict = json.loads(prov_raw)
            except Exception:
                prov_dict = prov_raw

            return {
                "decision_id": row["decision_id"],
                "symbol": row["symbol"],
                "strategy": row["strategy"],
                "status": row["status"],
                "provenance": prov_dict,
                "provenance_json": prov_raw,
                "created_at": row["created_at"],
            }

        if conn is not None:
            return _execute(conn)
        with self.db.connect() as c:
            return _execute(c)

    def get_decisions(
        self,
        symbol: Optional[str] = None,
        limit: int = 50,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve latest decisions, optionally filtered by symbol."""
        query = (
            "SELECT decision_id, symbol, strategy, status, provenance_json, "
            "created_at FROM decisions"
        )
        params: List[Any] = []
        if symbol:
            query += " WHERE UPPER(symbol) = UPPER(?)"
            params.append(symbol.strip())
        query += " ORDER BY created_at DESC LIMIT ?;"
        params.append(limit)

        def _execute(c: sqlite3.Connection) -> List[Dict[str, Any]]:
            cursor = c.cursor()
            cursor.execute(query, params)
            results = []
            for row in cursor.fetchall():
                prov_raw = row["provenance_json"]
                try:
                    prov_dict = json.loads(prov_raw)
                except Exception:
                    prov_dict = prov_raw
                results.append({
                    "decision_id": row["decision_id"],
                    "symbol": row["symbol"],
                    "strategy": row["strategy"],
                    "status": row["status"],
                    "provenance": prov_dict,
                    "provenance_json": prov_raw,
                    "created_at": row["created_at"],
                })
            return results

        if conn is not None:
            return _execute(conn)
        with self.db.connect() as c:
            return _execute(c)


class OutboxRepository:
    """Repository for transactional outbox events to be published to Inngest."""

    def __init__(self, db: Database):
        self.db = db

    def enqueue_event(
        self,
        event_name: str,
        data: Dict[str, Any],
        idempotency_key: str,
        event_id: Optional[str] = None,
        created_at: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> str:
        """Enqueue a semantic event for outbox delivery.

        Raises sqlite3.IntegrityError if idempotency_key already exists.
        """
        eid = event_id or uuid.uuid4().hex
        now_iso = created_at or datetime.now(timezone.utc).isoformat()
        clean_data = sanitize_storage_data(data)
        payload_json = json.dumps(clean_data)

        def _execute(c: sqlite3.Connection) -> None:
            c.execute(
                """
                INSERT INTO outbox_events
                (id, event_name, idempotency_key, payload_json, status,
                 retry_count, last_error, created_at, dispatched_at)
                VALUES (?, ?, ?, ?, 'PENDING', 0, NULL, ?, NULL);
                """,
                (eid, event_name, idempotency_key, payload_json, now_iso),
            )

        if conn is not None:
            _execute(conn)
        else:
            with self.db.transaction() as c:
                _execute(c)

        return eid

    def fetch_pending(
        self, limit: int = 20, conn: Optional[sqlite3.Connection] = None
    ) -> List[Dict[str, Any]]:
        """Fetch pending outbox events ordered by created_at."""
        query = """
            SELECT id, event_name, idempotency_key, payload_json, status,
                   retry_count, last_error, created_at, dispatched_at
            FROM outbox_events
            WHERE status = 'PENDING'
            ORDER BY created_at ASC
            LIMIT ?;
        """

        def _execute(c: sqlite3.Connection) -> List[Dict[str, Any]]:
            cursor = c.cursor()
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            events = []
            for r in rows:
                p_json = r["payload_json"]
                try:
                    payload = json.loads(p_json)
                except Exception:
                    payload = {}
                events.append({
                    "id": r["id"],
                    "event_name": r["event_name"],
                    "idempotency_key": r["idempotency_key"],
                    "payload_json": p_json,
                    "payload": payload,
                    "data": payload,
                    "status": r["status"],
                    "retry_count": int(r["retry_count"]),
                    "last_error": r["last_error"],
                    "created_at": r["created_at"],
                    "dispatched_at": r["dispatched_at"],
                })
            return events

        if conn is not None:
            return _execute(conn)
        with self.db.connect() as c:
            return _execute(c)

    def mark_dispatched(
        self,
        event_id: str,
        dispatched_at: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> bool:
        """Mark an outbox event as successfully dispatched."""
        now_iso = dispatched_at or datetime.now(timezone.utc).isoformat()

        def _execute(c: sqlite3.Connection) -> bool:
            cursor = c.cursor()
            cursor.execute(
                "UPDATE outbox_events SET status = 'DISPATCHED', "
                "dispatched_at = ? WHERE id = ?;",
                (now_iso, event_id),
            )
            return cursor.rowcount > 0

        if conn is not None:
            return _execute(conn)
        with self.db.transaction() as c:
            return _execute(c)

    def mark_failed(
        self,
        event_id: str,
        error: str,
        max_retries: int = 5,
        conn: Optional[sqlite3.Connection] = None,
    ) -> bool:
        """Increment retry count and update error message.

        Transitions to 'FAILED' (dead-letter) when retry_count reaches
        max_retries.
        """
        def _execute(c: sqlite3.Connection) -> bool:
            cursor = c.cursor()
            cursor.execute(
                "SELECT retry_count FROM outbox_events WHERE id = ?;", (event_id,)
            )
            row = cursor.fetchone()
            if not row:
                return False
            retries = int(row["retry_count"]) + 1
            new_status = "FAILED" if retries >= max_retries else "PENDING"
            cursor.execute(
                "UPDATE outbox_events SET retry_count = ?, last_error = ?, "
                "status = ? WHERE id = ?;",
                (retries, str(error), new_status, event_id),
            )
            return True

        if conn is not None:
            return _execute(conn)
        with self.db.transaction() as c:
            return _execute(c)

    def count_pending(
        self, conn: Optional[sqlite3.Connection] = None
    ) -> int:
        """Count pending outbox events awaiting dispatch."""
        def _execute(c: sqlite3.Connection) -> int:
            cursor = c.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM outbox_events WHERE status = 'PENDING';"
            )
            row = cursor.fetchone()
            return int(row[0]) if row else 0

        if conn is not None:
            return _execute(conn)
        with self.db.connect() as c:
            return _execute(c)

    def get_event(
        self, event_id: str, conn: Optional[sqlite3.Connection] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a specific outbox event by ID."""
        def _execute(c: sqlite3.Connection) -> Optional[Dict[str, Any]]:
            cursor = c.cursor()
            cursor.execute(
                """
                SELECT id, event_name, idempotency_key, payload_json, status,
                       retry_count, last_error, created_at, dispatched_at
                FROM outbox_events WHERE id = ?;
                """,
                (event_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            try:
                payload = json.loads(row["payload_json"])
            except Exception:
                payload = {}
            return {
                "id": row["id"],
                "event_name": row["event_name"],
                "idempotency_key": row["idempotency_key"],
                "payload_json": row["payload_json"],
                "payload": payload,
                "data": payload,
                "status": row["status"],
                "retry_count": int(row["retry_count"]),
                "last_error": row["last_error"],
                "created_at": row["created_at"],
                "dispatched_at": row["dispatched_at"],
            }

        if conn is not None:
            return _execute(conn)
        with self.db.connect() as c:
            return _execute(c)

    def get_event_by_idempotency_key(
        self, idempotency_key: str,
        conn: Optional[sqlite3.Connection] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a specific outbox event by its unique idempotency key."""
        def _execute(c: sqlite3.Connection) -> Optional[Dict[str, Any]]:
            cursor = c.cursor()
            cursor.execute(
                """
                SELECT id, event_name, idempotency_key, payload_json, status,
                       retry_count, last_error, created_at, dispatched_at
                FROM outbox_events WHERE idempotency_key = ?;
                """,
                (idempotency_key,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            try:
                payload = json.loads(row["payload_json"])
            except Exception:
                payload = {}
            return {
                "id": row["id"],
                "event_name": row["event_name"],
                "idempotency_key": row["idempotency_key"],
                "payload_json": row["payload_json"],
                "payload": payload,
                "data": payload,
                "status": row["status"],
                "retry_count": int(row["retry_count"]),
                "last_error": row["last_error"],
                "created_at": row["created_at"],
                "dispatched_at": row["dispatched_at"],
            }

        if conn is not None:
            return _execute(conn)
        with self.db.connect() as c:
            return _execute(c)


class AuditRepository:
    """Repository for durable platform audit logging."""

    def __init__(self, db: Database):
        self.db = db

    def append_log(
        self,
        event_type: str,
        symbol: Optional[str],
        entry_text: str,
        timestamp: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Append an entry to the audit log table."""
        sym = symbol.strip().upper() if symbol else None
        now_iso = timestamp or datetime.now(timezone.utc).isoformat()

        def _execute(c: sqlite3.Connection) -> int:
            cursor = c.cursor()
            cursor.execute(
                """
                INSERT INTO audit_log (event_type, symbol, entry_text, timestamp)
                VALUES (?, ?, ?, ?);
                """,
                (event_type, sym, entry_text, now_iso),
            )
            return cursor.lastrowid or 0

        if conn is not None:
            return _execute(conn)
        with self.db.transaction() as c:
            return _execute(c)

    def get_logs(
        self,
        symbol: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve audit log entries."""
        query = (
            "SELECT id, event_type, symbol, entry_text, timestamp FROM audit_log "
            "WHERE 1=1"
        )
        params: List[Any] = []
        if symbol:
            query += " AND UPPER(symbol) = UPPER(?)"
            params.append(symbol.strip())
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        query += " ORDER BY id DESC LIMIT ?;"
        params.append(limit)

        def _execute(c: sqlite3.Connection) -> List[Dict[str, Any]]:
            cursor = c.cursor()
            cursor.execute(query, params)
            return [
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "symbol": row["symbol"],
                    "entry_text": row["entry_text"],
                    "timestamp": row["timestamp"],
                }
                for row in cursor.fetchall()
            ]

        if conn is not None:
            return _execute(conn)
        with self.db.connect() as c:
            return _execute(c)
