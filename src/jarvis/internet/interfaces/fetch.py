"""
FetchProvider contract.
Interface for raw HTTP page fetching implementations.
"""

from abc import ABC, abstractmethod
from typing import Optional
from jarvis.core.base import CancellationToken
from jarvis.internet.interfaces.base import BaseInternetProvider, ProviderType
from jarvis.internet.schemas import FetchedPage


class FetchProvider(BaseInternetProvider, ABC):
    """Abstract interface for HTTP page fetchers."""

    provider_type = ProviderType.FETCH

    @abstractmethod
    async def fetch(
        self,
        url: str,
        timeout_sec: float = 10.0,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> FetchedPage:
        """Fetch raw HTML/text from URL."""
        pass
