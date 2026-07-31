"""
Unit tests for ObservabilityService.
"""

from vidya.core.observability import ObservabilityService


def test_observability_metrics(observability: ObservabilityService):
    observability.record_latency("stt_latency", 150.0)
    observability.record_latency("stt_latency", 250.0)
    observability.increment_counter("cancellation_count")
    observability.log_timeline_event("STT_START")

    summary = observability.get_metrics_summary()
    assert summary["stt_latency"]["count"] == 2
    assert summary["stt_latency"]["avg_ms"] == 200.0
    assert summary["counters"]["cancellation_count"] == 1

    timeline = observability.get_timeline()
    assert len(timeline) == 1
    assert timeline[0].stage == "STT_START"
