"""
InternetPlanner and StrategyEngine.
Deterministic code-driven query planning engine producing immutable ExecutionPlan instances.
"""

import logging
from typing import Optional
from jarvis.internet.planner.negotiation import CapabilityNegotiator
from jarvis.internet.planner.plan import ExecutionPlan, PlanStep
from jarvis.internet.providers.registry import ProviderRegistry

logger = logging.getLogger("jarvis.internet.planner.engine")


class InternetPlanner:
    """
    Code-driven deterministic query planner producing immutable ExecutionPlan objects.
    """

    def __init__(self, registry: ProviderRegistry) -> None:
        self.registry = registry
        self.negotiator = CapabilityNegotiator(registry)

    def create_plan(self, query: str, strategy_hint: Optional[str] = None) -> ExecutionPlan:
        """
        Evaluate query intent and provider capabilities to generate an immutable ExecutionPlan.
        """
        query_lower = query.lower()

        # 1. Check if query requests dynamic browser render / SPA
        if ("render" in query_lower or "spa" in query_lower or "browser" in query_lower) and self.negotiator.supports_action("browser_render"):
            return self._build_browser_plan(query)

        # 2. Check if deep research requested
        if ("research" in query_lower or "deep" in query_lower or "investigate" in query_lower) and self.negotiator.supports_action("verify"):
            return self._build_deep_research_plan(query)

        # 3. Default direct search plan
        return self._build_direct_search_plan(query)

    def _build_direct_search_plan(self, query: str) -> ExecutionPlan:
        s1 = PlanStep(
            action="search",
            provider_type="search",
            preferred_provider="duckduckgo",
            params={"query": query, "max_results": 5},
        )
        s2 = PlanStep(
            action="fetch",
            provider_type="fetch",
            preferred_provider="httpx",
            params={},
            dependencies=[s1.step_id],
        )
        s3 = PlanStep(
            action="extract",
            provider_type="extraction",
            preferred_provider="trafilatura",
            params={},
            dependencies=[s2.step_id],
        )
        s4 = PlanStep(
            action="rank",
            provider_type="ranking",
            preferred_provider="bm25",
            params={"query": query},
            dependencies=[s3.step_id],
        )

        return ExecutionPlan(
            goal=f"Direct search query: '{query}'",
            strategy_name="DirectSearchStrategy",
            steps=[s1, s2, s3, s4],
        )

    def _build_deep_research_plan(self, query: str) -> ExecutionPlan:
        s1 = PlanStep(
            action="search",
            provider_type="search",
            preferred_provider="duckduckgo",
            params={"query": query, "max_results": 5},
        )
        s2 = PlanStep(
            action="fetch",
            provider_type="fetch",
            preferred_provider="httpx",
            params={},
            dependencies=[s1.step_id],
        )
        s3 = PlanStep(
            action="extract",
            provider_type="extraction",
            preferred_provider="trafilatura",
            params={},
            dependencies=[s2.step_id],
        )
        s4 = PlanStep(
            action="verify",
            provider_type="verification",
            preferred_provider="cross_source",
            params={"query": query},
            dependencies=[s3.step_id],
        )
        s5 = PlanStep(
            action="rank",
            provider_type="ranking",
            preferred_provider="bm25",
            params={"query": query},
            dependencies=[s4.step_id],
        )

        return ExecutionPlan(
            goal=f"Deep research query: '{query}'",
            strategy_name="DeepResearchStrategy",
            steps=[s1, s2, s3, s4, s5],
        )

    def _build_browser_plan(self, query: str) -> ExecutionPlan:
        s1 = PlanStep(
            action="browser_render",
            provider_type="browser",
            preferred_provider="camoufox",
            params={"url": query if query.startswith("http") else f"https://duckduckgo.com/?q={query}"},
        )
        return ExecutionPlan(
            goal=f"Browser SPA automation query: '{query}'",
            strategy_name="BrowserSPAStrategy",
            steps=[s1],
        )
