"""
Unified SessionStore Provider using SQLite and Filesystem for turns, tasks, recordings, and metrics.
"""

import asyncio
import datetime
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from vidya.core.base import HealthStatus, ServiceStatus
from vidya.providers.base import StorageProtocol

logger = logging.getLogger("vidya.providers.storage.session_store")


class SQLiteSessionStore(StorageProtocol):
    """
    Unified SessionStore persisting conversation turns, task states, metrics, and recordings
    using non-blocking asynchronous executor threads for SQLite operations.
    """

    def __init__(self, db_path: str = "data/sessions/vidya.db") -> None:
        self.db_path = Path(db_path)
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db_sync(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS turns (
                    turn_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT,
                    result TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recordings (
                    recording_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    duration_sec REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            conn.commit()
        finally:
            conn.close()

    async def initialize(self) -> bool:
        try:
            await asyncio.to_thread(self._init_db_sync)
            self._status = ServiceStatus.RUNNING
            logger.info(f"SQLiteSessionStore initialized at {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"Error initializing SQLite database: {e}", exc_info=True)
            self._status = ServiceStatus.ERROR
            return False

    def _create_session_sync(self, session_id: str, title: str) -> Dict[str, Any]:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO sessions (session_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, title, now, now),
            )
            conn.commit()
        finally:
            conn.close()
        return {"session_id": session_id, "title": title, "created_at": now}

    async def create_session(self, session_id: str, title: str = "New Session") -> Dict[str, Any]:
        return await asyncio.to_thread(self._create_session_sync, session_id, title)

    def _save_turn_sync(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        meta_str = json.dumps(metadata or {})
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO sessions (session_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, "Voice Session", now, now),
            )
            cursor.execute(
                "INSERT INTO turns (session_id, role, content, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, meta_str, now),
            )
            turn_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()
        return {
            "turn_id": turn_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "metadata": metadata,
            "created_at": now,
        }

    async def save_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(self._save_turn_sync, session_id, role, content, metadata)

    def _get_history_sync(self, session_id: str, limit: int) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []
        history = []
        conn = self._get_connection()
        ignored_phrases = [
            "please ensure ollama is active",
            "i can hear you clearly",
            "model response timed out",
            "check if your computer is under high load",
            "[blank_audio]",
            "subtitles by",
            "thanks for watching",
        ]
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content, metadata, created_at FROM turns WHERE session_id = ? ORDER BY turn_id DESC LIMIT ?",
                (session_id, limit * 2),
            )
            rows = cursor.fetchall()
            for r in reversed(rows):
                content_lower = r["content"].lower()
                if any(p in content_lower for p in ignored_phrases):
                    continue
                history.append({
                    "role": r["role"],
                    "content": r["content"],
                    "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                    "created_at": r["created_at"],
                })
                if len(history) >= limit:
                    break
        finally:
            conn.close()
        return history

    async def get_history(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._get_history_sync, session_id, limit)

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="SQLite storage status",
            details={"db_path": str(self.db_path)},
        )

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        pass

