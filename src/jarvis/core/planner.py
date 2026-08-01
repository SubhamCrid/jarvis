"""
Planner abstraction and step resolution logic for assistant execution plans.
Supports explicit step state tracking, dependency ordering, and tool call intent resolution.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import uuid

from jarvis.core.task_manager import Task
from jarvis.tools.schemas import StepState


@dataclass
class PlanStep:
    step_id: str
    capability_name: str
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    state: StepState = StepState.PENDING
    depends_on: List[str] = field(default_factory=list)
    result_data: Optional[Any] = None


@dataclass
class Plan:
    plan_id: str
    task_id: str
    steps: List[PlanStep] = field(default_factory=list)


class PlannerProtocol(ABC):
    """Abstract contract for mapping tasks into executable plan steps."""

    @abstractmethod
    def create_plan(self, task: Task) -> Plan:
        """Construct a multi-step execution plan for the target task."""
        pass


class SimplePlanner(PlannerProtocol):
    """
    Default planner mapping incoming tasks into executable plan steps,
    supporting voice interactions, capability actions, and structured tool calls.
    """

    def create_plan(self, task: Task) -> Plan:
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"

        if task.task_type == "voice_interaction":
            step = PlanStep(
                step_id="step-1",
                capability_name="voice_assistant",
                action="process_voice",
                params=task.payload,
            )
            return Plan(plan_id=plan_id, task_id=task.task_id, steps=[step])

        if task.task_type == "tool_call":
            tool_name = task.payload.get("tool_name") or task.payload.get("tool", "read_file")
            tool_params = task.payload.get("params", {})
            step = PlanStep(
                step_id="step-1",
                capability_name="tools",
                action=tool_name,
                params=tool_params,
            )
            return Plan(plan_id=plan_id, task_id=task.task_id, steps=[step])

        capability_name = task.payload.get("capability", "voice_assistant")
        action_name = task.payload.get("action", "default")

        step = PlanStep(
            step_id="step-1",
            capability_name=capability_name,
            action=action_name,
            params=task.payload,
        )
        return Plan(plan_id=plan_id, task_id=task.task_id, steps=[step])
