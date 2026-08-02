"""
BaseStrategyRule abstract interface for pluggable strategy rules.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from jarvis.internet.planner.plan import PlanStep
from jarvis.internet.schemas import SearchHit


class BaseStrategyRule(ABC):
    """Abstract interface for pluggable adaptive strategy rules."""

    name: str = "base_rule"

    @abstractmethod
    def evaluate(
        self,
        query: str,
        current_hits: List[SearchHit],
        health_scores: dict,
    ) -> Optional[PlanStep]:
        """Evaluate rule and return a new PlanStep if rule triggers, else None."""
        pass
