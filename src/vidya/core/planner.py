"""
Planner Abstraction and Simple Single-Step Planner for Voice Tasks.
"""

import uuid
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass, field
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
    """Abstract interface for planning task execution steps."""

    @abstractmethod
    def create_plan(self, task: Task) -> Plan:
        """Create a plan consisting of steps for the given task."""
        pass


class SimplePlanner(PlannerProtocol):
    """
    Default simple planner for Voice MVP.
    Maps voice tasks directly to a 1-step VoiceAssistantCapability plan.
    """

    def create_plan(self, task: Task) -> Plan:
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"
        
        if task.task_type == "voice_interaction":
            step = PlanStep(
                step_id="step-1",
                capability_name="voice_assistant",
                action="process_voice",
                params=task.payload
            )
            return Plan(plan_id=plan_id, task_id=task.task_id, steps=[step])
        
        # Default fallback step
        step = PlanStep(
            step_id="step-1",
            capability_name=task.payload.get("capability", "voice_assistant"),
            action=task.payload.get("action", "default"),
            params=task.payload
        )
        return Plan(plan_id=plan_id, task_id=task.task_id, steps=[step])
