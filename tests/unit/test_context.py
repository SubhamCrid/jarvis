"""
Unit tests for jarvis.context platform.
"""

import time
import pytest
from jarvis.context import (
    ContextManager,
    ContextScope,
    ContextStore,
    ContextSnapshot,
)


def test_context_store_set_and_get():
    store = ContextStore()
    store.set("user_name", "Alice", scope=ContextScope.CONVERSATION)

    val = store.get("user_name", scope=ContextScope.CONVERSATION)
    assert val == "Alice"


def test_context_store_ttl_expiration():
    store = ContextStore()
    # Set item with 0.1s TTL
    store.set("temp_token", "abc12345", scope=ContextScope.EPHEMERAL, ttl_seconds=0.1)

    assert store.get("temp_token", scope=ContextScope.EPHEMERAL) == "abc12345"
    time.sleep(0.15)
    assert store.get("temp_token", scope=ContextScope.EPHEMERAL) is None


def test_context_manager_snapshot():
    manager = ContextManager()
    manager.set_context("focused_app", "VSCode", scope=ContextScope.DESKTOP)
    manager.set_context("active_task_id", "task-99", scope=ContextScope.TASK)

    snapshot = manager.take_snapshot(session_id="sess-1")
    assert snapshot.session_id == "sess-1"
    assert snapshot.focused_app == "VSCode"
    assert snapshot.active_task_id == "task-99"
