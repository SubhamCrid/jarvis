"""
ToolTracer module for auditing, logging, and telemetry event collection.
"""

import logging
import time
from typing import Any, Dict, List, Optional
from jarvis.tools.redactor import OutputRedactor
from jarvis.tools.schemas import AuditEvent, ToolCall, ToolResult

logger = logging.getLogger("jarvis.tools.tracer")


class ToolTracer:
    """Collects, redacts, and exposes audit event traces for tool execution calls."""

    def __init__(self, max_in_memory: int = 500) -> None:
        self._max_in_memory = max_in_memory
        self._traces: List[AuditEvent] = []

    def record_event(
        self,
        call: ToolCall,
        policy_decision: Dict[str, Any],
        start_time: float,
        result: ToolResult,
    ) -> AuditEvent:
        """Create, record, and log a redacted AuditEvent."""
        duration_ms = (time.time() - start_time) * 1000.0

        raw_summary = (
            f"Result: success={result.success}"
            + (f", data={result.data}" if result.data is not None else "")
            + (f", error={result.error.message}" if result.error else "")
        )
        redacted_summary = OutputRedactor.redact_text(raw_summary)

        event = AuditEvent(
            call_id=call.call_id,
            tool_name=call.tool_name,
            session_id=call.session_id,
            task_id=call.task_id,
            policy_decision=OutputRedactor.redact_data(policy_decision),
            start_time=start_time,
            duration_ms=duration_ms,
            success=result.success,
            redacted_summary=redacted_summary,
        )

        self._traces.append(event)
        if len(self._traces) > self._max_in_memory:
            self._traces.pop(0)

        logger.info(
            f"ToolTrace [{call.tool_name}] call_id={call.call_id} "
            f"success={result.success} duration={duration_ms:.1f}ms"
        )
        return event

    def get_recent_traces(self, limit: int = 50) -> List[AuditEvent]:
        """Retrieve recent audit traces."""
        return self._traces[-limit:]

    def clear(self) -> None:
        """Clear trace buffer."""
        self._traces.clear()
