"""trader_core.storage.database - SQLite Database Connection Management.

Provides thread-safe connection factory and transaction context manager for
local SQLite persistence with WAL mode, normal synchronous durability, 10s busy
timeout, and foreign keys enabled.
"""

from __future__ import annotations

from contextlib import contextmanager
import logging
import os
import sqlite3
import threading
from typing import Any, Generator, Optional, Union

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "trader/trader.db"


class Database:
    """Thread-safe SQLite database manager enforcing WAL mode and
    single-writer concurrency."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._lock = threading.RLock()
        self._mem_conn: Optional[sqlite3.Connection] = None

        if self.db_path != ":memory:" and not self.db_path.startswith("file:"):
            parent_dir = os.path.dirname(os.path.abspath(self.db_path))
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

    def _configure_connection(self, conn: sqlite3.Connection) -> sqlite3.Connection:
        """Applies WAL mode, row factory, timeouts, and foreign key pragmas."""
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA busy_timeout=10000;")
        finally:
            cursor.close()
        return conn

    def get_connection(self) -> sqlite3.Connection:
        """Create or retrieve a configured SQLite connection.

        For ':memory:' databases, a single persistent connection is retained
        for the instance. For disk files, each call returns a dedicated
        connection configured with WAL and busy timeout.
        """
        with self._lock:
            if self.db_path == ":memory:":
                if self._mem_conn is None:
                    conn = sqlite3.connect(
                        ":memory:",
                        timeout=10.0,
                        check_same_thread=False,
                    )
                    self._mem_conn = self._configure_connection(conn)
                return self._mem_conn

            conn = sqlite3.connect(
                self.db_path,
                timeout=10.0,
                check_same_thread=False,
            )
            return self._configure_connection(conn)

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager yielding an active database connection."""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            if self.db_path != ":memory:":
                conn.close()

    @contextmanager
    def transaction(
        self, conn: Optional[sqlite3.Connection] = None
    ) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for an atomic database transaction.

        Serializes writes across threads using a lock, commits on clean exit,
        and rolls back on any exception.
        """
        with self._lock:
            active_conn = conn or self.get_connection()
            close_on_exit = conn is None and self.db_path != ":memory:"
            try:
                yield active_conn
                active_conn.commit()
            except Exception:
                try:
                    active_conn.rollback()
                except Exception as rollback_err:
                    logger.warning(
                        "Error during transaction rollback: %s", rollback_err
                    )
                raise
            finally:
                if close_on_exit:
                    active_conn.close()

    def execute(
        self, sql: str, params: Union[tuple, list, dict] = ()
    ) -> sqlite3.Cursor:
        """Convenience method to execute a statement within an atomic transaction."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor

    def close(self) -> None:
        """Closes any persistent in-memory connection."""
        with self._lock:
            if self._mem_conn is not None:
                try:
                    self._mem_conn.close()
                except Exception:
                    pass
                self._mem_conn = None
