"""
Jarvis Search Platform.

A production-grade, modular, provider-based search framework supporting
multi-provider parallel execution, query planning, DSL parsing, ranking,
TTL caching, conversational search sessions, async streaming, and telemetry.
"""

from jarvis.search.adapter import SearchToolAdapter
from jarvis.search.capability import SearchCapability
from jarvis.search.config import SearchConfig
from jarvis.search.dsl import SearchDSLParser
from jarvis.search.events import SearchEventBus
from jarvis.search.health import SearchHealthCheck
from jarvis.search.index_manager import SearchIndexManager
from jarvis.search.merge import SearchMergeEngine
from jarvis.search.metrics import SearchMetricsCollector
from jarvis.search.pipeline import SearchPipelineEngine
from jarvis.search.planner import SearchQueryPlanner
from jarvis.search.ranking import SearchRanker
from jarvis.search.registry import SearchProviderRegistry
from jarvis.search.sandbox import SearchRootSandbox, SearchSandboxError
from jarvis.search.schemas import (
    SearchError,
    SearchExecutionPlan,
    SearchMatch,
    SearchProviderManifest,
    SearchQuery,
    SearchResponse,
    SearchTargetType,
)
from jarvis.search.session import SearchSession, SearchSessionStore
from jarvis.search.streaming import SearchStreamGenerator
from jarvis.search.tracer import SearchTracer

__version__ = "1.0.0"

__all__ = [
    "SearchConfig",
    "SearchQuery",
    "SearchMatch",
    "SearchResponse",
    "SearchTargetType",
    "SearchError",
    "SearchProviderManifest",
    "SearchExecutionPlan",
    "SearchDSLParser",
    "SearchQueryPlanner",
    "SearchRootSandbox",
    "SearchSandboxError",
    "SearchRanker",
    "SearchMergeEngine",
    "SearchCache",
    "SearchSessionStore",
    "SearchSession",
    "SearchStreamGenerator",
    "SearchEventBus",
    "SearchMetricsCollector",
    "SearchHealthCheck",
    "SearchTracer",
    "SearchIndexManager",
    "SearchProviderRegistry",
    "SearchPipelineEngine",
    "SearchCapability",
    "SearchToolAdapter",
]
