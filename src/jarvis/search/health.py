"""
Health monitoring service for Search Platform providers and engine.
"""

from typing import Any, Dict, List
from jarvis.search.metrics import SearchMetricsCollector


class SearchHealthCheck:
    """Monitors provider health, failure counts, and degraded engine state."""

    def __init__(self, metrics: SearchMetricsCollector) -> None:
        self.metrics = metrics
        self._provider_failures: Dict[str, int] = {}

    def record_provider_failure(self, provider_name: str) -> None:
        """Increment failure counter for a provider."""
        self._provider_failures[provider_name] = self._provider_failures.get(provider_name, 0) + 1

    def get_health_status(self, registered_providers: List[str], active_providers: List[str]) -> Dict[str, Any]:
        """Compute system health and status payload."""
        summary = self.metrics.get_summary()
        degraded = len(active_providers) < len(registered_providers) or summary.fallback_count > 5

        return {
            "status": "degraded" if degraded else "healthy",
            "registered_providers": registered_providers,
            "active_providers": active_providers,
            "failed_providers": list(self._provider_failures.keys()),
            "total_searches": summary.total_searches,
            "cache_hit_ratio": round(summary.cache_hit_ratio, 3),
            "avg_search_time_ms": round(summary.avg_search_time_ms, 2),
            "fallback_count": summary.fallback_count,
        }
