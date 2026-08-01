"""
Optional EmbeddingProvider contract and mock implementation for Jarvis Memory Platform.
"""

from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """Abstract contract for generating vector embeddings."""

    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        pass


class MockEmbeddingProvider(EmbeddingProvider):
    """Lightweight fallback mock embedding provider producing deterministic float vectors."""

    def __init__(self, dimension: int = 64) -> None:
        self.dimension = dimension

    async def embed_text(self, text: str) -> List[float]:
        val = sum(ord(c) for c in text) % 100 / 100.0
        return [val] * self.dimension

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [await self.embed_text(t) for t in texts]
