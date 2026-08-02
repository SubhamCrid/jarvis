"""
Typed MessageBus events emitted by jarvis.internet platform.
Integrates with Jarvis core MessageBus for observability, telemetry, and UI status updates.
"""

import time
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class BaseInternetEvent(BaseModel):
    """Base event contract for internet platform telemetry events."""

    event_type: str
    execution_id: str
    timestamp: float = Field(default_factory=time.time)
    details: Dict[str, Any] = Field(default_factory=dict)


class SearchStartedEvent(BaseInternetEvent):
    event_type: str = "internet.search.started"
    query: str = ""
    strategy: str = ""


class SearchCompletedEvent(BaseInternetEvent):
    event_type: str = "internet.search.completed"
    query: str = ""
    hits_count: int = 0
    duration_ms: float = 0.0


class FetchStartedEvent(BaseInternetEvent):
    event_type: str = "internet.fetch.started"
    url: str = ""


class FetchFailedEvent(BaseInternetEvent):
    event_type: str = "internet.fetch.failed"
    url: str = ""
    error_message: str = ""


class ExtractionFinishedEvent(BaseInternetEvent):
    event_type: str = "internet.extraction.finished"
    url: str = ""
    token_count: int = 0


class VerificationFinishedEvent(BaseInternetEvent):
    event_type: str = "internet.verification.finished"
    verified: bool = True
    confidence_score: float = 1.0


class BrowserOpenedEvent(BaseInternetEvent):
    event_type: str = "internet.browser.opened"
    engine: str = "camoufox"
    session_type: str = "ephemeral"


class BrowserClosedEvent(BaseInternetEvent):
    event_type: str = "internet.browser.closed"
    engine: str = "camoufox"


class BrowserHealthDegradedEvent(BaseInternetEvent):
    event_type: str = "internet.browser.health_degraded"
    state: str = "DEGRADED"
    reason: str = ""


class ProviderChangedEvent(BaseInternetEvent):
    event_type: str = "internet.provider.changed"
    provider_type: str = ""
    new_provider: str = ""


class ProviderDegradedEvent(BaseInternetEvent):
    event_type: str = "internet.provider.degraded"
    provider_name: str = ""
    consecutive_failures: int = 0


class CacheHitEvent(BaseInternetEvent):
    event_type: str = "internet.cache.hit"
    key: str = ""
    cache_type: str = "pipeline"


class InternetStateChangedEvent(BaseInternetEvent):
    event_type: str = "internet.state.changed"
    old_state: str = ""
    new_state: str = ""


class PipelineStartedEvent(BaseInternetEvent):
    event_type: str = "internet.pipeline.started"
    query: str = ""


class StageStartedEvent(BaseInternetEvent):
    event_type: str = "internet.stage.started"
    stage_name: str = ""


class StageFinishedEvent(BaseInternetEvent):
    event_type: str = "internet.stage.finished"
    stage_name: str = ""
    duration_ms: float = 0.0


class StageFailedEvent(BaseInternetEvent):
    event_type: str = "internet.stage.failed"
    stage_name: str = ""
    error_message: str = ""


class PipelineCompletedEvent(BaseInternetEvent):
    event_type: str = "internet.pipeline.completed"
    documents_count: int = 0
    duration_ms: float = 0.0


class JobRecoverableEvent(BaseInternetEvent):
    event_type: str = "internet.job.recoverable"
    job_id: str = ""

