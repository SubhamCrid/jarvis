"""
SQLiteInternetCache implementation.
Persists InternetResult objects into SQLite data/sessions/jarvis.db with TTL and schema validation.
"""

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional
from jarvis.core.base import HealthStatus, ServiceStatus
from jarvis.internet.interfaces.cache import CacheProvider
from jarvis.internet.schemas import InternetResult

logger = logging.getLogger("jarvis.internet.providers.cache.sqlite")


class SQLiteInternetCache(CacheProvider):
    name = "sqlite"
    version = "1.0.0"

    def __init__(self, db_path: str = "data/sessions/jarvis.db") -> None:
        self.db_path = db_path
        self._status = ServiceStatus.UNINITIALIZED

    async def initialize(self) -> bool:
        """Create sqlite table if not exists."""
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS internet_pipeline_cache (
                    cache_key TEXT PRIMARY KEY,
                    result_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            conn.commit()

        self._status = ServiceStatus.RUNNING
        return True

    async def health(self) -> HealthStatus:
        return HealthStatus(status=self._status, message="SQLiteInternetCache operational")

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        pass

    async def get_result(self, key: str) -> Optional[InternetResult]:
        now = time.time()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT result_json, expires_at FROM internet_pipeline_cache WHERE cache_key = ?",
                    (key,),
                )
                row = cursor.fetchone()
                if not row:
                    return None

                result_json, expires_at = row
                if now > expires_at:
                    cursor.execute("DELETE FROM internet_pipeline_cache WHERE cache_key = ?", (key,))
                    conn.commit()
                    return None

                return InternetResult.model_validate_json(result_json)
        except Exception as e:
            logger.warning(f"Cache get_result failed for key '{key}': {e}")
            return None

    async def set_result(self, key: str, result: InternetResult, ttl_sec: int = 86400) -> None:
        now = time.time()
        expires_at = now + ttl_sec
        try:
            result_json = result.model_dump_json()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO internet_pipeline_cache (cache_key, result_json, created_at, expires_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (key, result_json, now, expires_at),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Cache set_result failed for key '{key}': {e}")
