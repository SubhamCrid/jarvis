"""
ProviderHealthMonitor and ProviderCircuitBreaker.
Tracks provider status, error rate, latency, and circuit-breaker states (CLOSED -> OPEN -> HALF_OPEN).
"""

import logging
import time
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger("jarvis.internet.health")


class CircuitState(str, Enum):
    CLOSED = "closed"        # Healthy, normal operation
    OPEN = "open"            # Failing, blocking requests
    HALF_OPEN = "half_open"  # Probe request to test recovery


class ProviderCircuitBreaker:
    """3-State Circuit Breaker pattern for isolated provider fault containment."""

    def __init__(
        self,
        provider_name: str,
        failure_threshold: int = 3,
        cooldown_sec: float = 60.0,
    ) -> None:
        self.provider_name = provider_name
        self.failure_threshold = failure_threshold
        self.cooldown_sec = cooldown_sec

        self.state: CircuitState = CircuitState.CLOSED
        self.consecutive_failures: int = 0
        self.last_failure_time: float = 0.0
        self.last_success_time: float = 0.0
        self.total_calls: int = 0
        self.total_errors: int = 0
        self.last_latency_ms: float = 0.0

    def allow_request(self) -> bool:
        """Check if request is permitted under current circuit state."""
        now = time.time()
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if (now - self.last_failure_time) >= self.cooldown_sec:
                logger.info(f"CircuitBreaker [{self.provider_name}] cooling period expired; transitioning to HALF_OPEN probe.")
                self.state = CircuitState.HALF_OPEN
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return True

        return False

    def record_success(self, latency_ms: float = 0.0) -> None:
        """Record successful call and reset circuit breaker if half-open."""
        self.total_calls += 1
        self.last_success_time = time.time()
        self.last_latency_ms = latency_ms
        self.consecutive_failures = 0

        if self.state in (CircuitState.OPEN, CircuitState.HALF_OPEN):
            logger.info(f"CircuitBreaker [{self.provider_name}] recovered; resetting state to CLOSED.")
            self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record failed call and trip circuit breaker if threshold reached."""
        self.total_calls += 1
        self.total_errors += 1
        self.consecutive_failures += 1
        self.last_failure_time = time.time()

        if self.consecutive_failures >= self.failure_threshold:
            if self.state != CircuitState.OPEN:
                logger.warning(
                    f"CircuitBreaker [{self.provider_name}] tripped! "
                    f"{self.consecutive_failures} consecutive failures. Transitioning to OPEN for {self.cooldown_sec}s."
                )
                self.state = CircuitState.OPEN


class ProviderHealthMonitor:
    """Registry-level health monitor supervising all active internet providers."""

    def __init__(self) -> None:
        self.breakers: Dict[str, ProviderCircuitBreaker] = {}

    def get_breaker(self, provider_name: str) -> ProviderCircuitBreaker:
        if provider_name not in self.breakers:
            self.breakers[provider_name] = ProviderCircuitBreaker(provider_name=provider_name)
        return self.breakers[provider_name]

    def allow_request(self, provider_name: str) -> bool:
        return self.get_breaker(provider_name).allow_request()

    def record_success(self, provider_name: str, latency_ms: float = 0.0) -> None:
        self.get_breaker(provider_name).record_success(latency_ms)

    def record_failure(self, provider_name: str) -> None:
        self.get_breaker(provider_name).record_failure()

    def get_provider_health(self, provider_name: str) -> dict:
        breaker = self.get_breaker(provider_name)
        return {
            "status": breaker.state.value,
            "consecutive_failures": breaker.consecutive_failures,
            "total_calls": breaker.total_calls,
            "total_errors": breaker.total_errors,
            "last_latency_ms": breaker.last_latency_ms,
        }
