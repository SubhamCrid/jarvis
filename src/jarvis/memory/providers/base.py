"""
Abstract provider interface contracts for distinct memory types in Jarvis Memory Platform.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from jarvis.memory.schemas import (
    MemoryItem,
    MemoryQuery,
    MemorySearchResult,
    MemoryType,
)


class BaseMemoryProvider(ABC):
    """Abstract interface fulfilled by all memory type providers."""

    @property
    @abstractmethod
    def memory_type(self) -> MemoryType:
        pass

    @abstractmethod
    async def initialize(self) -> bool:
        pass

    @abstractmethod
    async def store(self, item: MemoryItem) -> MemoryItem:
        pass

    @abstractmethod
    async def query(self, query: MemoryQuery) -> List[MemorySearchResult]:
        pass

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        pass

    @abstractmethod
    async def clear(self, session_id: Optional[str] = None) -> int:
        pass


class WorkingMemoryProvider(BaseMemoryProvider, ABC):
    """Interface for short-term active conversation context and scratchpad memory."""
    pass


class EpisodicMemoryProvider(BaseMemoryProvider, ABC):
    """Interface for interaction history and temporal event log memory."""
    pass


class SemanticMemoryProvider(BaseMemoryProvider, ABC):
    """Interface for factual entity relationships and knowledge graph memory."""
    pass


class UserProfileMemoryProvider(BaseMemoryProvider, ABC):
    """Interface for persistent user traits, preferences, and identity facts."""
    pass


class KnowledgeStoreMemoryProvider(BaseMemoryProvider, ABC):
    """Interface for indexed notes, documents, and reference materials."""
    pass


class VectorStoreProvider(BaseMemoryProvider, ABC):
    """Interface for dense vector store embeddings memory."""
    pass
