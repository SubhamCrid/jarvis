"""
Windows Search Index Provider interacting with the native Windows Desktop Indexer.
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


class WindowsIndexSearchProvider(BaseSearchProvider):
    """Windows Search Indexer Provider."""

    @property
    def manifest(self) -> SearchProviderManifest:
        return SearchProviderManifest(
            name="windows_index",
            supports_filename=True,
            supports_content=True,
            supports_regex=False,
            supports_metadata=True,
            supports_apps=True,
            supports_recent=True,
            confidence_score=0.95,
        )

    async def is_available(self) -> bool:
        """Available on Windows OS platforms."""
        return sys.platform.startswith("win")

    async def search(
        self,
        query: SearchQuery,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[SearchMatch]:
        """Placeholder query wrapper for Windows Search OLE DB / PowerShell indexer."""
        if not await self.is_available():
            return []
        # Return empty array to trigger fallback if indexer is inactive
        return []
