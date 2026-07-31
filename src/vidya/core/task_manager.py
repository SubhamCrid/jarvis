"""
Task management and lifecycle tracking for asynchronous assistant operations.
"""

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class Task:
    task_id: str
    session_id: str
    task_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    completed_at: Optional[str] = None


class TaskManager:
    """Tracks active and historical execution tasks across user sessions."""

    def __init__(self) -> None:
        self._tasks: Dict[str, Task] = {}

    def create_task(
        self, session_id: str, task_type: str, payload: Optional[Dict[str, Any]] = None
    ) -> Task:
        """Instantiate and register a new pending execution task."""
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task = Task(
            task_id=task_id,
            session_id=session_id,
            task_type=task_type,
            payload=payload or {},
        )
        self._tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve a task by its unique identifier."""
        return self._tasks.get(task_id)

    def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> Optional[Task]:
        """Update the operational status, outcome, or error state of a task."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        task.status = status
        if result is not None:
            task.result = result
        if error is not None:
            task.error = error
        if status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED):
            task.completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return task

    def cancel_task(self, task_id: str, reason: str = "User interruption") -> Optional[Task]:
        """Cancel an active task with a specified cancellation reason."""
        return self.update_status(task_id, TaskStatus.CANCELLED, error=reason)

    def list_active_tasks(self) -> List[Task]:
        """Return all tasks currently in PENDING or RUNNING status."""
        return [
            t
            for t in self._tasks.values()
            if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
        ]

