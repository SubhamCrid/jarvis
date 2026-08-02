"""
Base service protocols and lifecycle contracts for the Jarvis framework.
"""

import asyncio
import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class CancellationToken:
    """Thread-safe and async-safe cancellation token wrapper."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        """Trigger cancellation signal."""
        self._event.set()

    def is_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        return self._event.is_set()

    async def wait(self) -> None:
        """Wait until cancellation is requested."""
        await self._event.wait()


class ServiceStatus(str, Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class HealthStatus:
    status: ServiceStatus
    message: str = "Healthy"
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


class BaseServiceProtocol(ABC):
    """
    Abstract base protocol specifying the lifecycle operations required
    by all services, capability managers, and hardware providers.
    """

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize underlying dependencies, connections, and hardware resources."""
        pass

    @abstractmethod
    async def health(self) -> HealthStatus:
        """Return diagnostic health metrics and component operational state."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Gracefully close background tasks and release hardware/network resources."""
        pass

    @abstractmethod
    async def cancel(self) -> None:
        """Cancel active in-flight executions, streams, or asynchronous tasks immediately."""
        pass
