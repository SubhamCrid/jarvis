"""
SearchToolAdapter bridging Tool Execution Platform to Search Platform cleanly
without circular package dependencies.
"""

from typing import Any, Dict
from jarvis.search.pipeline import SearchPipelineEngine
from jarvis.tools.adapters.base import BaseToolAdapter
from jarvis.tools.schemas import (
    ExecutionContext,
    PermissionLevel,
    SideEffectLevel,
    ToolManifest,
    ToolSpec,
)


class SearchToolAdapter(BaseToolAdapter):
    """Tool adapter wrapping SearchPipelineEngine.search for ToolRegistry."""

    def __init__(self, search_engine: SearchPipelineEngine) -> None:
        self.search_engine = search_engine

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            manifest=ToolManifest(
                name="search_system",
                version="1.0.0",
                description="Search system files, folders, and contents using natural queries or DSL (e.g. 'kind:file ext:py size>10KB').",
                permission_level=PermissionLevel.READ_ONLY,
                idempotent=True,
                read_only=True,
                side_effect_level=SideEffectLevel.NONE,
                timeout_sec=15.0,
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query or DSL expression (e.g. 'report.pdf', 'kind:file ext:py').",
                    },
                },
                "required": ["query"],
            },
        )

    async def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        query_str = params["query"]
        response = await self.search_engine.execute_search(
            query_str,
            session_id=context.session_id,
            cancellation_token=context.cancellation_token,
        )
        return response.model_dump()
