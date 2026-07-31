"""
Unit tests for TaskManager and Task lifecycle.
"""

from jarvis.core.task_manager import TaskManager, TaskStatus


def test_task_lifecycle(task_manager: TaskManager):
    task = task_manager.create_task(
        session_id="sess-123",
        task_type="voice_interaction",
        payload={"utterance": "hello"}
    )
    assert task.status == TaskStatus.PENDING
    assert task.session_id == "sess-123"

    updated = task_manager.update_status(task.task_id, TaskStatus.RUNNING)
    assert updated.status == TaskStatus.RUNNING

    completed = task_manager.update_status(task.task_id, TaskStatus.COMPLETED, result={"response": "hi"})
    assert completed.status == TaskStatus.COMPLETED
    assert completed.result == {"response": "hi"}
    assert completed.completed_at is not None


def test_task_cancellation(task_manager: TaskManager):
    task = task_manager.create_task("sess-456", "voice_interaction")
    cancelled = task_manager.cancel_task(task.task_id, reason="User barge-in")
    assert cancelled.status == TaskStatus.CANCELLED
    assert cancelled.error == "User barge-in"
