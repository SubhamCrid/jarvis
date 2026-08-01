"""
Telemetry and performance metrics collector for Search Platform.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class SearchMetricsSummary:
    total_searches: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_ratio: float = 0.0
    cancel_count: int = 0
    fallback_count: int = 0
    avg_search_time_ms: float = 0.0
    provider_latencies: Dict[str, float] = field(default_factory=dict)


class SearchMetricsCollector:
    """Collects latencies, cache hit ratios, cancellation counts, and fallback statistics."""

    def __init__(self) -> None:
        self.total_searches = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.cancel_count = 0
        self.fallback_count = 0
        self._search_durations: List[float] = []
        self._provider_durations: Dict[str, List[float]] = {}

    def record_search(self, duration_ms: float, cached: bool, cancelled: bool = False, fallback: bool = False) -> None:
        """Record a completed search operation metrics."""
        self.total_searches += 1
        if cached:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

        if cancelled:
            self.cancel_count += 1

        if fallback:
            self.fallback_count += 1

        self._search_durations.append(duration_ms)
        if len(self._search_durations) > 1000:
            self._search_durations.pop(0)

    def record_provider_latency(self, provider_name: str, duration_ms: float) -> None:
        """Record latency for a specific provider."""
        if provider_name not in self._provider_durations:
            self._provider_durations[provider_name] = []
        self._provider_durations[provider_name].append(duration_ms)
        if len(self._provider_durations[provider_name]) > 500:
            self._provider_durations[provider_name].pop(0)

    def get_summary(self) -> SearchMetricsSummary:
        """Compute and return operational metrics summary."""
        total_cache_queries = self.cache_hits + self.cache_misses
        hit_ratio = (self.cache_hits / total_cache_queries) if total_cache_queries > 0 else 0.0
        avg_search_ms = (sum(self._search_durations) / len(self._search_durations)) if self._search_durations else 0.0

        avg_provider_latencies = {}
        for p_name, dur_list in self._provider_durations.items():
            avg_provider_latencies[p_name] = (sum(dur_list) / len(dur_list)) if dur_list else 0.0

        return SearchMetricsSummary(
            total_searches=self.total_searches,
            cache_hits=self.cache_hits,
            cache_misses=self.cache_misses,
            cache_hit_ratio=hit_ratio,
            cancel_count=self.cancel_count,
            fallback_count=self.fallback_count,
            avg_search_time_ms=avg_search_ms,
            provider_latencies=avg_provider_latencies,
        )
