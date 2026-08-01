"""
SearchFilterEngine enforcing size, date, extension, and sandbox boundary filtering.
"""

from pathlib import Path
from typing import List, Optional
from jarvis.search.sandbox import SearchRootSandbox
from jarvis.search.schemas import SearchMatch, SearchQuery, SearchTargetType


class SearchFilterEngine:
    """Filters candidate search matches according to query filters and security sandbox."""

    def __init__(self, sandbox: Optional[SearchRootSandbox] = None) -> None:
        self.sandbox = sandbox

    def filter_matches(self, query: SearchQuery, matches: List[SearchMatch]) -> List[SearchMatch]:
        """Apply all query and security filters to candidate matches."""
        filtered = []

        for match in matches:
            # 1. Root Sandbox Confinement Check
            if self.sandbox and not self.sandbox.is_within_root(match.path):
                continue

            path_obj = Path(match.path)

            # 2. Target type filter (file vs folder)
            if query.target_type == SearchTargetType.FILE and match.target_type == SearchTargetType.FOLDER:
                continue
            if query.target_type == SearchTargetType.FOLDER and match.target_type == SearchTargetType.FILE:
                continue

            # 3. Extension filter
            if query.extensions:
                ext = path_obj.suffix.lstrip(".").lower()
                if ext not in [e.lower() for e in query.extensions]:
                    continue

            # 4. Size bounds filter
            if query.min_size_bytes is not None and match.size_bytes < query.min_size_bytes:
                continue
            if query.max_size_bytes is not None and match.size_bytes > query.max_size_bytes:
                continue

            # 5. Modification date bounds
            if query.modified_after is not None and match.modified_at < query.modified_after:
                continue
            if query.modified_before is not None and match.modified_at > query.modified_before:
                continue

            # 6. Hidden files check (e.g. skip .git, .pytest_cache unless requested)
            if any(part.startswith(".") for part in path_obj.parts if part not in (".", "..")):
                if not (query.clean_query and query.clean_query.startswith(".")):
                    continue

            filtered.append(match)

        return filtered
