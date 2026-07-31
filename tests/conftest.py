"""
Pytest configuration and fixtures for Vidya unit tests.
"""

import pytest
import asyncio
from pathlib import Path
from vidya.core.config.loader import load_config
from vidya.core.config.schema import AppConfig
from vidya.core.bus import MessageBus
from vidya.core.task_manager import TaskManager
from vidya.core.planner import SimplePlanner
from vidya.core.executor import TaskExecutor
from vidya.core.observability import ObservabilityService


@pytest.fixture
def config() -> AppConfig:
    return load_config(user_overrides={"system": {"environment": "test"}})


@pytest.fixture
def message_bus() -> MessageBus:
    return MessageBus()


@pytest.fixture
def task_manager() -> TaskManager:
    return TaskManager()


@pytest.fixture
def planner() -> SimplePlanner:
    return SimplePlanner()


@pytest.fixture
def executor() -> TaskExecutor:
    return TaskExecutor()


@pytest.fixture
def observability() -> ObservabilityService:
    return ObservabilityService()
