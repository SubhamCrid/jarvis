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

    # Test stop listening handler
    resp = await server._handle_stop_listening(None)
    assert resp.status == 200

    # Test trigger wake handler
    resp = await server._handle_trigger_wake(None)
    assert resp.status == 200

    # Test interrupt while listening -> transitions to IDLE
    resp = await server._handle_interrupt(None)
    assert resp.status == 200
    assert orchestrator.fsm.state == "IDLE"

    # Test interrupt while IDLE -> ignored, stays IDLE
    resp = await server._handle_interrupt(None)
    assert resp.status == 200
    assert orchestrator.fsm.state == "IDLE"

    await server.stop()
    await orchestrator.shutdown()

