"""
Base Capability protocol and Permission definitions.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Dict, Any, Optional
from vidya.core.base import BaseServiceProtocol


class PermissionEnum(str, Enum):
    AUDIO = "audio"
    INTERNET = "internet"
    DESKTOP = "desktop"
    SHELL = "shell"
    FILESYSTEM = "filesystem"


class BaseCapability(BaseServiceProtocol, ABC):
    """
    Base Capability abstraction representing a high-level assistant domain (Voice, Browser, Desktop).
    Capabilities orchestrate tools and manage domain sessions.
    """

    name: str = "base_capability"
    required_permissions: List[PermissionEnum] = []

    @abstractmethod
    async def execute(self, action: str, params: Dict[str, Any], session_id: str) -> Any:
        """Execute a capability action for a given session."""
        pass
