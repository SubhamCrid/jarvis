"""
TaskExecutor for sequencing step execution, retries, timeouts, and cancellation.
"""

import asyncio
import logging
from typing import Any, Dict, Optional
from vidya.core.planner import Plan, PlanStep

logger = logging.getLogger("vidya.core.executor")


class ExecutionCancelledException(Exception):
    """Raised when task execution is cancelled mid-flight."""
    pass


class TaskExecutor:
    """
    Executes Plan steps by routing to registered capabilities.
    Enforces retries, timeouts, and active cancellation without god-object complexity.
    """

    def __init__(self) -> None:
        self._current_task: Optional[asyncio.Task] = None
        self._is_cancelled: bool = False

    async def execute_plan(
        self,
        plan: Plan,
        capability_registry: Any,
        session_id: str,
        timeout_sec: float = 30.0,
        max_retries: int = 2
    ) -> Any:
        self._is_cancelled = False
        last_result = None

        for step in plan.steps:
            if self._is_cancelled:
                raise ExecutionCancelledException("Execution was cancelled before step start.")

            capability = capability_registry.get(step.capability_name)
            if not capability:
                raise ValueError(f"Capability '{step.capability_name}' not registered.")

            retry_count = 0
            success = False
            last_error: Optional[Exception] = None

            while retry_count <= max_retries and not success:
                if self._is_cancelled:
                    raise ExecutionCancelledException("Execution cancelled during retry loop.")

                try:
                    logger.debug(f"Executing step {step.step_id} (Attempt {retry_count + 1}/{max_retries + 1})")
                    
                    # Wrap step in timeout
                    step_coro = capability.execute(
                        action=step.action,
                        params=step.params,
                        session_id=session_id
                    )
                    
                    self._current_task = asyncio.create_task(step_coro)
                    last_result = await asyncio.wait_for(self._current_task, timeout=timeout_sec)
                    success = True

                except asyncio.TimeoutError as te:
                    logger.warning(f"Step {step.step_id} timed out after {timeout_sec}s.")
                    last_error = te
                    retry_count += 1
                except asyncio.CancelledError as ce:
                    logger.info(f"Step {step.step_id} cancelled.")
                    self._is_cancelled = True
                    raise ExecutionCancelledException("Step task cancelled.") from ce
                except Exception as e:
                    logger.error(f"Error in step {step.step_id}: {e}")
                    last_error = e
                    retry_count += 1
                finally:
                    self._current_task = None

            if not success:
                raise RuntimeError(f"Step {step.step_id} failed after {max_retries + 1} attempts: {last_error}")

        return last_result

    async def cancel(self) -> None:
        """Cancel current in-flight step execution."""
        self._is_cancelled = True
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            logger.info("TaskExecutor cancelled active task step.")
