"""
Base Service Protocol and Lifecycle Contracts for Vidya.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import datetime


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
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class BaseServiceProtocol(ABC):
    """
    Unified Lifecycle Contract for all services, providers, and capabilities.
    Every service must implement initialize(), health(), shutdown(), and cancel().
    """

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize resources, connections, or models."""
        pass

    @abstractmethod
    async def health(self) -> HealthStatus:
        """Return current health status and diagnostic details."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Gracefully release all resources and background tasks."""
        pass

    @abstractmethod
    async def cancel(self) -> None:
        """Immediately cancel any in-flight execution, stream, or task."""
        pass
