"""
CapabilityNegotiator inspecting active provider capabilities prior to execution plan generation.
"""

import logging
from typing import List, Optional
from jarvis.internet.interfaces.base import ProviderType
from jarvis.internet.providers.registry import ProviderRegistry

logger = logging.getLogger("jarvis.internet.planner.negotiation")


class CapabilityNegotiator:
    """Inspects ProviderRegistry to determine supported actions before building ExecutionPlan."""

    def __init__(self, registry: ProviderRegistry) -> None:
        self.registry = registry

    def supports_action(self, action: str) -> bool:
        """Check if action is supported by registered healthy providers."""
        if action in ("search", "direct_search"):
            return len(self.registry.list_providers(ProviderType.SEARCH)) > 0
        elif action in ("fetch", "web_fetch"):
            return len(self.registry.list_providers(ProviderType.FETCH)) > 0
        elif action in ("browser_render", "browser"):
            return len(self.registry.list_providers(ProviderType.BROWSER)) > 0
        elif action in ("extract", "extraction"):
            return len(self.registry.list_providers(ProviderType.EXTRACTION)) > 0
        elif action in ("rank", "ranking"):
            return len(self.registry.list_providers(ProviderType.RANKING)) > 0
        elif action in ("verify", "verification"):
            return len(self.registry.list_providers(ProviderType.VERIFICATION)) > 0
        return True

    def get_supported_strategies(self) -> List[str]:
        strategies = ["direct_search"]
        if self.supports_action("browser_render"):
            strategies.append("browser_spa")
        if self.supports_action("search") and self.supports_action("fetch") and self.supports_action("verify"):
            strategies.append("deep_research")
        return strategies
