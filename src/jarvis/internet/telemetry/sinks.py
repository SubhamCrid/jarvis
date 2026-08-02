"""
Pluggable MetricSink interfaces and implementations (SQLiteSink, ConsoleSink, MessageBusSink, NullSink).
Separates metric collection from metric storage.
Supports persistent in-memory database connections for unit tests.
"""

import json
import logging
import sqlite3
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("jarvis.internet.telemetry.sinks")


class MetricSink(ABC):
    """Abstract interface for telemetry metric sinks."""

    @abstractmethod
    async def record_metric(self, name: str, value: float, tags: Dict[str, Any]) -> None:
        pass


class NullSink(MetricSink):
    """Zero-overhead null sink for disabling metric persistence."""

    async def record_metric(self, name: str, value: float, tags: Dict[str, Any]) -> None:
        pass


class ConsoleSink(MetricSink):
    """Console logging metric sink."""

    async def record_metric(self, name: str, value: float, tags: Dict[str, Any]) -> None:
        logger.debug(f"[TELEMETRY] {name}={value} tags={tags}")


class SQLiteSink(MetricSink):
    """Persists metrics to SQLite table internet_metrics."""

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
            CREATE TABLE IF NOT EXISTS internet_metrics (
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                tags_json TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
            """
        )
        conn.commit()
        if not self._mem_conn:
            conn.close()

    async def record_metric(self, name: str, value: float, tags: Dict[str, Any]) -> None:
        conn = self._get_connection()
        conn.execute(
            "INSERT INTO internet_metrics (metric_name, metric_value, tags_json, timestamp) VALUES (?, ?, ?, ?)",
            (name, value, json.dumps(tags), time.time()),
        )
        conn.commit()
        if not self._mem_conn:
            conn.close()
