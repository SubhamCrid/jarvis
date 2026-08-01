"""
Planner converting high-level Goals into structured Plan objects for the Agent Runtime.
"""

from typing import Any, Dict, List, Optional
from jarvis.runtime.schemas import Goal, Plan, PlanStep, ExecutionState, RetryPolicy


class RuntimePlanner:
    """
    Constructs executable multi-step Plan objects from input Goals.
    """

    def create_plan(
        self, goal: Goal, explicit_steps: Optional[List[PlanStep]] = None
    ) -> Plan:
        if explicit_steps:
            steps = explicit_steps
        else:
            # Generate default plan steps based on goal parameters/payload
            steps = [
                PlanStep(
                    name="analyze_goal",
                    capability_name="tools",
                    action_name="execute",
                    params={"subcommand": "analyze", "description": goal.description},
                    retry_policy=RetryPolicy(),
                )
            ]

        plan = Plan(goal_id=goal.goal_id, steps=steps)
        goal.state = ExecutionState.PLANNED
        return plan
