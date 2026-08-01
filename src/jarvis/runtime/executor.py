"""
Top-level Agent Runtime execution engine coordinating Planner, WorkflowEngine, StateMachine, and CapabilityRouter.
"""

import logging
from typing import Any, Dict, Optional
from jarvis.core.base import BaseServiceProtocol, HealthStatus, ServiceStatus
from jarvis.runtime.schemas import Goal, Task, Plan, ExecutionState, StepResult
from jarvis.runtime.state import RuntimeStateMachine
from jarvis.runtime.capability_router import CapabilityRouter
from jarvis.runtime.planner import RuntimePlanner
from jarvis.runtime.workflow import WorkflowEngine
from jarvis.runtime.approval import ApprovalManager
from jarvis.runtime.checkpoint import CheckpointManager
from jarvis.runtime.recovery import RecoveryManager, ExecutionHistory
from jarvis.policy.engine import PolicyEngine

logger = logging.getLogger("jarvis.runtime.executor")


class AgentRuntime(BaseServiceProtocol):
    """
    Agent Runtime Platform: Top-level orchestration brain executing goals and plans
    exclusively via registered BaseCapability interfaces through CapabilityRouter.
    """

    def __init__(
        self,
        router: Optional[CapabilityRouter] = None,
        policy_engine: Optional[PolicyEngine] = None,
    ) -> None:
        self.router = router or CapabilityRouter()
        self.policy_engine = policy_engine or PolicyEngine()
        self.planner = RuntimePlanner()
        self.workflow_engine = WorkflowEngine(self.router, self.policy_engine)
        self.approval_manager = ApprovalManager()
        self.checkpoint_manager = CheckpointManager()
        self.recovery_manager = RecoveryManager()
        self.history = ExecutionHistory()
        self._status = ServiceStatus.UNINITIALIZED
        self._active_goals: Dict[str, Goal] = {}

    async def initialize(self) -> bool:
        self._status = ServiceStatus.RUNNING
        logger.info("AgentRuntime Platform initialized successfully.")
        return True

    async def execute_goal(
        self, description: str, session_id: str = "default_session"
    ) -> Dict[str, StepResult]:
        goal = Goal(description=description, session_id=session_id)
        self._active_goals[goal.goal_id] = goal

        state_machine = RuntimeStateMachine(initial_state=goal.state)
        state_machine.transition_to(ExecutionState.PLANNED)
        goal.state = ExecutionState.PLANNED

        plan = self.planner.create_plan(goal)

        state_machine.transition_to(ExecutionState.RUNNING)
        goal.state = ExecutionState.RUNNING

        results = await self.workflow_engine.execute_plan(plan, session_id=session_id)

        all_success = all(r.success for r in results.values())
        if all_success:
            state_machine.transition_to(ExecutionState.COMPLETED)
            goal.state = ExecutionState.COMPLETED
        else:
            state_machine.transition_to(ExecutionState.FAILED)
            goal.state = ExecutionState.FAILED

        return results

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="Agent Runtime Platform status",
            details={"active_goals_count": len(self._active_goals)},
        )

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        for goal in self._active_goals.values():
            goal.state = ExecutionState.CANCELLED
