"""
Immutable versioned domain events for Agent Runtime Platform.
"""

from dataclasses import dataclass, field
import datetime
from typing import Any, Dict, Optional


def current_iso_timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@dataclass(frozen=True)
class GoalCreated:
    event_version: str = "1.0"
    goal_id: str = ""
    description: str = ""
    session_id: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class TaskQueued:
    event_version: str = "1.0"
    task_id: str = ""
    task_type: str = ""
    session_id: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class PlanCreated:
    event_version: str = "1.0"
    plan_id: str = ""
    goal_id: str = ""
    total_steps: int = 0
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class StepStarted:
    event_version: str = "1.0"
    plan_id: str = ""
    step_id: str = ""
    capability_name: str = ""
    action_name: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class StepCompleted:
    event_version: str = "1.0"
    plan_id: str = ""
    step_id: str = ""
    success: bool = True
    result: Any = None
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class ApprovalRequested:
    event_version: str = "1.0"
    request_id: str = ""
    goal_id: str = ""
    step_id: str = ""
    reason: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class ApprovalGranted:
    event_version: str = "1.0"
    request_id: str = ""
    approved: bool = True
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class RuntimePaused:
    event_version: str = "1.0"
    goal_id: str = ""
    reason: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class RuntimeResumed:
    event_version: str = "1.0"
    goal_id: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class RuntimeCancelled:
    event_version: str = "1.0"
    goal_id: str = ""
    reason: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class WorkflowCompleted:
    event_version: str = "1.0"
    goal_id: str = ""
    plan_id: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class WorkflowFailed:
    event_version: str = "1.0"
    goal_id: str = ""
    plan_id: str = ""
    error: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)
