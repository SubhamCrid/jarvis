"""
AdaptiveStrategyEngine executing pluggable StrategyRule chains.
Provides deterministic, code-driven fallback and rule evaluation.
"""

import logging
from typing import List, Optional
from jarvis.internet.planner.plan import ExecutionPlan, PlanStep
from jarvis.internet.planner.rules.base import BaseStrategyRule
from jarvis.internet.planner.rules.broaden import BroadenQueryRule
from jarvis.internet.schemas import SearchHit

logger = logging.getLogger("jarvis.internet.planner.adaptive")


class AdaptiveStrategyEngine:
    """Executes a sequence of pluggable StrategyRule instances."""

    def __init__(self, rules: Optional[List[BaseStrategyRule]] = None) -> None:
        self.rules = rules or [BroadenQueryRule()]

    def register_rule(self, rule: BaseStrategyRule) -> None:
        self.rules.append(rule)

    def evaluate_rules(
        self,
        query: str,
        current_hits: List[SearchHit],
        health_scores: dict,
    ) -> List[PlanStep]:
        """Evaluate registered rules and return list of adaptive PlanStep triggers."""
        triggered_steps = []
        for rule in self.rules:
            step = rule.evaluate(query, current_hits, health_scores)
            if step:
                logger.info(f"StrategyRule '{rule.name}' triggered step action '{step.action}'.")
                triggered_steps.append(step)
        return triggered_steps
