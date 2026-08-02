"""
Central InternetPlatform service class in jarvis.internet.
Positioned alongside jarvis.memory, jarvis.context, jarvis.policy, and jarvis.resources.
"""

import logging
from typing import Any, Dict, Optional
from jarvis.core.base import BaseServiceProtocol, HealthStatus, ServiceStatus
from jarvis.internet.budget import ExecutionBudget
from jarvis.internet.config import InternetConfig, load_internet_config
from jarvis.internet.health import ProviderHealthMonitor
from jarvis.internet.policy import InternetPolicy
from jarvis.internet.pipeline.context import ExecutionContext
from jarvis.internet.pipeline.engine import DeclarativePipeline, PipelineEngine
from jarvis.internet.pipeline.stages import (
    ExtractStage,
    FetchStage,
    FormatStage,
    RankStage,
    SearchStage,
    VerifyStage,
)
from jarvis.internet.planner.engine import InternetPlanner
from jarvis.internet.providers.browser.camoufox import CamoufoxBrowserProvider
from jarvis.internet.providers.cache.sqlite_cache import SQLiteInternetCache
from jarvis.internet.providers.extraction.trafilatura_extract import TrafilaturaExtractionProvider
from jarvis.internet.providers.fetch.httpx_fetch import HTTPXFetchProvider
from jarvis.internet.providers.ranking.bm25_ranker import BM25RankingProvider
from jarvis.internet.providers.registry import ProviderRegistry
from jarvis.internet.providers.search.arxiv import ArXivSearchProvider
from jarvis.internet.providers.search.duckduckgo import DuckDuckGoSearchProvider
from jarvis.internet.providers.search.wikipedia import WikipediaSearchProvider
from jarvis.internet.providers.verification.consensus_verifier import CrossSourceVerificationProvider
from jarvis.internet.schemas import ExtractedDocument, InternetResult
from jarvis.core.base import CancellationToken

logger = logging.getLogger("jarvis.internet.platform")


