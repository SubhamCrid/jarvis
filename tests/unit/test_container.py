"""
Unit tests for jarvis.core.container ServiceContainer.
"""

import pytest
from jarvis.core.container import ServiceContainer
from jarvis.core.bus import MessageBus
from jarvis.policy.engine import PolicyEngine
from jarvis.context.manager import ContextManager
from jarvis.memory.coordinator import MemoryCoordinator
from jarvis.runtime.executor import AgentRuntime


@pytest.mark.asyncio
async def test_service_container_resolution():
    container = ServiceContainer()
    await container.initialize()

    bus = container.resolve(MessageBus)
    assert bus is not None

    policy = container.resolve(PolicyEngine)
    assert policy is not None

    context = container.resolve(ContextManager)
    assert context is not None

    mem = container.resolve(MemoryCoordinator)
    assert mem is not None

    runtime = container.resolve(AgentRuntime)
    assert runtime is not None
