"""
Pytest configuration and fixtures for Jarvis unit tests.
"""

import pytest
import asyncio
from pathlib import Path
from jarvis.core.config.loader import load_config
from jarvis.core.config.schema import AppConfig
from jarvis.core.bus import MessageBus
from jarvis.core.task_manager import TaskManager
from jarvis.core.planner import SimplePlanner
from jarvis.core.executor import TaskExecutor
from jarvis.core.observability import ObservabilityService


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
