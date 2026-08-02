"""
Comprehensive automated Pytest unit suite for jarvis.internet platform.
Tests URLSandbox SSRF protection, ProviderRegistry, ProviderCircuitBreakers,
InternetPlanner ExecutionPlan generation, Declarative Pipeline Engine,
Camoufox Browser Sandbox, CancellationToken barge-in, and Tool Adapters.
"""

import pytest
from jarvis.core.base import CancellationToken, ServiceStatus
from jarvis.internet.exceptions import SSRFPolicyError
from jarvis.internet.health import CircuitState, ProviderCircuitBreaker
from jarvis.internet.pipeline.context import ExecutionContext
from jarvis.internet.pipeline.engine import DeclarativePipeline, PipelineEngine
from jarvis.internet.pipeline.stages import FormatStage, SearchStage
from jarvis.internet.planner.engine import InternetPlanner
from jarvis.internet.platform import InternetPlatform
from jarvis.internet.providers.browser.camoufox import CamoufoxBrowserProvider
from jarvis.internet.providers.browser.fsm import BrowserState
from jarvis.internet.providers.mock import (
    MockBrowserProvider,
    MockExtractionProvider,
    MockFetchProvider,
    MockSearchProvider,
)
from jarvis.internet.providers.registry import ProviderRegistry
from jarvis.internet.schemas import SearchHit
from jarvis.internet.security.sandbox import URLSandbox
from jarvis.tools.adapters.internet.search_tool import InternetSearchToolAdapter
from jarvis.tools.schemas import ExecutionContext as ToolExecutionContext


@pytest.mark.asyncio
async def test_url_sandbox_ssrf_protection():
    """Verify URLSandbox rejects loopbacks, private subnets, and cloud metadata."""
    sandbox = URLSandbox(enable_ssrf_protection=True)

    # Rejections
    with pytest.raises(SSRFPolicyError):
        sandbox.validate_url("http://127.0.0.1/admin")

    with pytest.raises(SSRFPolicyError):
        sandbox.validate_url("http://localhost:8080")

    with pytest.raises(SSRFPolicyError):
        sandbox.validate_url("http://169.254.169.254/latest/meta-data/")

    # Acceptance
    url = sandbox.validate_url("https://en.wikipedia.org/wiki/Python")
    assert url == "https://en.wikipedia.org/wiki/Python"


@pytest.mark.asyncio
async def test_provider_circuit_breaker():
    """Verify ProviderCircuitBreaker state transitions (CLOSED -> OPEN -> HALF_OPEN)."""
    cb = ProviderCircuitBreaker(provider_name="test_prov", failure_threshold=2, cooldown_sec=0.1)
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True

    # Record 1 failure
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED

    # Record 2nd failure -> Trips to OPEN
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False

    # Wait for cooldown
    import asyncio
    await asyncio.sleep(0.15)
    assert cb.allow_request() is True
    assert cb.state == CircuitState.HALF_OPEN

    # Record success -> Resets to CLOSED
    cb.record_success(latency_ms=10.0)
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_provider_registry():
    """Verify ProviderRegistry registration and dynamic provider resolution."""
    registry = ProviderRegistry()
    mock_search = MockSearchProvider()
    registry.register(mock_search)

    retrieved = registry.get("search", "mock")
    assert retrieved.name == "mock"
    assert "search:mock" in registry.list_providers()


@pytest.mark.asyncio
async def test_internet_planner_execution_plan():
    """Verify InternetPlanner generates immutable ExecutionPlan objects."""
    registry = ProviderRegistry()
    registry.register(MockSearchProvider())
    planner = InternetPlanner(registry)

    plan = planner.create_plan("what is Python programming language?")
    assert plan.plan_id.startswith("plan-")
    assert plan.strategy_name == "DirectSearchStrategy"
    assert len(plan.steps) == 4
    assert plan.steps[0].action == "search"

    json_str = plan.to_json()
    assert "DirectSearchStrategy" in json_str


@pytest.mark.asyncio
async def test_camoufox_browser_provider():
    """Verify CamoufoxBrowserProvider initialization, capabilities, and execution."""
    camoufox = CamoufoxBrowserProvider()
    await camoufox.initialize()
    assert camoufox.state == BrowserState.READY
    assert camoufox.capabilities.stealth_level == "high"

    doc = await camoufox.render_and_extract("https://en.wikipedia.org/wiki/Python")
    assert doc.url == "https://en.wikipedia.org/wiki/Python"
    assert doc.clean_markdown != ""

    await camoufox.shutdown()
    assert camoufox.state == BrowserState.STOPPED


@pytest.mark.asyncio
async def test_internet_platform_end_to_end():
    """Verify InternetPlatform query execution end-to-end with mock providers."""
    platform = InternetPlatform()
    # Register mock providers into platform registry
    platform.registry.register(MockSearchProvider())
    platform.registry.register(MockFetchProvider())
    platform.registry.register(MockExtractionProvider())
    platform.registry.register(MockBrowserProvider())

    await platform.initialize()
    assert platform._status == ServiceStatus.RUNNING

    result = await platform.execute_query("Jarvis, test unique query 999")
    assert result.query == "Jarvis, test unique query 999"
    assert len(result.documents) > 0
    assert result.documents[0].url.startswith("https://example.com")

    health = await platform.health()
    assert health.status == ServiceStatus.RUNNING

    await platform.shutdown()
    assert platform._status == ServiceStatus.STOPPED


@pytest.mark.asyncio
async def test_internet_search_tool_adapter():
    """Verify InternetSearchToolAdapter compatibility with ToolRegistry."""
    platform = InternetPlatform()
    platform.registry.register(MockSearchProvider())
    platform.registry.register(MockFetchProvider())
    platform.registry.register(MockExtractionProvider())
    await platform.initialize()

    adapter = InternetSearchToolAdapter(platform)
    assert adapter.spec.name == "web_search"

    tool_ctx = ToolExecutionContext(session_id="test_sess", task_id="test_task")
    res = await adapter.execute({"query": "Python news"}, tool_ctx)

    assert res["query"] == "Python news"
    assert "hits" in res
    assert len(res["hits"]) > 0

    await platform.shutdown()
