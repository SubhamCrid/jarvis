"""
Unit tests for WebDashboardServer static dashboard, tool execution, and WebSocket endpoints.
"""

import pytest
from aiohttp.test_utils import make_mocked_request

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

    # Test GET /api/tools handler
    resp = await server._handle_list_tools(None)
    assert resp.status == 200

    # Test GET /api/capabilities handler
    resp = await server._handle_list_capabilities(None)
    assert resp.status == 200

    # Test GET /api/agent/state handler
    resp = await server._handle_get_agent_state(None)
    assert resp.status == 200

    # Test POST /api/approval/respond handler
    mock_req = make_mocked_request("POST", "/api/approval/respond")
    mock_req.json = lambda: _async_return({"request_id": "req_123", "approved": True})
    resp = await server._handle_respond_approval(mock_req)
    assert resp.status == 200

    await server.stop()
    await orchestrator.shutdown()


async def _async_return(val):
    return val
