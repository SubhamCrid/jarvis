"""
RankingProvider contract.
Interface for score-ranking search hits and extracted documents.
"""

from abc import ABC, abstractmethod
from typing import List
from jarvis.internet.interfaces.base import BaseInternetProvider, ProviderType
from jarvis.internet.schemas import SearchHit


class RankingProvider(BaseInternetProvider, ABC):
    """Abstract interface for snippet and hit ranking providers."""

    provider_type = ProviderType.RANKING

    @abstractmethod
    async def rank(
        self,
        hits: List[SearchHit],
        query: str,
        top_k: int = 5,
    ) -> List[SearchHit]:
        """Rank search hits according to relevance, BM25, recency, or domain trust."""
        pass
