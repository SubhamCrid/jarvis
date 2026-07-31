"""
Unit tests for WebDashboardServer static dashboard and WebSocket endpoints.
"""

import pytest
from jarvis.core.config.loader import load_config
from jarvis.orchestrator import AssistantOrchestrator
from jarvis.web.server import WebDashboardServer


@pytest.mark.asyncio
async def test_web_dashboard_server_routes():
    config = load_config(user_overrides={"system": {"environment": "test"}})
    orchestrator = AssistantOrchestrator(config)
    await orchestrator.initialize()

    server = WebDashboardServer(orchestrator, port=8099)
    await server.start()

    # Verify server status
    assert server._runner is not None

    await server.stop()
    await orchestrator.shutdown()
