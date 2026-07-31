"""
Unit tests for AssistantOrchestrator lifecycle and health checks.
"""

import pytest
from jarvis.core.config.loader import load_config
from jarvis.orchestrator import AssistantOrchestrator
from jarvis.core.base import ServiceStatus


@pytest.mark.asyncio
async def test_orchestrator_lifecycle():
    config = load_config(user_overrides={"system": {"environment": "test"}})
    orchestrator = AssistantOrchestrator(config)

    assert await orchestrator.initialize()

    health = await orchestrator.health()
    assert health.status == ServiceStatus.RUNNING
    assert "voice_assistant" in health.details["registered_capabilities"]

    await orchestrator.start()
    await orchestrator.shutdown()
    assert orchestrator._status == ServiceStatus.STOPPED
