"""
ExecutionContext and ContextExecutionState.
Immutable context container propagated through pipeline stages carrying execution_id, trace_id, and CancellationToken.
"""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from jarvis.internet.schemas import ExtractedDocument, FetchedPage, InternetDocument, SearchHit, VerificationResult
from jarvis.core.base import CancellationToken


class ContextExecutionState(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    SEARCHING = "searching"
    FETCHING = "fetching"
    EXTRACTING = "extracting"
    RANKING = "ranking"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass
class ExecutionContext:
    """Per-request immutable context container passed through pipeline stages."""

    query: str
    execution_id: str = field(default_factory=lambda: f"exec-{uuid.uuid4().hex[:8]}")
    trace_id: str = field(default_factory=lambda: f"trace-{uuid.uuid4().hex[:8]}")
    cancellation_token: CancellationToken = field(default_factory=CancellationToken)
    state: ContextExecutionState = ContextExecutionState.PENDING

    search_hits: List[SearchHit] = field(default_factory=list)
    fetched_pages: List[FetchedPage] = field(default_factory=list)
    extracted_documents: List[ExtractedDocument] = field(default_factory=list)
    verification_result: Optional[VerificationResult] = None
    final_documents: List[InternetDocument] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)
