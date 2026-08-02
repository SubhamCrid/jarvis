"""
JobStore for SQLite persistence of InternetJob records.
Manages SQLite table internet_jobs in data/sessions/jarvis.db.
Supports persistent in-memory database connections for unit tests.
"""

import logging
import sqlite3
import time
from pathlib import Path
from typing import List, Optional
from jarvis.internet.jobs.schemas import InternetJob, JobState

logger = logging.getLogger("jarvis.internet.jobs.store")


class JobStore:
    """Manages persistent SQLite storage for InternetJob records."""

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
            CREATE TABLE IF NOT EXISTS internet_jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                progress REAL NOT NULL,
                query TEXT NOT NULL,
                job_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.commit()
        if not self._mem_conn:
            conn.close()

    def save_job(self, job: InternetJob) -> None:
        job.updated_at = time.time()
        job_json = job.model_dump_json()
        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO internet_jobs (job_id, status, progress, query, job_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (job.job_id, job.status.value, job.progress, job.query, job_json, job.created_at, job.updated_at),
        )
        conn.commit()
        if not self._mem_conn:
            conn.close()

    def get_job(self, job_id: str) -> Optional[InternetJob]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT job_json FROM internet_jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        if not self._mem_conn:
            conn.close()
        if not row:
            return None
        return InternetJob.model_validate_json(row[0])

    def list_jobs(self, status: Optional[JobState] = None) -> List[InternetJob]:
        conn = self._get_connection()
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT job_json FROM internet_jobs WHERE status = ?", (status.value,))
        else:
            cursor.execute("SELECT job_json FROM internet_jobs")
        rows = cursor.fetchall()
        if not self._mem_conn:
            conn.close()
        return [InternetJob.model_validate_json(r[0]) for r in rows]
