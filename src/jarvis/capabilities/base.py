"""
Base Capability protocol and Permission definitions.
Capabilities represent high-level assistant domains (Search, Tools, Voice, Memory, Browser, Desktop).
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Dict, Any, Optional, Type
from jarvis.core.base import BaseServiceProtocol, HealthStatus, ServiceStatus
from jarvis.resource.schemas import ResourcePermission, ActionDescriptor


class PermissionEnum(str, Enum):
    AUDIO = "audio"
    INTERNET = "internet"
    DESKTOP = "desktop"
    SHELL = "shell"
    FILESYSTEM = "filesystem"


class BaseCapability(BaseServiceProtocol, ABC):
    """
    Unified Base Capability abstraction representing a high-level assistant domain.
    Exposes a consistent lifecycle: initialize, shutdown, health, cancel, actions, events, permissions, execute.
    """

    name: str = "base_capability"
    description: str = "Abstract base capability"
    required_permissions: List[ResourcePermission] = []
    actions: List[ActionDescriptor] = []
    events: List[Type[Any]] = []

    @abstractmethod
    async def execute(self, action: str, params: Dict[str, Any], session_id: str) -> Any:
        """Execute a capability action for a given session."""
        pass
