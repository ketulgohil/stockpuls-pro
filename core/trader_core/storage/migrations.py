"""trader_core.storage.migrations - Schema Migration Runner.

Manages versioned schema migrations for SQLite persistence.
Enforces transactional execution and idempotent migration status tracking.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import sqlite3
from typing import Callable, Dict, List, Union

from .database import Database

logger = logging.getLogger(__name__)


def _migration_v1(conn: sqlite3.Connection) -> None:
    """Version 1 schema migration: alerts, decisions, outbox_events, audit_log."""
    conn.executescript(
        """
        -- Alerts table for interactive user price alerts
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            price REAL NOT NULL,
            direction TEXT NOT NULL,
            note TEXT,
            triggered INTEGER DEFAULT 0,
            triggered_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts(symbol);
        CREATE INDEX IF NOT EXISTS idx_alerts_triggered ON alerts(triggered);

        -- Decisions table for decision provenance and trading auditability
        CREATE TABLE IF NOT EXISTS decisions (
            decision_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            strategy TEXT NOT NULL,
            status TEXT NOT NULL,
            provenance_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_decisions_symbol ON decisions(symbol);

        -- Outbox events table for reliable semantic event publishing (Inngest)
        CREATE TABLE IF NOT EXISTS outbox_events (
            id TEXT PRIMARY KEY,
            event_name TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            retry_count INTEGER DEFAULT 0,
            last_error TEXT,
            created_at TEXT NOT NULL,
            dispatched_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_outbox_status_created
            ON outbox_events(status, created_at);

        -- Audit log table for platform events and incidents
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            symbol TEXT,
            entry_text TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
        """
    )


MIGRATIONS: Dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _migration_v1,
}


def run_migrations(
    target: Union[Database, sqlite3.Connection, str],
) -> List[int]:
    """Run all pending schema migrations on target database.

    Args:
        target: Database instance, sqlite3.Connection, or path string.

    Returns:
        List of newly applied migration version integers.
    """
    if isinstance(target, str):
        db = Database(target)
        conn = db.get_connection()
        should_close = True
    elif isinstance(target, Database):
        db = target
        conn = db.get_connection()
        should_close = db.db_path != ":memory:"
    else:
        conn = target
        should_close = False

    applied: List[int] = []
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                """
            )

        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_migrations ORDER BY version ASC;")
        existing_versions = {row[0] for row in cursor.fetchall()}

        for version in sorted(MIGRATIONS.keys()):
            if version not in existing_versions:
                logger.info("Applying schema migration version %d...", version)
                with conn:
                    MIGRATIONS[version](conn)
                    now_iso = datetime.now(timezone.utc).isoformat()
                    conn.execute(
                        "INSERT INTO schema_migrations (version, applied_at) "
                        "VALUES (?, ?);",
                        (version, now_iso),
                    )
                applied.append(version)
                logger.info(
                    "Schema migration version %d applied successfully.", version
                )
    finally:
        if should_close:
            conn.close()

    return applied
