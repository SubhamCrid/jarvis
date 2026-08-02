"""
ProviderHealthScorer providing continuous health scoring (0.0 to 1.0) with exponential time decay and rolling statistics.
Weights loaded dynamically from InternetConfig.health_weights.
"""

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from jarvis.internet.config import HealthWeightsConfig

logger = logging.getLogger("jarvis.internet.health.scorer")


@dataclass
class CallRecord:
    timestamp: float
    success: bool
    latency_ms: float


@dataclass
class ProviderRollingStats:
    provider_name: str
    records: List[CallRecord] = field(default_factory=list)
    max_history: int = 50

    def add_call(self, success: bool, latency_ms: float) -> None:
        self.records.append(CallRecord(timestamp=time.time(), success=success, latency_ms=latency_ms))
        if len(self.records) > self.max_history:
            self.records.pop(0)

    @property
    def success_rate(self) -> float:
        if not self.records:
            return 1.0
        successes = sum(1 for r in self.records if r.success)
        return successes / len(self.records)

    @property
    def avg_latency_ms(self) -> float:
        if not self.records:
            return 0.0
        return sum(r.latency_ms for r in self.records) / len(self.records)


class ProviderHealthScorer:
    """Computes continuous provider health score S in [0.0, 1.0] with configurable weights and time decay."""

    def __init__(self, weights: Optional[HealthWeightsConfig] = None) -> None:
        self.weights = weights or HealthWeightsConfig()
        self.stats: Dict[str, ProviderRollingStats] = {}

    def record_call(self, provider_name: str, success: bool, latency_ms: float = 0.0) -> None:
        if provider_name not in self.stats:
            self.stats[provider_name] = ProviderRollingStats(provider_name=provider_name)
        self.stats[provider_name].add_call(success, latency_ms)

    def compute_score(self, provider_name: str) -> float:
        """Compute continuous score for a provider based on rolling stats and exponential time decay."""
        if provider_name not in self.stats or not self.stats[provider_name].records:
            return 1.0  # Default un-called provider score

        st = self.stats[provider_name]
        now = time.time()

        # 1. Success rate score
        success_score = st.success_rate

        # 2. Latency score (normalized: 100ms -> 1.0, 5000ms -> 0.0)
        avg_lat = st.avg_latency_ms
        latency_score = max(0.0, min(1.0, 1.0 - (avg_lat / 5000.0)))

        # 3. Reliability score (penalty for recent consecutive failures)
        recent_failures = 0
        for r in reversed(st.records):
            if not r.success:
                recent_failures += 1
            else:
                break
        reliability_score = max(0.0, 1.0 - (recent_failures * 0.25))

        # 4. Freshness score with time decay (half-life of 300 seconds)
        last_call_t = st.records[-1].timestamp
        elapsed_sec = now - last_call_t
        freshness_score = math.exp(-0.693 * elapsed_sec / 300.0)

        # Composite score calculation using configurable weights
        raw_score = (
            (self.weights.success_weight * success_score)
            + (self.weights.latency_weight * latency_score)
            + (self.weights.reliability_weight * reliability_score)
            + (self.weights.freshness_weight * freshness_score)
        )

        return round(max(0.0, min(1.0, raw_score)), 3)
