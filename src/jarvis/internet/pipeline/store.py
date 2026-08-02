"""
ExecutionStore for SQLite checkpoint persistence and clean pipeline crash recovery.
Manages SQLite table internet_execution_checkpoints.
Supports persistent in-memory database connections for unit tests.
"""

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("jarvis.internet.pipeline.store")


class ExecutionCheckpoint(BaseModel):
    version: int = 1
    execution_id: str
    step_id: str
    completed_steps: List[str] = Field(default_factory=list)
    state_json: str = ""
    saved_at: float = Field(default_factory=time.time)


class ExecutionStore:
    """Manages SQLite table internet_execution_checkpoints for pipeline step recovery."""

    def __init__(self, db_path: str = "data/sessions/jarvis.db") -> None:
        self.db_path = db_path
        self._mem_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:")

    def _get_connection(self) -> sqlite3.Connection:
        if self._mem_conn:
            return self._mem_conn
        return sqlite3.connect(self.db_path)

    def initialize(self) -> None:
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = self._get_connection()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS internet_execution_checkpoints (
                execution_id TEXT PRIMARY KEY,
                step_id TEXT NOT NULL,
                checkpoint_json TEXT NOT NULL,
                saved_at REAL NOT NULL
            )
            """
        )
        conn.commit()
        if not self._mem_conn:
            conn.close()

    def save_checkpoint(self, checkpoint: ExecutionCheckpoint) -> None:
        cp_json = checkpoint.model_dump_json()
        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO internet_execution_checkpoints (execution_id, step_id, checkpoint_json, saved_at)
            VALUES (?, ?, ?, ?)
            """,
            (checkpoint.execution_id, checkpoint.step_id, cp_json, checkpoint.saved_at),
        )
        conn.commit()
        if not self._mem_conn:
            conn.close()

    def get_checkpoint(self, execution_id: str) -> Optional[ExecutionCheckpoint]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT checkpoint_json FROM internet_execution_checkpoints WHERE execution_id = ?",
            (execution_id,),
        )
        row = cursor.fetchone()
        if not self._mem_conn:
            conn.close()
        if not row:
            return None
        return ExecutionCheckpoint.model_validate_json(row[0])
