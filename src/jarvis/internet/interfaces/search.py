"""
SearchProvider contract.
Interface for search engine provider implementations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from jarvis.core.base import CancellationToken
from jarvis.internet.interfaces.base import BaseInternetProvider, ProviderType
from jarvis.internet.schemas import SearchHit


class SearchProvider(BaseInternetProvider, ABC):
    """Abstract interface for web search engine providers."""

    provider_type = ProviderType.SEARCH

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 5,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[SearchHit]:
        """Execute search query and return typed SearchHit objects."""
        pass
