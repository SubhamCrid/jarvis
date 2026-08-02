"""
Typed schemas for persistent InternetJob management.
"""

import time
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from jarvis.internet.ids import JobId


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RECOVERABLE = "recoverable"


class RetryMetadata(BaseModel):
    retry_count: int = 0
    max_retries: int = 3
    last_retry_at: Optional[float] = None
    last_error: Optional[str] = None


class JobCheckpoint(BaseModel):
    version: int = 1
    step_id: str
    completed_steps: list[str] = Field(default_factory=list)
    checkpoint_data: Dict[str, Any] = Field(default_factory=dict)
    saved_at: float = Field(default_factory=time.time)


class InternetJob(BaseModel):
    """Durable job record managed by InternetJobManager."""

    version: int = 1
    job_id: str = Field(default_factory=lambda: JobId().value)
    query: str
    session_id: str = "default"
    status: JobState = JobState.QUEUED
    progress: float = 0.0
    strategy_name: str = "DirectSearch"
    plan_json: str = ""
    checkpoint: Optional[JobCheckpoint] = None
    retry_info: RetryMetadata = Field(default_factory=RetryMetadata)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)
