"""
Immutable domain events, health checker, and tracing for Memory Platform.
"""

from dataclasses import dataclass, field
import datetime
from typing import Any, Dict
from jarvis.core.base import HealthStatus, ServiceStatus


def current_iso_timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@dataclass(frozen=True)
class MemoryStoredEvent:
    event_version: str = "1.0"
    memory_id: str = ""
    memory_type: str = ""
    key: str = ""
    session_id: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class MemoryQueriedEvent:
    event_version: str = "1.0"
    query_text: str = ""
    results_count: int = 0
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class MemoryDeletedEvent:
    event_version: str = "1.0"
    memory_id: str = ""
    memory_type: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)


class MemoryHealthChecker:

    def check_health(self, active_providers_count: int) -> HealthStatus:
        return HealthStatus(
            status=ServiceStatus.RUNNING,
            message="Memory Platform operational",
            details={"active_memory_providers": active_providers_count},
        )


class MemoryTracer:

    def trace_query(self, query: str, total_found: int) -> Dict[str, Any]:
        return {"query": query, "total_found": total_found, "traced": True}
