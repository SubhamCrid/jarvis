"""
CheckpointManager for saving and restoring runtime execution snapshots.
"""

from typing import Dict, Optional
from jarvis.runtime.schemas import Checkpoint, Plan, ExecutionState


class CheckpointManager:
    """
    Manages persistence and restoration of execution checkpoints.
    """

    def __init__(self) -> None:
        self._checkpoints: Dict[str, Checkpoint] = {}

    def create_checkpoint(
        self, goal_id: str, plan: Plan, completed_step_ids: list, step_results: dict
    ) -> Checkpoint:
        chk = Checkpoint(
            goal_id=goal_id,
            plan_id=plan.plan_id,
            completed_step_ids=completed_step_ids,
            step_results=step_results,
            state=ExecutionState.PAUSED,
        )
        self._checkpoints[chk.checkpoint_id] = chk
        return chk

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        return self._checkpoints.get(checkpoint_id)

    def restore_plan_state(self, plan: Plan, checkpoint: Checkpoint) -> Plan:
        for step in plan.steps:
            if step.step_id in checkpoint.completed_step_ids:
                step.state = ExecutionState.COMPLETED
                step.result = checkpoint.step_results.get(step.step_id)
        return plan
