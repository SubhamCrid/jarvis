"""
ExecutionPlan and PlanStep dataclasses/Pydantic models.
Defines immutable, serializable, replayable execution plans.
"""

import time
import uuid
from typing import Any, Dict, List
from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    """Individual atomic execution step in an ExecutionPlan."""

    step_id: str = Field(default_factory=lambda: f"step-{uuid.uuid4().hex[:6]}")
    action: str  # "search", "fetch", "extract", "verify", "rank", "browser_render"
    provider_type: str
    preferred_provider: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    """Immutable, serializable, replayable plan produced by InternetPlanner."""

    plan_id: str = Field(default_factory=lambda: f"plan-{uuid.uuid4().hex[:8]}")
    goal: str
    strategy_name: str
    steps: List[PlanStep] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)
