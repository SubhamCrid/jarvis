"""
InternetTelemetryService for asynchronous, low-overhead observability collection.
"""

from typing import Any, Dict, List, Optional
from jarvis.internet.telemetry.sinks import MetricSink, NullSink


class InternetTelemetryService:
    """Asynchronous metric collector dispatching to pluggable MetricSink instances."""

    def __init__(self, sinks: Optional[List[MetricSink]] = None) -> None:
        self.sinks = sinks or [NullSink()]

    def add_sink(self, sink: MetricSink) -> None:
        self.sinks.append(sink)

    async def emit_metric(self, name: str, value: float, tags: Optional[Dict[str, Any]] = None) -> None:
        """Record metric sample across all registered sinks asynchronously."""
        tag_map = tags or {}
        for sink in self.sinks:
            try:
                await sink.record_metric(name, value, tag_map)
            except Exception:
                pass
