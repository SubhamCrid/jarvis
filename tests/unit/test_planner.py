"""
Unit tests for Planner and SimplePlanner.
"""

from vidya.core.task_manager import Task
from vidya.core.planner import SimplePlanner, Plan


def test_simple_planner_voice_task(planner: SimplePlanner):
    task = Task(
        task_id="task-001",
        session_id="sess-001",
        task_type="voice_interaction",
        payload={"audio": "input.wav"}
    )
    plan = planner.create_plan(task)
    assert isinstance(plan, Plan)
    assert len(plan.steps) == 1
    assert plan.steps[0].capability_name == "voice_assistant"
    assert plan.steps[0].action == "process_voice"
