"""
Typed contracts and schemas for Jarvis modular tool execution platform.
Fully model-agnostic and provider-agnostic.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field


class PermissionLevel(str, Enum):
    READ_ONLY = "read_only"
    WRITE = "write"
    RISKY = "risky"
    ADMIN = "admin"


class SideEffectLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DESTRUCTIVE = "destructive"


class StepState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class CancellationToken:
    """Thread-safe and async-safe cancellation token wrapper."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        """Trigger cancellation signal."""
        self._event.set()

    def is_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        return self._event.is_set()

    async def wait(self) -> None:
        """Wait until cancellation is requested."""
        await self._event.wait()


@dataclass
class ToolManifest:
    """Metadata manifest defining a tool's identity, version, and security properties."""

    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = "Jarvis Engine"
    permission_level: PermissionLevel = PermissionLevel.READ_ONLY
    idempotent: bool = True
    read_only: bool = True
    side_effect_level: SideEffectLevel = SideEffectLevel.NONE
    timeout_sec: float = 30.0


@dataclass
class ToolSpec:
    """Tool specification wrapping manifest, JSON schema parameters, and optional Pydantic input model."""

    manifest: ToolManifest
    parameters_schema: Dict[str, Any] = field(default_factory=dict)
    input_model: Optional[Type[BaseModel]] = None

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def version(self) -> str:
        return self.manifest.version

    @property
    def description(self) -> str:
        return self.manifest.description


class ToolError(BaseModel):
    """Standardized error contract for normalized tool failure reporting."""

    code: str
    message: str
    retryable: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """Invocation request representing an intent to execute a tool."""

    call_id: str = Field(default_factory=lambda: f"call-{uuid.uuid4().hex[:10]}")
    tool_name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    task_id: str = "default_task"
    session_id: str = "default_session"
    timestamp: float = Field(default_factory=time.time)


class ToolResult(BaseModel):
    """Execution output container for machine-readable results."""

    call_id: str
    tool_name: str
    success: bool
    data: Optional[Any] = None
    error: Optional[ToolError] = None
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def result(self) -> Optional[Any]:
        return self.data


class AuditEvent(BaseModel):
    """Structured audit trail record for security, debugging, and replay."""

    event_id: str = Field(default_factory=lambda: f"audit-{uuid.uuid4().hex[:10]}")
    call_id: str
    tool_name: str
    session_id: str
    task_id: str
    policy_decision: Dict[str, Any]
    start_time: float
    duration_ms: float
    success: bool
    redacted_summary: str


@dataclass
class ExecutionContext:
    """Runtime context passed into tool adapters during execution."""

    session_id: str
    task_id: str
    cancellation_token: CancellationToken = field(default_factory=CancellationToken)
    metadata: Dict[str, Any] = field(default_factory=dict)
