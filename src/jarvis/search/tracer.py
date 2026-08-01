"""
SearchTracer module for structured search telemetry logging.
"""

import logging
import time
from typing import Any, Dict, List
from jarvis.search.schemas import SearchMatch, SearchQuery, SearchResponse

logger = logging.getLogger("jarvis.search.tracer")


class SearchTracer:
    """Logs structured telemetry events for search queries and responses."""

    def __init__(self, max_in_memory: int = 200) -> None:
        self._max_in_memory = max_in_memory
        self._traces: List[Dict[str, Any]] = []

    def record_trace(self, query: SearchQuery, response: SearchResponse) -> None:
        """Record and log search trace."""
        trace_entry = {
            "timestamp": time.time(),
            "raw_query": query.raw_query,
            "target_type": query.target_type.value,
            "matches_count": len(response.matches),
            "providers_used": response.providers_used,
            "execution_time_ms": response.execution_time_ms,
            "cached": response.cached,
        }

        self._traces.append(trace_entry)
        if len(self._traces) > self._max_in_memory:
            self._traces.pop(0)

        logger.info(
            f"SearchTrace [{query.raw_query}] matches={len(response.matches)} "
            f"providers={response.providers_used} duration={response.execution_time_ms:.1f}ms cached={response.cached}"
        )

    def get_recent_traces(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent search trace entries."""
        return self._traces[-limit:]
