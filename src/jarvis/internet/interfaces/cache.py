"""
CacheProvider contract.
Interface for caching pages, search results, and pipeline outputs.
"""

from abc import ABC, abstractmethod
from typing import Optional
from jarvis.internet.interfaces.base import BaseInternetProvider, ProviderType
from jarvis.internet.schemas import InternetResult


class CacheProvider(BaseInternetProvider, ABC):
    """Abstract interface for internet caching providers."""

    provider_type = ProviderType.CACHE

    @abstractmethod
    async def get_result(self, key: str) -> Optional[InternetResult]:
        """Retrieve cached InternetResult if available and valid."""
        pass

    @abstractmethod
    async def set_result(self, key: str, result: InternetResult, ttl_sec: int = 86400) -> None:
        """Store InternetResult in cache with TTL."""
        pass
