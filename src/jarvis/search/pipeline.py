"""
SearchPipelineEngine orchestrating the 7-stage search execution pipeline.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

from jarvis.search.cache import SearchCache
from jarvis.search.config import SearchConfig
from jarvis.search.dsl import SearchDSLParser
from jarvis.search.events import SearchEventBus
from jarvis.search.filter import SearchFilterEngine
from jarvis.search.health import SearchHealthCheck
from jarvis.search.index_manager import SearchIndexManager
from jarvis.search.merge import SearchMergeEngine
from jarvis.search.metrics import SearchMetricsCollector
from jarvis.search.planner import SearchQueryPlanner
from jarvis.search.ranking import SearchRanker
from jarvis.search.registry import SearchProviderRegistry
from jarvis.search.sandbox import SearchRootSandbox
from jarvis.search.schemas import SearchMatch, SearchQuery, SearchResponse
from jarvis.search.session import SearchSessionStore
from jarvis.search.tracer import SearchTracer
from jarvis.tools.schemas import CancellationToken


class SearchPipelineEngine:
    """Orchestrates the 7-stage search pipeline."""

    def __init__(
        self,
        config: Optional[SearchConfig] = None,
        registry: Optional[SearchProviderRegistry] = None,
    ) -> None:
        self.config = config or SearchConfig.from_env()
        self.registry = registry or SearchProviderRegistry()
        self.sandbox = SearchRootSandbox(self.config.search_root)
        self.filter_engine = SearchFilterEngine(self.sandbox)
        self.cache = SearchCache(ttl_sec=self.config.cache_ttl_sec)
        self.session_store = SearchSessionStore()
        self.event_bus = SearchEventBus()
        self.metrics = SearchMetricsCollector()
        self.health = SearchHealthCheck(self.metrics)
        self.tracer = SearchTracer()
        self.index_manager = SearchIndexManager(workspace_root=self.config.search_root)

    async def execute_search(
        self,
        raw_query_str: str,
        session_id: Optional[str] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> SearchResponse:
        """Execute full 7-stage search pipeline."""
        t0 = time.time()

        # 1. DSL Parsing & Query Normalization
        query = SearchDSLParser.parse(raw_query_str)
        if not query.search_root:
            query.search_root = str(self.config.search_root)

        if session_id:
            query.session_id = session_id

        # 2. Check Cache
        cache_key = f"{query.raw_query}:{query.target_type.value}:{query.search_root or ''}"
        cached_resp = self.cache.get(cache_key)
        if cached_resp:
            self.metrics.record_search(duration_ms=(time.time() - t0) * 1000.0, cached=True)
            return cached_resp

        # 3. Query Planning
        available_names = await self.registry.list_available_names()
        plan = SearchQueryPlanner.plan(query, available_names)

        # 4. Multi-Provider Parallel Execution & Fallback
        target_provider_names = plan.primary_providers or plan.fallback_providers
        if not target_provider_names:
            target_provider_names = ["filesystem"]

        provider_instances = [self.registry.get(name) for name in target_provider_names if self.registry.get(name)]

        # Execute providers in parallel
        provider_tasks = [
            p.search(query, cancellation_token) for p in provider_instances
        ]

        raw_results: List[List[SearchMatch]] = []
        providers_used: List[str] = []
        is_fallback = False

        if provider_tasks:
            try:
                results_list = await asyncio.gather(*provider_tasks, return_exceptions=True)
                for idx, res in enumerate(results_list):
                    p_name = provider_instances[idx].manifest.name
                    if isinstance(res, list) and res:
                        raw_results.append(res)
                        providers_used.append(p_name)
                    elif isinstance(res, Exception):
                        self.health.record_provider_failure(p_name)

            except Exception:
                is_fallback = True

        # Fallback to IndexManager if primary results are empty
        if not raw_results and self.config.enable_index_manager:
            index_matches = self.index_manager.query_index(query.clean_query or query.raw_query)
            if index_matches:
                raw_results.append(index_matches)
                providers_used.append("index_manager")
                is_fallback = True

        # 5. Merge & Deduplicate
        candidate_matches = SearchMergeEngine.merge(raw_results)

        # 6. Filter & Sandbox Enforce
        filtered_matches = self.filter_engine.filter_matches(query, candidate_matches)

        # 7. Rank & Score Matches
        ranked_matches = SearchRanker.rank(query, filtered_matches)[: query.max_results]

        dt_ms = (time.time() - t0) * 1000.0
        response = SearchResponse(
            query=raw_query_str,
            matches=ranked_matches,
            total_found=len(ranked_matches),
            providers_used=providers_used,
            execution_time_ms=dt_ms,
            cached=False,
        )

        # Store session state for voice pagination
        if session_id:
            self.session_store.update_session(session_id, query, ranked_matches)

        # Cache response
        self.cache.put(cache_key, response)

        # Record metrics & telemetry trace
        self.metrics.record_search(duration_ms=dt_ms, cached=False, fallback=is_fallback)
        self.tracer.record_trace(query, response)

        return response
