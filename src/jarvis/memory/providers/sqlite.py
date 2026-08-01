"""
SQLite-backed multi-type memory provider implementation for Jarvis Memory Platform.
"""

import json, sqlite3, time
from typing import List, Optional
from jarvis.memory.schemas import (
    MemoryItem,
    MemoryQuery,
    MemorySearchResult,
    MemoryType,
)
from jarvis.memory.providers.base import (
    BaseMemoryProvider,
    WorkingMemoryProvider,
    EpisodicMemoryProvider,
    SemanticMemoryProvider,
    UserProfileMemoryProvider,
    KnowledgeStoreMemoryProvider,
)


class SQLiteMemoryProvider(
    WorkingMemoryProvider,
    EpisodicMemoryProvider,
    SemanticMemoryProvider,
    UserProfileMemoryProvider,
    KnowledgeStoreMemoryProvider,
):
    """
    Persistent SQLite memory provider capable of managing any distinct MemoryType.
    """

    def __init__(
        self,
        memory_type: MemoryType = MemoryType.WORKING,
        db_path: str = ":memory:",
    ) -> None:
        self._memory_type = memory_type
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def memory_type(self) -> MemoryType:
        return self._memory_type

    async def initialize(self) -> bool:
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    key TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    tags_json TEXT NOT NULL,
                    session_id TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
        return True

    async def store(self, item: MemoryItem) -> MemoryItem:
        if not self._conn:
            await self.initialize()
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO memory_items (
                    id, memory_type, key, content, metadata_json, confidence, tags_json, session_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.memory_type.value,
                    item.key,
                    item.content,
                    json.dumps(item.metadata),
                    item.confidence,
                    json.dumps(item.tags),
                    item.session_id,
                    item.created_at,
                    item.updated_at,
                ),
            )
        return item

    async def query(self, query: MemoryQuery) -> List[MemorySearchResult]:
        if not self._conn:
            await self.initialize()

        cursor = self._conn.cursor()
        q_lower = f"%{query.query_text.lower()}%"
        cursor.execute(
            """
            SELECT * FROM memory_items 
            WHERE memory_type = ? AND (LOWER(key) LIKE ? OR LOWER(content) LIKE ?)
            LIMIT ?
            """,
            (self._memory_type.value, q_lower, q_lower, query.limit),
        )

        results = []
        for row in cursor.fetchall():
            item = MemoryItem(
                id=row["id"],
                memory_type=MemoryType(row["memory_type"]),
                key=row["key"],
                content=row["content"],
                metadata=json.loads(row["metadata_json"]),
                confidence=row["confidence"],
                tags=json.loads(row["tags_json"]),
                session_id=row["session_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            results.append(MemorySearchResult(item=item, relevance_score=0.9, matched_by="sqlite_keyword"))
        return results

    async def delete(self, memory_id: str) -> bool:
        if not self._conn:
            return False
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM memory_items WHERE id = ? AND memory_type = ?",
                (memory_id, self._memory_type.value),
            )
            return cur.rowcount > 0

    async def clear(self, session_id: Optional[str] = None) -> int:
        if not self._conn:
            return 0
        with self._conn:
            if session_id:
                cur = self._conn.execute(
                    "DELETE FROM memory_items WHERE session_id = ? AND memory_type = ?",
                    (session_id, self._memory_type.value),
                )
            else:
                cur = self._conn.execute(
                    "DELETE FROM memory_items WHERE memory_type = ?",
                    (self._memory_type.value,),
                )
            return cur.rowcount
