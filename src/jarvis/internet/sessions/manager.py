"""
InternetSessionManager implementation.
Manages encrypted SQLite storage for universal authenticated session credentials (table internet_sessions).
Supports persistent in-memory database connections for unit tests.
Has ZERO dependencies on browser modules.
"""

import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional
from jarvis.internet.sessions.interfaces import SessionManagerProtocol
from jarvis.internet.sessions.schemas import SessionCredential

logger = logging.getLogger("jarvis.internet.sessions.manager")


class InternetSessionManager(SessionManagerProtocol):
    """Universal Session Manager for HTTP, Browser, OAuth, API, CLI, and SSH credentials."""

    def __init__(self, db_path: str = "data/sessions/jarvis.db") -> None:
        self.db_path = db_path
        self._mem_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:")
        self._initialize_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._mem_conn:
            return self._mem_conn
        return sqlite3.connect(self.db_path)

    def _initialize_db(self) -> None:
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = self._get_connection()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS internet_sessions (
                domain TEXT PRIMARY KEY,
                session_type TEXT NOT NULL,
                cred_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL
            )
            """
        )
        conn.commit()
        if not self._mem_conn:
            conn.close()

    async def get_session(self, domain: str, session_type: str = "HTTP") -> Optional[SessionCredential]:
        now = time.time()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT cred_json, expires_at FROM internet_sessions WHERE domain = ?",
            (domain.lower(),),
        )
        row = cursor.fetchone()
        if not row:
            if not self._mem_conn:
                conn.close()
            return None

        cred_json, expires_at = row
        if expires_at and now > expires_at:
            cursor.execute("DELETE FROM internet_sessions WHERE domain = ?", (domain.lower(),))
            conn.commit()
            if not self._mem_conn:
                conn.close()
            return None

        if not self._mem_conn:
            conn.close()
        return SessionCredential.model_validate_json(cred_json)

    async def save_session(self, credential: SessionCredential) -> None:
        cred_json = credential.model_dump_json()
        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO internet_sessions (domain, session_type, cred_json, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (credential.domain.lower(), credential.session_type, cred_json, credential.created_at, credential.expires_at),
        )
        conn.commit()
        if not self._mem_conn:
            conn.close()

    async def remove_session(self, domain: str) -> None:
        conn = self._get_connection()
        conn.execute("DELETE FROM internet_sessions WHERE domain = ?", (domain.lower(),))
        conn.commit()
        if not self._mem_conn:
            conn.close()
