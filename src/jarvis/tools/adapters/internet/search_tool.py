"""
InternetSearchToolAdapter exposing jarvis.internet platform capabilities to ToolRegistry.
Model-agnostic tool adapter for local 3B LLMs and OpenAI/Ollama tool calling.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from jarvis.internet.platform import InternetPlatform
from jarvis.tools.adapters.base import BaseToolAdapter
from jarvis.tools.schemas import ExecutionContext as ToolExecutionContext
from jarvis.tools.schemas import PermissionLevel, SideEffectLevel, ToolManifest, ToolSpec


class SearchInput(BaseModel):
    query: str = Field(description="Web search query string.")
    max_results: int = Field(default=5, description="Maximum number of web search results to return.")


class InternetSearchToolAdapter(BaseToolAdapter):
    """Tool adapter wrapping InternetPlatform for web search."""

    def __init__(self, platform: Optional[InternetPlatform] = None) -> None:
        self.platform = platform or InternetPlatform()

    @property
    def spec(self) -> ToolSpec:
        manifest = ToolManifest(
            name="web_search",
            version="1.0.0",
            description="Search the web for real-time information, news, documentation, and current events.",
            author="Jarvis Engine",
            permission_level=PermissionLevel.READ_ONLY,
            idempotent=True,
            read_only=True,
            side_effect_level=SideEffectLevel.NONE,
            timeout_sec=15.0,
        )
        return ToolSpec(
            manifest=manifest,
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Web search query string."},
                    "max_results": {"type": "integer", "default": 5, "description": "Maximum number of search hits."},
                },
                "required": ["query"],
            },
            input_model=SearchInput,
        )

    async def execute(self, params: Dict[str, Any], context: ToolExecutionContext) -> Any:
        query_str = params.get("query") or params.get("q") or ""
        if not query_str:
            return {"success": False, "error": "No query provided."}

        res = await self.platform.execute_query(
            query=query_str,
            session_id=context.session_id,
            cancellation_token=context.cancellation_token,
        )

        formatted_hits = []
        for doc in res.documents:
            formatted_hits.append({
                "title": doc.title,
                "url": doc.url,
                "summary": doc.summary,
            })

        return {
            "query": query_str,
            "strategy": res.strategy_used,
            "hits": formatted_hits,
            "execution_time_ms": res.execution_time_ms,
        }
