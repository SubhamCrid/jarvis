"""
SearchQueryPlanner generating SearchExecutionPlan based on intent and provider capabilities.
Separates query planning from provider execution.
"""

from typing import List
from jarvis.search.schemas import (
    SearchExecutionPlan,
    SearchQuery,
    SearchTargetType,
)


class SearchQueryPlanner:
    """Constructs tailored SearchExecutionPlan instances for incoming queries."""

    @classmethod
    def plan(cls, query: SearchQuery, available_providers: List[str]) -> SearchExecutionPlan:
        """Analyze query target type and filters to determine optimal provider strategy."""
        strategy = "filename_search"
        primary: List[str] = []
        fallbacks: List[str] = []

        if query.target_type == SearchTargetType.CONTENT:
            strategy = "content_search"
            if "ripgrep" in available_providers:
                primary.append("ripgrep")
            if "filesystem" in available_providers:
                fallbacks.append("filesystem")
        else:
            strategy = "filename_search"
            for p in ("everything", "windows_index"):
                if p in available_providers:
                    primary.append(p)

            if "ripgrep" in available_providers and query.clean_query:
                primary.append("ripgrep")

            if "filesystem" in available_providers:
                fallbacks.append("filesystem")

        if not primary and fallbacks:
            primary = fallbacks
            fallbacks = []

        return SearchExecutionPlan(
            query=query,
            primary_providers=primary,
            fallback_providers=fallbacks,
            strategy=strategy,
            parallel_execution=len(primary) > 1,
        )
