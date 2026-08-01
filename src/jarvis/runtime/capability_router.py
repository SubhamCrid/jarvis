"""
CapabilityRouter routing execution requests exclusively via the BaseCapability interface.
"""

import logging
from typing import Any, Dict, Optional
from jarvis.capabilities.base import BaseCapability
from jarvis.capabilities.registry import CapabilityRegistry

logger = logging.getLogger("jarvis.runtime.router")


class CapabilityRouter:
    """
    CapabilityRouter routes step execution calls to registered capability modules
    using only the public BaseCapability interface.
    """

    def __init__(self, registry: Optional[CapabilityRegistry] = None) -> None:
        self.registry = registry or CapabilityRegistry()

    def register_capability(self, capability: BaseCapability) -> None:
        self.registry.register(capability)

    async def execute_action(
        self,
        capability_name: str,
        action_name: str,
        params: Dict[str, Any],
        session_id: str = "default_session",
    ) -> Any:
        cap = self.registry.get(capability_name)
        if not cap:
            raise KeyError(f"Capability '{capability_name}' is not registered in CapabilityRouter.")

        logger.info(f"CapabilityRouter routing action '{action_name}' to capability '{capability_name}'")
        return await cap.execute(action=action_name, params=params, session_id=session_id)
