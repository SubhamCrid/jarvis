"""
SearchCapability container integrating Search Platform into CapabilityRegistry.
"""

import logging
from typing import Any, Dict, Optional
from jarvis.capabilities.base import BaseCapability, PermissionEnum
from jarvis.core.base import HealthStatus, ServiceStatus
from jarvis.search.pipeline import SearchPipelineEngine
from jarvis.search.providers import (
    EverythingSearchProvider,
    FilesystemSearchProvider,
    RipgrepSearchProvider,
    WindowsIndexSearchProvider,
)

logger = logging.getLogger("jarvis.search.capability")


class SearchCapability(BaseCapability):
    """Domain capability exposing Search Platform to AssistantOrchestrator."""

    name = "search"
    required_permissions = [PermissionEnum.FILESYSTEM]

    def __init__(self, engine: Optional[SearchPipelineEngine] = None) -> None:
        self.engine = engine or SearchPipelineEngine()
        self._status = ServiceStatus.UNINITIALIZED

    async def initialize(self) -> bool:
        """Register default search providers."""
        if not self.engine.registry.list_names():
            self.engine.registry.register(EverythingSearchProvider())
            self.engine.registry.register(WindowsIndexSearchProvider())
            self.engine.registry.register(RipgrepSearchProvider())
            self.engine.registry.register(FilesystemSearchProvider())

        self._status = ServiceStatus.RUNNING
        logger.info(f"SearchCapability initialized with {len(self.engine.registry.list_names())} providers.")
        return True

    async def health(self) -> HealthStatus:
        reg_names = self.engine.registry.list_names()
        avail_names = await self.engine.registry.list_available_names()
        health_info = self.engine.health.get_health_status(reg_names, avail_names)

        return HealthStatus(
            status=self._status,
            message="Search Platform status",
            details=health_info,
        )

    async def execute(self, action: str, params: Dict[str, Any], session_id: str) -> Any:
        """Execute a search action via SearchPipelineEngine."""
        query_str = params.get("query") or params.get("q") or ""
        if action == "search" or action == "query":
            response = await self.engine.execute_search(query_str, session_id=session_id)
            return response.model_dump()
        elif action == "next_page":
            page_items = self.engine.session_store.get_next_page(session_id)
            return [m.model_dump() for m in page_items]
        else:
            response = await self.engine.execute_search(f"{action}:{query_str}", session_id=session_id)
            return response.model_dump()

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        pass
