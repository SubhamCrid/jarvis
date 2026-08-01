"""
Native Filesystem Search Provider with fnmatch and difflib fuzzy matching.
100% reliable fallback provider.
"""

import asyncio
import difflib
import fnmatch
from pathlib import Path
from typing import List, Optional
from jarvis.search.providers.base import BaseSearchProvider
from jarvis.search.schemas import (
    SearchMatch,
    SearchProviderManifest,
    SearchQuery,
    SearchTargetType,
)
from jarvis.tools.schemas import CancellationToken


class FilesystemSearchProvider(BaseSearchProvider):
    """Native Python filesystem traversal provider."""

    @property
    def manifest(self) -> SearchProviderManifest:
        return SearchProviderManifest(
            name="filesystem",
            supports_filename=True,
            supports_content=False,
            supports_regex=False,
            supports_metadata=True,
            supports_apps=False,
            supports_recent=True,
            confidence_score=0.7,
        )

    async def is_available(self) -> bool:
        return True  # Always available

    async def search(
        self,
        query: SearchQuery,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[SearchMatch]:
        """Traverse directory tree asynchronously and collect candidate matches."""
        target_root = Path(query.search_root).resolve() if query.search_root else Path.cwd().resolve()
        if not target_root.exists():
            return []

        pattern = (query.clean_query or query.raw_query).strip()
        matches: List[SearchMatch] = []

        def _scan_directory():
            count = 0
            for item in target_root.rglob("*"):
                if cancellation_token and cancellation_token.is_cancelled():
                    break

                # Ignore build/temp dirs
                if any(ignored in item.parts for ignored in (".git", "__pycache__", "node_modules", ".pytest_cache")):
                    continue

                fname = item.name
                fname_lower = fname.lower()
                pattern_lower = pattern.lower()

                is_match = False
                base_score = 0.5

                if not pattern_lower:
                    is_match = True
                elif fnmatch.fnmatch(fname_lower, f"*{pattern_lower}*"):
                    is_match = True
                    base_score = 0.8
                elif query.fuzzy:
                    ratio = difflib.SequenceMatcher(None, pattern_lower, fname_lower).ratio()
                    if ratio >= 0.6:
                        is_match = True
                        base_score = ratio

                if is_match:
                    try:
                        stat = item.stat()
                        t_type = SearchTargetType.FOLDER if item.is_dir() else SearchTargetType.FILE
                        matches.append(
                            SearchMatch(
                                path=str(item),
                                filename=fname,
                                target_type=t_type,
                                score=base_score,
                                size_bytes=stat.st_size if item.is_file() else 0,
                                modified_at=stat.st_mtime,
                                provider_name="filesystem",
                            )
                        )
                        count += 1
                        if count >= query.max_results * 2:  # Over-fetch for ranker filtering
                            break
                    except Exception:
                        continue

        await asyncio.to_thread(_scan_directory)
        return matches
