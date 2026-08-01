"""
Persistence store for tool executions, policy decisions, and audit traces.
Integrates with SQLite storage providers for historical replay and debugging.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from jarvis.tools.schemas import AuditEvent, ToolCall, ToolResult

logger = logging.getLogger("jarvis.tools.persistence")


class ToolStore:
    """SQLite-backed persistence manager storing tool traces and execution history."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path
        if self.db_path:
            self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database tables for tool trace records."""
        if not self.db_path:
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tool_traces (
                        event_id TEXT PRIMARY KEY,
                        call_id TEXT NOT NULL,
                        tool_name TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        task_id TEXT NOT NULL,
                        policy_decision TEXT,
                        start_time REAL,
                        duration_ms REAL,
                        success INTEGER,
                        redacted_summary TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
        except Exception as e:
            logger.error(f"Failed to initialize tool_traces table: {e}")
        finally:
            conn.close()

    def save_trace(self, event: AuditEvent) -> bool:
        """Persist an AuditEvent record to SQLite."""
        if not self.db_path:
            return False

        conn = sqlite3.connect(str(self.db_path))
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO tool_traces (
                        event_id, call_id, tool_name, session_id, task_id,
                        policy_decision, start_time, duration_ms, success, redacted_summary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.call_id,
                        event.tool_name,
                        event.session_id,
                        event.task_id,
                        json.dumps(event.policy_decision),
                        event.start_time,
                        event.duration_ms,
                        1 if event.success else 0,
                        event.redacted_summary,
                    ),
                )
            return True
        except Exception as e:
            logger.error(f"Error saving tool trace event {event.event_id}: {e}")
            return False
        finally:
            conn.close()

    def get_traces_for_session(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent tool trace records for a target session_id."""
        if not self.db_path or not self.db_path.exists():
            return []

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM tool_traces
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, limit),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error querying tool traces for session {session_id}: {e}")
            return []
        finally:
            conn.close()
