"""
Unit tests for jarvis.runtime platform.
"""

import pytest, asyncio
from jarvis.runtime import (
    AgentRuntime,
    ExecutionState,
    RuntimeStateMachine,
    StateMachineError,
    CapabilityRouter,
    WorkflowEngine,
    Plan,
    PlanStep,
    Goal,
    RuntimeScheduler,
    CheckpointManager,
    ApprovalManager,
    RecoveryManager,
)
from jarvis.capabilities.base import BaseCapability
from jarvis.core.base import HealthStatus, ServiceStatus


class MockCapability(BaseCapability):
    name: str = "mock_cap"
    description: str = "Mock capability for runtime testing"

    def __init__(self) -> None:
        self.call_count = 0

    async def initialize(self) -> bool:
        return True

    async def execute(self, action: str, params: dict, session_id: str):
        self.call_count += 1
        if action == "fail":
            raise ValueError("Intentional mock failure")
        return {"action": action, "status": "success", "call_count": self.call_count}

    async def health(self) -> HealthStatus:
        return HealthStatus(status=ServiceStatus.RUNNING)

    async def shutdown(self) -> None:
        pass

    async def cancel(self) -> None:
        pass


def test_state_machine_valid_transitions():
    sm = RuntimeStateMachine(ExecutionState.CREATED)
    assert sm.current_state == ExecutionState.CREATED

    sm.transition_to(ExecutionState.PLANNED)
    assert sm.current_state == ExecutionState.PLANNED

    sm.transition_to(ExecutionState.RUNNING)
    assert sm.current_state == ExecutionState.RUNNING

    sm.transition_to(ExecutionState.COMPLETED)
    assert sm.current_state == ExecutionState.COMPLETED


def test_state_machine_invalid_transition():
    sm = RuntimeStateMachine(ExecutionState.CREATED)
    with pytest.raises(StateMachineError):
        sm.transition_to(ExecutionState.COMPLETED)


@pytest.mark.asyncio
async def test_capability_router_execution():
    router = CapabilityRouter()
    mock_cap = MockCapability()
    router.register_capability(mock_cap)

    res = await router.execute_action(
        capability_name="mock_cap",
        action_name="test_run",
        params={"foo": "bar"},
    )
    assert res["status"] == "success"
    assert res["action"] == "test_run"


@pytest.mark.asyncio
async def test_workflow_engine_dag_execution():
    router = CapabilityRouter()
    mock_cap = MockCapability()
    router.register_capability(mock_cap)

    engine = WorkflowEngine(router=router)

    step1 = PlanStep(
        step_id="step-1",
        name="Step 1",
        capability_name="mock_cap",
        action_name="run_a",
    )
    step2 = PlanStep(
        step_id="step-2",
        name="Step 2",
        capability_name="mock_cap",
        action_name="run_b",
        depends_on=["step-1"],
    )

    plan = Plan(goal_id="g1", steps=[step1, step2])
    results = await engine.execute_plan(plan)

    assert len(results) == 2
    assert results["step-1"].success is True
    assert results["step-2"].success is True


def test_scheduler_once():
    sched = RuntimeScheduler()
    ran = False

    def handler():
        nonlocal ran
        ran = True

    task = sched.schedule_once(name="test", delay_seconds=0.0, handler=handler)
    assert task.name == "test"

    asyncio.run(sched.run_pending())
    assert ran is True


def test_checkpoint_manager():
    mgr = CheckpointManager()
    plan = Plan(
        goal_id="g1",
        steps=[PlanStep(step_id="s1", name="Step 1", capability_name="c1", action_name="a1")],
    )
    chk = mgr.create_checkpoint("g1", plan, completed_step_ids=["s1"], step_results={"s1": "ok"})
    assert chk.goal_id == "g1"

    restored_plan = mgr.restore_plan_state(plan, chk)
    assert restored_plan.steps[0].state == ExecutionState.COMPLETED


@pytest.mark.asyncio
async def test_agent_runtime_full_goal():
    router = CapabilityRouter()
    mock_cap = MockCapability()
    mock_cap.name = "tools"
    router.register_capability(mock_cap)

    runtime = AgentRuntime(router=router)
    await runtime.initialize()

    results = await runtime.execute_goal(description="Test Goal Execution")
    assert len(results) >= 1
