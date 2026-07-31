"""
Unit tests for TaskExecutor.
"""

import pytest
import asyncio
from jarvis.core.planner import Plan, PlanStep
from jarvis.core.executor import TaskExecutor, ExecutionCancelledException


class MockCapabilityRegistry:
    def __init__(self, capability_map):
        self._map = capability_map

    def get(self, name):
        return self._map.get(name)


class MockSuccessCapability:
    async def execute(self, action: str, params: dict, session_id: str):
        return "success_result"


class MockFailThenSucceedCapability:
    def __init__(self):
        self.attempts = 0

    async def execute(self, action: str, params: dict, session_id: str):
        self.attempts += 1
        if self.attempts == 1:
            raise RuntimeError("Temporary glitch")
        return "recovered"


class MockSlowCapability:
    async def execute(self, action: str, params: dict, session_id: str):
        await asyncio.sleep(5.0)
        return "slow"


@pytest.mark.asyncio
async def test_executor_successful_plan(executor: TaskExecutor):
    registry = MockCapabilityRegistry({"voice_assistant": MockSuccessCapability()})
    plan = Plan("p1", "t1", [PlanStep("s1", "voice_assistant", "process")])
    
    result = await executor.execute_plan(plan, registry, "sess-1")
    assert result == "success_result"


@pytest.mark.asyncio
async def test_executor_retry_logic(executor: TaskExecutor):
    cap = MockFailThenSucceedCapability()
    registry = MockCapabilityRegistry({"voice_assistant": cap})
    plan = Plan("p1", "t1", [PlanStep("s1", "voice_assistant", "process")])
    
    result = await executor.execute_plan(plan, registry, "sess-1", max_retries=2)
    assert result == "recovered"
    assert cap.attempts == 2


@pytest.mark.asyncio
async def test_executor_timeout(executor: TaskExecutor):
    registry = MockCapabilityRegistry({"voice_assistant": MockSlowCapability()})
    plan = Plan("p1", "t1", [PlanStep("s1", "voice_assistant", "process")])
    
    with pytest.raises(RuntimeError):
        await executor.execute_plan(plan, registry, "sess-1", timeout_sec=0.1, max_retries=0)


@pytest.mark.asyncio
async def test_executor_cancellation(executor: TaskExecutor):
    registry = MockCapabilityRegistry({"voice_assistant": MockSlowCapability()})
    plan = Plan("p1", "t1", [PlanStep("s1", "voice_assistant", "process")])
    
    async def cancel_later():
        await asyncio.sleep(0.05)
        await executor.cancel()

    asyncio.create_task(cancel_later())
    
    with pytest.raises(ExecutionCancelledException):
        await executor.execute_plan(plan, registry, "sess-1", timeout_sec=5.0)
