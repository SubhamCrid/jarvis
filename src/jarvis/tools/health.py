"""
Telemetry and health monitoring for Jarvis tool execution platform.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List
from jarvis.tools.concurrency import ResourceLockManager


@dataclass
class ToolHealthMetrics:
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    cancelled_calls: int = 0
    active_locks: int = 0
    error_rate: float = 0.0
    degraded: bool = False
    registered_tools: List[str] = field(default_factory=list)


class ToolHealthCheck:
    """Monitors failure rates, active lock contention, and system degraded status."""

    def __init__(self, lock_manager: ResourceLockManager) -> None:
        self.lock_manager = lock_manager
        self._total_calls = 0
        self._success_calls = 0
        self._failed_calls = 0
        self._cancelled_calls = 0

    def record_execution(self, success: bool, cancelled: bool = False) -> None:
        """Record an execution outcome."""
        self._total_calls += 1
        if cancelled:
            self._cancelled_calls += 1
            self._failed_calls += 1
        elif success:
            self._success_calls += 1
        else:
            self._failed_calls += 1

    def get_health_metrics(self, registered_tools: List[str]) -> ToolHealthMetrics:
        """Calculate and return operational health metrics."""
        error_rate = (self._failed_calls / self._total_calls) if self._total_calls > 0 else 0.0
        active_locks = self.lock_manager.active_locks_count()
        degraded = error_rate > 0.3 if self._total_calls >= 10 else False

        return ToolHealthMetrics(
            total_calls=self._total_calls,
            successful_calls=self._success_calls,
            failed_calls=self._failed_calls,
            cancelled_calls=self._cancelled_calls,
            active_locks=active_locks,
            error_rate=error_rate,
            degraded=degraded,
            registered_tools=registered_tools,
        )
