"""
Abstract contract for search backend providers.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from jarvis.search.schemas import (
    SearchMatch,
    SearchProviderManifest,
    SearchQuery,
)
from jarvis.tools.schemas import CancellationToken


class BaseSearchProvider(ABC):
    """Abstract interface for all search backend providers."""

    @property
    @abstractmethod
    def manifest(self) -> SearchProviderManifest:
        """Return the capability manifest declared by this provider."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if this provider is available and ready on the system."""
        pass

    @abstractmethod
    async def search(
        self,
        query: SearchQuery,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[SearchMatch]:
        """Execute search query against backend and return candidate SearchMatch list."""
        pass
