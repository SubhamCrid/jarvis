"""
BM25RankingProvider implementation.
Ranks SearchHit objects using BM25 / keyword term frequency relevance scoring.
"""

import math
import re
from typing import List
from jarvis.core.base import HealthStatus, ServiceStatus
from jarvis.internet.interfaces.ranking import RankingProvider
from jarvis.internet.schemas import SearchHit


class BM25RankingProvider(RankingProvider):
    name = "bm25"
    version = "1.0.0"

    def __init__(self) -> None:
        self._status = ServiceStatus.UNINITIALIZED

    async def initialize(self) -> bool:
        self._status = ServiceStatus.RUNNING
        return True

    async def health(self) -> HealthStatus:
        return HealthStatus(status=self._status, message="BM25RankingProvider operational")

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        pass

    async def rank(
        self,
        hits: List[SearchHit],
        query: str,
        top_k: int = 5,
    ) -> List[SearchHit]:
        """Rank hits based on term match overlap with query."""
        if not hits or not query:
            return hits[:top_k]

        query_terms = set(re.findall(r"\w+", query.lower()))
        if not query_terms:
            return hits[:top_k]

        scored_hits = []
        for hit in hits:
            text = f"{hit.title} {hit.snippet}".lower()
            tokens = re.findall(r"\w+", text)
            score = 0.0
            for term in query_terms:
                count = tokens.count(term)
                if count > 0:
                    score += (count / (count + 1.5)) * math.log(1.0 + len(tokens))

            # Combine engine score and BM25 score
            final_score = round(hit.score * 0.5 + score * 0.5, 3)
            hit.score = final_score
            scored_hits.append(hit)

        scored_hits.sort(key=lambda h: h.score, reverse=True)
        return scored_hits[:top_k]
