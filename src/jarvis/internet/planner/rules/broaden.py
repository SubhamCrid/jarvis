"""
BroadenQueryRule implementation.
Triggers query broadening if initial search yields fewer than 2 search hits.
"""

import re
from typing import List, Optional
from jarvis.internet.planner.plan import PlanStep
from jarvis.internet.planner.rules.base import BaseStrategyRule
from jarvis.internet.schemas import SearchHit


class BroadenQueryRule(BaseStrategyRule):
    name = "broaden_query"

    def evaluate(
        self,
        query: str,
        current_hits: List[SearchHit],
        health_scores: dict,
    ) -> Optional[PlanStep]:
        if len(current_hits) >= 2:
            return None

        # Strip quotes, punctuation, and boolean operators
        broadened = re.sub(r'[\"\':?\!\(\)]', '', query)
        broadened = re.sub(r'\b(AND|OR|NOT|site:[^\s]+)\b', '', broadened, flags=re.IGNORECASE)
        broadened = re.sub(r'\s+', ' ', broadened).strip()

        if broadened == query:
            return None

        return PlanStep(
            action="search",
            provider_type="search",
            preferred_provider="duckduckgo",
            params={"query": broadened, "max_results": 5},
        )
