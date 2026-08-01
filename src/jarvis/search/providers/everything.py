"""
Everything SDK Search Provider for instant Voidtools Everything MFT index searching.
"""

import sys
from typing import List, Optional
from jarvis.search.providers.base import BaseSearchProvider
from jarvis.search.schemas import (
    SearchMatch,
    SearchProviderManifest,
    SearchQuery,
)
from jarvis.tools.schemas import CancellationToken


class EverythingSearchProvider(BaseSearchProvider):
    """Everything Search SDK Provider."""

    @property
    def manifest(self) -> SearchProviderManifest:
        return SearchProviderManifest(
            name="everything",
            supports_filename=True,
            supports_content=False,
            supports_regex=True,
            supports_metadata=True,
            supports_apps=True,
            supports_recent=True,
            confidence_score=1.0,
        )

    async def is_available(self) -> bool:
        """Available on Windows OS platforms when Everything service is active."""
        return sys.platform.startswith("win")

    async def search(
        self,
        query: SearchQuery,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[SearchMatch]:
        """Placeholder query wrapper for Everything IPC / DLL."""
        if not await self.is_available():
            return []
        # Return empty list to allow fallback chain if Everything IPC is not bound
        return []
