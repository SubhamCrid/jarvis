"""
MemoryCoordinator for multi-type provider dispatch, cross-retrieval, deduplication, ranking, and storage routing.
"""

import logging
from typing import Dict, List, Optional
from jarvis.memory.schemas import (
    MemoryItem,
    MemoryQuery,
    MemorySearchResult,
    MemoryStoreRequest,
    MemoryType,
)
from jarvis.memory.providers.base import BaseMemoryProvider
from jarvis.memory.providers.sqlite import SQLiteMemoryProvider
from jarvis.resource.schemas import Resource, ResourceType, ResourcePermission, ActionDescriptor
from jarvis.resource.actions import generate_memory_actions

logger = logging.getLogger("jarvis.memory.coordinator")


class MemoryCoordinator:
    """
    High-level coordinator orchestrating multi-type memory providers (Working, Episodic, Semantic,
    User Profile, Knowledge Store), handling query dispatch, ranking, deduplication, and resource output conversion.
    """

    def __init__(self) -> None:
        self._providers: Dict[MemoryType, BaseMemoryProvider] = {}

    def register_provider(self, provider: BaseMemoryProvider) -> None:
        self._providers[provider.memory_type] = provider

    def get_provider(self, memory_type: MemoryType) -> Optional[BaseMemoryProvider]:
        return self._providers.get(memory_type)

    async def initialize_defaults(self) -> None:
        """Instantiate default SQLite providers for essential memory types."""
        for m_type in [
            MemoryType.WORKING,
            MemoryType.EPISODIC,
            MemoryType.SEMANTIC,
            MemoryType.USER_PROFILE,
            MemoryType.KNOWLEDGE_STORE,
        ]:
            if m_type not in self._providers:
                provider = SQLiteMemoryProvider(memory_type=m_type)
                await provider.initialize()
                self.register_provider(provider)

    async def store(self, request: MemoryStoreRequest) -> MemoryItem:
        provider = self.get_provider(request.memory_type)
        if not provider:
            provider = SQLiteMemoryProvider(memory_type=request.memory_type)
            await provider.initialize()
            self.register_provider(provider)

        item = MemoryItem(
            memory_type=request.memory_type,
            key=request.key,
            content=request.content,
            metadata=request.metadata,
            tags=request.tags,
            session_id=request.session_id,
        )
        return await provider.store(item)

    async def query(self, query: MemoryQuery) -> List[MemorySearchResult]:
        all_results: List[MemorySearchResult] = []

        # Dispatch query to requested memory type providers
        for m_type in query.memory_types:
            provider = self.get_provider(m_type)
            if provider:
                type_results = await provider.query(query)
                all_results.extend(type_results)

        # Deduplicate results by memory item ID
        seen_ids = set()
        deduped: List[MemorySearchResult] = []
        for r in all_results:
            if r.item.id not in seen_ids:
                seen_ids.add(r.item.id)
                deduped.append(r)

        # Rank by relevance score descending
        deduped.sort(key=lambda x: x.relevance_score, reverse=True)
        return deduped[: query.limit]

    async def query_as_resources(self, query: MemoryQuery) -> List[Resource]:
        search_results = await self.query(query)
        resources = []
        for res in search_results:
            item = res.item
            actions = generate_memory_actions(memory_id=item.id, memory_type=item.memory_type.value)
            resource = Resource(
                id=item.id,
                type=ResourceType.MEMORY,
                title=f"[{item.memory_type.value.upper()}] {item.key}",
                uri=f"memory://{item.memory_type.value}/{item.id}",
                metadata={"content": item.content, "confidence": item.confidence, "tags": item.tags},
                provider=f"memory_{item.memory_type.value}",
                actions=actions,
                permissions=[ResourcePermission.READ, ResourcePermission.DELETE],
            )
            resources.append(resource)
        return resources
