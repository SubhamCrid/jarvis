"""
Schemas and dataclasses for Ephemeral Context Platform (jarvis.context).
"""

import time
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ContextScope(str, Enum):
    SYSTEM = "system"
    CONVERSATION = "conversation"
    TASK = "task"
    WORKFLOW = "workflow"
    DESKTOP = "desktop"
    ENVIRONMENT = "environment"
    EPHEMERAL = "ephemeral"


class ContextItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    value: Any
    scope: ContextScope = ContextScope.EPHEMERAL
    ttl_seconds: Optional[float] = None
    created_at: float = Field(default_factory=time.time)
    expires_at: Optional[float] = None
    tags: List[str] = Field(default_factory=list)

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        now = current_time or time.time()
        if self.expires_at is not None:
            return now >= self.expires_at
        return False


class ContextSnapshot(BaseModel):
    """Consolidated snapshot of active execution context passed to planners/evaluators."""

    model_config = ConfigDict(frozen=True)

    session_id: str = "default_session"
    active_task_id: Optional[str] = None
    focused_app: str = ""
    active_window: str = ""
    current_file: str = ""
    current_url: str = ""
    clipboard_preview: str = ""
    environment_vars: Dict[str, str] = Field(default_factory=dict)
    scoped_variables: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)

