"""
RecoveryManager and ExecutionHistory for failure recovery and history replay.
"""

from typing import Any, Dict, List, Optional
from jarvis.runtime.schemas import Plan, PlanStep, ExecutionState, StepResult


class RecoveryManager:
    """
    Manages failure recovery: retry policies, plan resumption, and step rollback.
    """

    def can_rollback(self, plan: Plan) -> bool:
        return any(s.state == ExecutionState.COMPLETED for s in plan.steps)

    def rollback_plan(self, plan: Plan) -> Plan:
        for step in plan.steps:
            if step.state in (ExecutionState.COMPLETED, ExecutionState.FAILED):
                step.state = ExecutionState.ROLLED_BACK
                step.result = None
                step.error = None
        return plan


class ExecutionHistory:
    """
    Records runtime step execution history and supports replay.
    """

    def __init__(self) -> None:
        self._history: List[Dict[str, Any]] = []

    def record_step(self, step: PlanStep, result: StepResult) -> None:
        self._history.append({
            "step_id": step.step_id,
            "name": step.name,
            "capability_name": step.capability_name,
            "action_name": step.action_name,
            "params": step.params,
            "success": result.success,
            "output": result.output,
            "error_message": result.error_message,
        })

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._history)
