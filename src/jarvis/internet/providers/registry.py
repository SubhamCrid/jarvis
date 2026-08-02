"""
ProviderRegistry, ProviderFactory, and ProviderLoader.
Manages dynamic registration, instantiation, lookup, and hot-swapping of BaseInternetProvider implementations.
"""

import logging
from typing import Dict, List, Optional, Type
from jarvis.internet.exceptions import ProviderNotFoundError
from jarvis.internet.health import ProviderHealthMonitor
from jarvis.internet.interfaces.base import BaseInternetProvider, ProviderType

logger = logging.getLogger("jarvis.internet.providers.registry")


class ProviderRegistry:
    """Central registry holding active providers by type and name."""

    def __init__(self, health_monitor: Optional[ProviderHealthMonitor] = None) -> None:
        self._providers: Dict[str, BaseInternetProvider] = {}
        self.health_monitor = health_monitor or ProviderHealthMonitor()

    def register(self, provider: BaseInternetProvider) -> None:
        """Register a concrete BaseInternetProvider instance."""
        key = f"{provider.provider_type.value}:{provider.name}"
        self._providers[key] = provider
        logger.info(f"Registered provider: '{key}' (v{provider.version})")

    def unregister(self, provider_type: ProviderType | str, name: str) -> bool:
        ptype = provider_type.value if isinstance(provider_type, ProviderType) else str(provider_type)
        key = f"{ptype}:{name}"
        if key in self._providers:
            del self._providers[key]
            logger.info(f"Unregistered provider: '{key}'")
            return True
        return False

    def get(self, provider_type: ProviderType | str, name: str) -> BaseInternetProvider:
        ptype = provider_type.value if isinstance(provider_type, ProviderType) else str(provider_type)
        key = f"{ptype}:{name}"
        if key not in self._providers:
            raise ProviderNotFoundError(f"Provider '{key}' is not registered.")
        return self._providers[key]

    def list_providers(self, provider_type: Optional[ProviderType | str] = None) -> List[str]:
        if not provider_type:
            return list(self._providers.keys())
        ptype = provider_type.value if isinstance(provider_type, ProviderType) else str(provider_type)
        prefix = f"{ptype}:"
        return [k.split(":", 1)[1] for k in self._providers.keys() if k.startswith(prefix)]

    def get_available_provider(self, provider_type: ProviderType | str, preferred_name: str) -> BaseInternetProvider:
        """Get preferred provider if healthy, else fallback to first available healthy provider of same type."""
        ptype = provider_type.value if isinstance(provider_type, ProviderType) else str(provider_type)
        key = f"{ptype}:{preferred_name}"

        # 1. Try preferred
        if key in self._providers and self.health_monitor.allow_request(preferred_name):
            return self._providers[key]

        # 2. Fallback to any healthy provider of same type
        registered_names = self.list_providers(ptype)
        for name in registered_names:
            if self.health_monitor.allow_request(name):
                logger.warning(f"Preferred provider '{key}' unavailable; falling back to '{ptype}:{name}'")
                return self.get(ptype, name)

        # 3. If all circuit breakers OPEN, return preferred anyway as last resort
        if key in self._providers:
            return self._providers[key]

        raise ProviderNotFoundError(f"No available provider found for type '{ptype}'.")
