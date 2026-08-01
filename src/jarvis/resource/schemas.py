"""
Typed contract schemas for the Jarvis Universal Resource Model.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ResourceType(str, Enum):
    FILE = "file"
    FOLDER = "folder"
    APP = "app"
    BROWSER_TAB = "browser_tab"
    BROWSER_HISTORY = "browser_history"
    EMAIL = "email"
    CALENDAR = "calendar"
    NOTE = "note"
    CLIPBOARD = "clipboard"
    CONVERSATION = "conversation"
    MEMORY = "memory"
    DATABASE = "database"
    DOCKER = "docker"
    WSL = "wsl"
    GIT = "git"
    UNKNOWN = "unknown"


class ResourcePermission(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    SHARE = "share"
    ADMIN = "admin"


class ActionDescriptor(BaseModel):
    """Generic, capability-agnostic descriptor of an action that can be performed."""

    model_config = ConfigDict(frozen=True)

    name: str
    label: str
    capability_name: str = "system"
    required_permissions: List[ResourcePermission] = Field(
        default_factory=lambda: [ResourcePermission.READ]
    )
    params: Dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class Resource(BaseModel):
    """
    Universal resource representation exchanged across Search, Tools,
    Memory, Browser, Voice, and Runtime platforms.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    type: ResourceType = ResourceType.UNKNOWN
    title: str
    uri: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    provider: str = "system"
    actions: List[ActionDescriptor] = Field(default_factory=list)
    permissions: List[ResourcePermission] = Field(
        default_factory=lambda: [ResourcePermission.READ]
    )

