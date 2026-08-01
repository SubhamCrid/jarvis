"""
Typed contract schemas for Agent Runtime Platform (jarvis.runtime).
"""

import time, uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ExecutionState(str, Enum):
    CREATED = "created"
    PLANNED = "planned"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_EVENT = "waiting_event"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"


class RetryPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_retries: int = 3
    delay_seconds: float = 1.0
    backoff_factor: float = 2.0


class PlanStep(BaseModel):
    model_config = ConfigDict(frozen=False)

    step_id: str = Field(default_factory=lambda: f"step-{uuid.uuid4().hex[:8]}")
    name: str
    capability_name: str
    action_name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    requires_approval: bool = False
    retry_policy: Optional[RetryPolicy] = None
    state: ExecutionState = ExecutionState.CREATED
    result: Optional[Any] = None
    error: Optional[str] = None


class Plan(BaseModel):
    model_config = ConfigDict(frozen=False)

    plan_id: str = Field(default_factory=lambda: f"plan-{uuid.uuid4().hex[:8]}")
    goal_id: str
    steps: List[PlanStep] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class Goal(BaseModel):
    model_config = ConfigDict(frozen=False)

    goal_id: str = Field(default_factory=lambda: f"goal-{uuid.uuid4().hex[:8]}")
    description: str
    session_id: str = "default_session"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    state: ExecutionState = ExecutionState.CREATED
    created_at: float = Field(default_factory=time.time)


class Task(BaseModel):
    model_config = ConfigDict(frozen=False)

    task_id: str = Field(default_factory=lambda: f"task-{uuid.uuid4().hex[:8]}")
    goal_id: Optional[str] = None
    session_id: str = "default_session"
    task_type: str = "general"
    payload: Dict[str, Any] = Field(default_factory=dict)
    state: ExecutionState = ExecutionState.CREATED
    created_at: float = Field(default_factory=time.time)


class Checkpoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    checkpoint_id: str = Field(default_factory=lambda: f"chk-{uuid.uuid4().hex[:8]}")
    goal_id: str
    plan_id: str
    completed_step_ids: List[str] = Field(default_factory=list)
    step_results: Dict[str, Any] = Field(default_factory=dict)
    state: ExecutionState = ExecutionState.PAUSED
    timestamp: float = Field(default_factory=time.time)


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(frozen=False)

    request_id: str = Field(default_factory=lambda: f"appr-{uuid.uuid4().hex[:8]}")
    goal_id: str
    step_id: str
    capability_name: str
    action_name: str
    reason: str
    approved: Optional[bool] = None
    timestamp: float = Field(default_factory=time.time)


class StepResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    step_id: str
    success: bool
    output: Any = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0

