"""
CapabilityRegistry for storing and looking up assistant capabilities.
"""

import logging
from typing import Dict, Optional, List
from jarvis.capabilities.base import BaseCapability

logger = logging.getLogger("jarvis.capabilities.registry")


class CapabilityRegistry:
    """Central registry holding active capabilities."""

    def __init__(self) -> None:
        self._capabilities: Dict[str, BaseCapability] = {}

    def register(self, capability: BaseCapability) -> None:
        self._capabilities[capability.name] = capability
        logger.info(f"Registered capability: '{capability.name}'")

    def get(self, name: str) -> Optional[BaseCapability]:
        return self._capabilities.get(name)

    def list_capabilities(self) -> List[str]:
        return list(self._capabilities.keys())
