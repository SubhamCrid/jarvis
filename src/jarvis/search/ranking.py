"""
SearchRanker module for provider-independent match scoring and ranking.
"""

import difflib
import time
from pathlib import Path
from typing import List
from jarvis.search.schemas import SearchMatch, SearchQuery


class SearchRanker:
    """Scores candidate SearchMatch objects based on weighted factors."""

    @classmethod
    def rank(cls, query: SearchQuery, matches: List[SearchMatch]) -> List[SearchMatch]:
        """Score and sort matches descending by calculated rank score."""
        if not matches:
            return []

        target_text = (query.clean_query or query.raw_query).lower().strip()
        now = time.time()

        for match in matches:
            score = 0.0
            fname_lower = match.filename.lower()

            # 1. Exact filename match (+0.40)
            if target_text and fname_lower == target_text:
                score += 0.40
            elif target_text and target_text in fname_lower:
                score += 0.25

            # 2. Fuzzy similarity ratio (+0.25)
            if target_text:
                ratio = difflib.SequenceMatcher(None, target_text, fname_lower).ratio()
                score += ratio * 0.25

            # 3. Path depth & relevance (+0.15)
            depth = len(Path(match.path).parts)
            depth_bonus = max(0.0, 0.15 - (depth * 0.02))
            score += depth_bonus

            # 4. Modification recency (+0.10)
            if match.modified_at > 0:
                age_days = max(0.0, (now - match.modified_at) / 86400.0)
                recency_bonus = max(0.0, 0.10 - (age_days * 0.003))
                score += recency_bonus

            # 5. Base provider match score boost
            score += min(0.10, match.score * 0.10)

            match.score = round(min(1.0, score), 4)

        # Sort descending by score
        return sorted(matches, key=lambda m: m.score, reverse=True)
