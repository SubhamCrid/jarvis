"""
Strongly-typed value object IDs for jarvis.internet platform.
Eliminates accidental string ID mix-ups across providers, jobs, executions, replays, sessions, and downloads.
"""

import uuid
from pydantic import BaseModel, Field


class ProviderId(BaseModel):
    value: str

    def __str__(self) -> str:
        return self.value


class JobId(BaseModel):
    value: str = Field(default_factory=lambda: f"job-{uuid.uuid4().hex[:8]}")

    def __str__(self) -> str:
        return self.value


class ExecutionId(BaseModel):
    value: str = Field(default_factory=lambda: f"exec-{uuid.uuid4().hex[:8]}")

    def __str__(self) -> str:
        return self.value


class ReplayId(BaseModel):
    value: str = Field(default_factory=lambda: f"replay-{uuid.uuid4().hex[:8]}")

    def __str__(self) -> str:
        return self.value


class SessionId(BaseModel):
    value: str = Field(default_factory=lambda: f"sess-{uuid.uuid4().hex[:8]}")

    def __str__(self) -> str:
        return self.value


class DownloadId(BaseModel):
    value: str = Field(default_factory=lambda: f"dl-{uuid.uuid4().hex[:8]}")

    def __str__(self) -> str:
        return self.value
