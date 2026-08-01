"""
SearchIndexManager owning local SQLite search index, incremental indexing,
and change tracking.
"""

import asyncio
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from jarvis.search.schemas import SearchMatch, SearchTargetType

logger = logging.getLogger("jarvis.search.index_manager")


class SearchIndexManager:
    """Manages local SQLite index at data/search/index.db for fast metadata searches."""

    def __init__(self, db_path: Optional[Path] = None, workspace_root: Optional[Path] = None) -> None:
        self.db_path = db_path or Path("data/search/index.db").resolve()
        self.workspace_root = (workspace_root or Path.cwd()).resolve()
        self._is_indexing = False
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite index tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS file_index (
                        path TEXT PRIMARY KEY,
                        filename TEXT NOT NULL,
                        is_dir INTEGER NOT NULL,
                        extension TEXT,
                        size_bytes INTEGER,
                        modified_at REAL,
                        indexed_at REAL
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_filename ON file_index(filename);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_extension ON file_index(extension);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_modified ON file_index(modified_at);")
        except Exception as e:
            logger.error(f"Failed to initialize search index database: {e}")
        finally:
            conn.close()

    async def index_workspace(self, max_files: int = 5000) -> int:
        """Perform asynchronous background indexing of the workspace directory."""
        if self._is_indexing:
            return 0

        self._is_indexing = True
        indexed_count = 0
        t0 = time.time()

        try:
            records = []
            for p in self.workspace_root.rglob("*"):
                # Skip .git, __pycache__, node_modules, .pytest_cache
                if any(ignored in p.parts for ignored in (".git", "__pycache__", "node_modules", ".pytest_cache")):
                    continue

                try:
                    rel_path = str(p.relative_to(self.workspace_root))
                    stat = p.stat()
                    is_dir = 1 if p.is_dir() else 0
                    ext = p.suffix.lstrip(".").lower() if not is_dir else ""
                    records.append((
                        rel_path,
                        p.name,
                        is_dir,
                        ext,
                        stat.st_size if not is_dir else 0,
                        stat.st_mtime,
                        time.time(),
                    ))
                    indexed_count += 1
                    if indexed_count >= max_files:
                        break
                except Exception:
                    continue

            # Batch insert/update SQLite
            await asyncio.to_thread(self._batch_upsert, records)
            logger.info(f"SearchIndexManager indexed {indexed_count} items in {(time.time() - t0):.2f}s.")
        except Exception as err:
            logger.error(f"Error during workspace indexing: {err}")
        finally:
            self._is_indexing = False

        return indexed_count

    def _batch_upsert(self, records: List[tuple]) -> None:
        """Batch insert or update index records."""
        if not records:
            return
        conn = sqlite3.connect(str(self.db_path))
        try:
            with conn:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO file_index (
                        path, filename, is_dir, extension, size_bytes, modified_at, indexed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    records,
                )
        finally:
            conn.close()

    def query_index(self, pattern: str, limit: int = 50) -> List[SearchMatch]:
        """Query index table by filename pattern or substring."""
        if not self.db_path.exists():
            return []

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            like_pattern = f"%{pattern.lower()}%"
            cursor.execute(
                """
                SELECT * FROM file_index
                WHERE LOWER(filename) LIKE ? OR LOWER(path) LIKE ?
                ORDER BY modified_at DESC
                LIMIT ?
                """,
                (like_pattern, like_pattern, limit),
            )
            rows = cursor.fetchall()
            matches = []
            for r in rows:
                full_p = str((self.workspace_root / r["path"]).resolve())
                t_type = SearchTargetType.FOLDER if r["is_dir"] else SearchTargetType.FILE
                matches.append(
                    SearchMatch(
                        path=full_p,
                        filename=r["filename"],
                        target_type=t_type,
                        score=0.8,
                        size_bytes=r["size_bytes"],
                        modified_at=r["modified_at"],
                        provider_name="index_manager",
                    )
                )
            return matches
        except Exception as e:
            logger.error(f"Error querying search index: {e}")
            return []
        finally:
            conn.close()
