"""
Ripgrep Search Provider executing high-speed CLI content and regex search via `rg`.
"""

import asyncio
import shutil
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


class RipgrepSearchProvider(BaseSearchProvider):
    """Ripgrep provider for regex and file content searching."""

    @property
    def manifest(self) -> SearchProviderManifest:
        return SearchProviderManifest(
            name="ripgrep",
            supports_filename=True,
            supports_content=True,
            supports_regex=True,
            supports_metadata=False,
            supports_apps=False,
            supports_recent=False,
            confidence_score=0.9,
        )

    async def is_available(self) -> bool:
        """Check if `rg` CLI binary is installed and executable."""
        return shutil.which("rg") is not None

    async def search(
        self,
        query: SearchQuery,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[SearchMatch]:
        """Execute `rg` command asynchronously and parse match output."""
        if not await self.is_available():
            return []

        pattern = query.clean_query or query.raw_query
        if not pattern:
            return []

        target_dir = str(Path(query.search_root).resolve()) if query.search_root else str(Path.cwd().resolve())

        # Command arguments: --json or --line-number
        args = ["rg", "--ignore-case", "--max-count", str(query.max_results), "--line-number", pattern, target_dir]

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await proc.communicate()
            if not stdout:
                return []

            lines = stdout.decode("utf-8", errors="replace").splitlines()
            matches: List[SearchMatch] = []
            seen_paths = set()

            for line in lines:
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    file_path_str, line_num, snippet = parts[0], parts[1], parts[2]
                    p_obj = Path(file_path_str)
                    canon_path = str(p_obj.resolve())

                    if canon_path not in seen_paths:
                        seen_paths.add(canon_path)
                        matches.append(
                            SearchMatch(
                                path=canon_path,
                                filename=p_obj.name,
                                target_type=SearchTargetType.CONTENT,
                                score=0.85,
                                highlights=[f"L{line_num}: {snippet.strip()}"],
                                provider_name="ripgrep",
                            )
                        )

            return matches
        except Exception:
            return []
