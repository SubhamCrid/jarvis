"""
BaseInternetProvider contract.
All provider interfaces in jarvis.internet extend this root contract for consistent lifecycle management.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict
from jarvis.core.base import BaseServiceProtocol, HealthStatus, ServiceStatus


class ProviderType(str, Enum):
    SEARCH = "search"
    FETCH = "fetch"
    EXTRACTION = "extraction"
    BROWSER = "browser"
    RANKING = "ranking"
    CACHE = "cache"
    VERIFICATION = "verification"


class BaseInternetProvider(BaseServiceProtocol, ABC):
    """
    Root provider interface extending BaseServiceProtocol.
    Every provider must define provider_type, name, version, initialize, health, shutdown, cancel.
    """

    provider_type: ProviderType
    name: str
    version: str = "1.0.0"

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize provider resources."""
        pass

    @abstractmethod
    async def health(self) -> HealthStatus:
        """Return provider health status."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Cleanly shutdown provider resources."""
        pass

    @abstractmethod
    async def cancel(self) -> None:
        """Cancel active operations on voice barge-in."""
        pass
