"""
Focused Metrics and Event Timeline Observability Engine.
"""

import logging
import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("vidya.core.observability")


@dataclass
class TimelineEvent:
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    stage: str = ""
    duration_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


class ObservabilityService:
    """
    Tracks focused MVP metrics:
    - wake_latency
    - stt_latency
    - ttft (Time-To-First-Token)
    - tts_first_audio (Time-To-First-Audio)
    - total_response_latency
    - cancellation_count
    Plus event timeline tracing.
    """

    def __init__(self) -> None:
        self._latencies: Dict[str, List[float]] = {
            "wake_latency": [],
            "stt_latency": [],
            "ttft": [],
            "tts_first_audio": [],
            "total_response_latency": [],
        }
        self._counters: Dict[str, int] = {
            "cancellation_count": 0,
        }
        self._timeline: List[TimelineEvent] = []

    def record_latency(self, metric_name: str, duration_ms: float) -> None:
        if metric_name not in self._latencies:
            self._latencies[metric_name] = []
        self._latencies[metric_name].append(duration_ms)
        logger.debug(f"[Metric] {metric_name}: {duration_ms:.2f}ms")

    def increment_counter(self, counter_name: str, amount: int = 1) -> None:
        if counter_name not in self._counters:
            self._counters[counter_name] = 0
        self._counters[counter_name] += amount
        logger.debug(f"[Counter] {counter_name}: {self._counters[counter_name]}")

    def log_timeline_event(self, stage: str, duration_ms: float = 0.0, details: Optional[Dict[str, Any]] = None) -> None:
        event = TimelineEvent(stage=stage, duration_ms=duration_ms, details=details or {})
        self._timeline.append(event)
        logger.debug(f"[Timeline] {stage} ({duration_ms:.2f}ms)")

    def get_metrics_summary(self) -> Dict[str, Any]:
        summary: Dict[str, Any] = {}
        for name, values in self._latencies.items():
            if values:
                summary[name] = {
                    "count": len(values),
                    "latest_ms": values[-1],
                    "avg_ms": sum(values) / len(values),
                    "min_ms": min(values),
                    "max_ms": max(values),
                }
            else:
                summary[name] = {"count": 0, "latest_ms": 0.0, "avg_ms": 0.0}
        
        summary["counters"] = self._counters.copy()
        return summary

    def get_timeline(self) -> List[TimelineEvent]:
        return self._timeline.copy()

    def reset(self) -> None:
        for name in self._latencies:
            self._latencies[name] = []
        for name in self._counters:
            self._counters[name] = 0
        self._timeline.clear()
