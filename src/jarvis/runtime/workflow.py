"""
Workflow engine supporting DAG execution, dependencies, branching, loops, and parallel execution.
"""

import asyncio, logging
from typing import Any, Dict, List, Optional, Set
from jarvis.runtime.schemas import Plan, PlanStep, ExecutionState, StepResult
from jarvis.runtime.capability_router import CapabilityRouter
from jarvis.policy.engine import PolicyEngine

logger = logging.getLogger("jarvis.runtime.workflow")


class WorkflowEngine:
    """
    Executes Plan step DAGs, resolving step dependencies, managing retries,
    consulting PolicyEngine for approval gates, and executing steps via CapabilityRouter.
    """

    def __init__(
        self,
        router: CapabilityRouter,
        policy_engine: Optional[PolicyEngine] = None,
    ) -> None:
        self.router = router
        self.policy_engine = policy_engine or PolicyEngine()

    async def execute_plan(
        self, plan: Plan, session_id: str = "default_session"
    ) -> Dict[str, StepResult]:
        results: Dict[str, StepResult] = {}
        completed_steps: Set[str] = set()
        failed_steps: Set[str] = set()

        step_map = {step.step_id: step for step in plan.steps}

        while len(completed_steps) + len(failed_steps) < len(plan.steps):
            # Find steps whose dependencies are satisfied
            ready_steps = [
                step
                for step in plan.steps
                if step.step_id not in completed_steps
                and step.step_id not in failed_steps
                and all(dep in completed_steps for dep in step.depends_on)
            ]

            if not ready_steps:
                # Deadlock or missing dependency
                logger.error("Workflow DAG stalled: no ready steps found.")
                break

            # Execute ready steps in parallel
            tasks = [
                self._execute_step(step, session_id) for step in ready_steps
            ]
            step_results = await asyncio.gather(*tasks, return_exceptions=True)

            for step, res in zip(ready_steps, step_results):
                if isinstance(res, Exception):
                    step.state = ExecutionState.FAILED
                    step.error = str(res)
                    failed_steps.add(step.step_id)
                    results[step.step_id] = StepResult(
                        step_id=step.step_id, success=False, error_message=str(res)
                    )
                elif res.success:
                    step.state = ExecutionState.COMPLETED
                    step.result = res.output
                    completed_steps.add(step.step_id)
                    results[step.step_id] = res
                else:
                    step.state = ExecutionState.FAILED
                    step.error = res.error_message
                    failed_steps.add(step.step_id)
                    results[step.step_id] = res

        return results

    async def _execute_step(self, step: PlanStep, session_id: str) -> StepResult:
        step.state = ExecutionState.RUNNING

        # Consult PolicyEngine before execution
        eval_res = self.policy_engine.evaluate_action(
            capability_name=step.capability_name,
            action_name=step.action_name,
            params=step.params,
        )

        if eval_res.decision.value == "deny":
            return StepResult(
                step_id=step.step_id,
                success=False,
                error_message=f"Policy denied execution: {eval_res.reason}",
            )

        # Handle retries if policy allows
        max_attempts = step.retry_policy.max_retries if step.retry_policy else 1
        last_err: Optional[Exception] = None

        for attempt in range(max_attempts):
            try:
                output = await self.router.execute_action(
                    capability_name=step.capability_name,
                    action_name=step.action_name,
                    params=step.params,
                    session_id=session_id,
                )
                return StepResult(step_id=step.step_id, success=True, output=output)
            except Exception as e:
                last_err = e
                logger.warning(f"Step '{step.name}' attempt {attempt + 1} failed: {e}")
                if attempt < max_attempts - 1 and step.retry_policy:
                    await asyncio.sleep(step.retry_policy.delay_seconds)

        return StepResult(
            step_id=step.step_id,
            success=False,
            error_message=str(last_err) if last_err else "Execution failed",
        )