class InternetPlatform(BaseServiceProtocol):
    """
    Foundational Internet Intelligence Platform for Jarvis.
    Model-agnostic, low-VRAM (<6GB), secure, provider-decoupled, event-driven.
    """

    def __init__(self, config: Optional[InternetConfig] = None) -> None:
        self.config = config or load_internet_config()
        self._status = ServiceStatus.UNINITIALIZED

        self.health_monitor = ProviderHealthMonitor()
        self.registry = ProviderRegistry(health_monitor=self.health_monitor)
        self.policy = InternetPolicy(self.config)
        self.planner = InternetPlanner(self.registry)
        self.engine = PipelineEngine()

    async def initialize(self) -> bool:
        """Register default providers and initialize platform."""
        logger.info("Initializing jarvis.internet platform...")

        # Register default providers
        self.registry.register(DuckDuckGoSearchProvider())
        self.registry.register(WikipediaSearchProvider())
        self.registry.register(ArXivSearchProvider())
        self.registry.register(HTTPXFetchProvider())
        self.registry.register(TrafilaturaExtractionProvider())
        self.registry.register(CamoufoxBrowserProvider())
        self.registry.register(BM25RankingProvider())
        self.registry.register(SQLiteInternetCache())
        self.registry.register(CrossSourceVerificationProvider())

        # Initialize registered providers
        for name in self.registry.list_providers():
            provider = self.registry._providers[name]
            try:
                await provider.initialize()
            except Exception as e:
                logger.warning(f"Provider '{name}' initialization failed ({e}); keeping registered.")

        self._status = ServiceStatus.RUNNING
        logger.info(f"jarvis.internet platform initialized with {len(self.registry.list_providers())} registered providers.")
        return True

    async def health(self) -> HealthStatus:
        providers_health = {}
        for name in self.registry.list_providers():
            prov_name = name.split(":", 1)[1]
            h = self.health_monitor.get_provider_health(prov_name)
            providers_health[name] = h

        return HealthStatus(
            status=self._status,
            message="jarvis.internet platform operational",
            details={
                "providers": providers_health,
                "policy_mode": self.config.policy_mode,
                "enabled": self.config.enabled,
            },
        )

    async def execute_query(
        self,
        query: str,
        session_id: str = "default",
        cancellation_token: Optional[CancellationToken] = None,
    ) -> InternetResult:
        """
        Main platform entry point executing an internet query.
        """
        # 1. Check cache first if enabled
        cache_provider = self.registry.get_available_provider("cache", "sqlite")
        cache_key = f"query:{query.lower().strip()}"
        if self.config.providers.cache_enabled and cache_provider:
            cached_res = await cache_provider.get_result(cache_key)
            if cached_res:
                logger.info(f"Retrieved pipeline result from cache for query: '{query}'")
                return cached_res

        # 2. Plan execution
        plan = self.planner.create_plan(query)
        logger.info(f"InternetPlanner generated plan '{plan.plan_id}' using strategy '{plan.strategy_name}'")

        # 3. Create context and budget
        ctx = ExecutionContext(
            query=query,
            cancellation_token=cancellation_token or CancellationToken(),
            metadata={"strategy": plan.strategy_name},
        )
        budget = ExecutionBudget(
            max_tokens=self.config.limits.max_extraction_tokens,
            max_bytes=self.config.limits.max_page_size_bytes,
            timeout_sec=self.config.limits.max_concurrent_requests * 2.0,
            max_requests=self.config.limits.max_concurrent_requests,
        )

        # 4. Handle browser SPA strategy vs standard pipeline
        search_prov_name = "mock" if "search:mock" in self.registry._providers else self.config.providers.search.default
        fetch_prov_name = "mock" if "fetch:mock" in self.registry._providers else self.config.providers.fetch_default
        extract_prov_name = "mock" if "extraction:mock" in self.registry._providers else self.config.providers.extraction_default

        if plan.strategy_name == "BrowserSPAStrategy":
            browser_prov_name = "mock" if "browser:mock" in self.registry._providers else "camoufox"
            browser_prov = self.registry.get_available_provider("browser", browser_prov_name)
            ext_doc = await browser_prov.render_and_extract(
                url=query if query.startswith("http") else f"https://duckduckgo.com/?q={query}",
                timeout_sec=budget.timeout_sec,
                cancellation_token=ctx.cancellation_token,
            )
            ctx.extracted_documents = [ext_doc]
            pipeline = DeclarativePipeline(FormatStage())
        else:
            # Declarative search & fetch pipeline
            pipeline = DeclarativePipeline(
                SearchStage(self.registry, provider_name=search_prov_name, max_results=self.config.limits.max_domains_per_query),
                FetchStage(self.registry, provider_name=fetch_prov_name),
                ExtractStage(self.registry, provider_name=extract_prov_name),
                VerifyStage(self.registry, provider_name="cross_source") if self.config.providers.verification_enabled else FormatStage(),
                RankStage(self.registry, provider_name=self.config.providers.ranking_default),
                FormatStage(),
            )

        # 5. Run pipeline
        result = await self.engine.run_pipeline(pipeline, ctx, budget)

        # 6. Store in cache if successful
        if self.config.providers.cache_enabled and cache_provider and result.documents:
            await cache_provider.set_result(cache_key, result, ttl_sec=self.config.providers.cache_ttl_sec)

        return result

    async def shutdown(self) -> None:
        """Shutdown all registered providers."""
        logger.info("Shutting down jarvis.internet platform...")
        for name in self.registry.list_providers():
            provider = self.registry._providers[name]
            try:
                await provider.shutdown()
            except Exception as e:
                logger.warning(f"Provider '{name}' shutdown error: {e}")
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        """Cancel active platform tasks."""
        for name in self.registry.list_providers():
            provider = self.registry._providers[name]
            try:
                await provider.cancel()
            except Exception:
                pass
