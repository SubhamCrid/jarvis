"""
Planner abstraction and step resolution logic for assistant execution plans.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List
import uuid

from vidya.core.task_manager import Task


@dataclass
class PlanStep:
    step_id: str
    capability_name: str
    action: str
    params: Dict[str, Any] = field(default_factory=dict)


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
    Default single-step planner mapping incoming interaction tasks directly
    to capability actions.
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

        capability_name = task.payload.get("capability", "voice_assistant")
        action_name = task.payload.get("action", "default")

        step = PlanStep(
            step_id="step-1",
            capability_name=capability_name,
            action=action_name,
            params=task.payload,
        )
        return Plan(plan_id=plan_id, task_id=task.task_id, steps=[step])

