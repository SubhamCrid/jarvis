"""
Scheduler for background jobs, delayed tasks, and recurring task execution.
"""

import asyncio, time, uuid, logging
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("jarvis.runtime.scheduler")


class ScheduledTask(BaseModel):
    task_id: str = Field(default_factory=lambda: f"sched-{uuid.uuid4().hex[:8]}")
    name: str
    run_at: float
    interval_seconds: Optional[float] = None
    executed: bool = False
    cancelled: bool = False

    class Config:
        frozen = False


class RuntimeScheduler:
    """
    Background job scheduler handling delayed, background, and recurring task execution.
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, ScheduledTask] = {}
        self._handlers: Dict[str, Callable[[], Any]] = {}

    def schedule_once(
        self, name: str, delay_seconds: float, handler: Callable[[], Any]
    ) -> ScheduledTask:
        run_at = time.time() + delay_seconds
        task = ScheduledTask(name=name, run_at=run_at)
        self._tasks[task.task_id] = task
        self._handlers[task.task_id] = handler
        return task

    def schedule_recurring(
        self, name: str, interval_seconds: float, handler: Callable[[], Any]
    ) -> ScheduledTask:
        run_at = time.time() + interval_seconds
        task = ScheduledTask(name=name, run_at=run_at, interval_seconds=interval_seconds)
        self._tasks[task.task_id] = task
        self._handlers[task.task_id] = handler
        return task

    def cancel(self, task_id: str) -> bool:
        if task_id in self._tasks:
            self._tasks[task_id].cancelled = True
            return True
        return False

    async def run_pending(self) -> int:
        now = time.time()
        executed_count = 0

        for task_id, task in list(self._tasks.items()):
            if not task.executed and not task.cancelled and now >= task.run_at:
                handler = self._handlers.get(task_id)
                if handler:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler()
                        else:
                            handler()
                    except Exception as e:
                        logger.error(f"Error running scheduled task '{task.name}': {e}")

                    executed_count += 1
                    if task.interval_seconds:
                        task.run_at = now + task.interval_seconds
                    else:
                        task.executed = True

        return executed_count
