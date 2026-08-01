"""
SearchProviderRegistry storing registered search provider instances.
"""

import logging
from typing import Dict, List, Optional
from jarvis.search.providers.base import BaseSearchProvider

logger = logging.getLogger("jarvis.search.registry")


class SearchProviderRegistry:
    """Central registry storing search backend provider instances."""

    def __init__(self) -> None:
        self._providers: Dict[str, BaseSearchProvider] = {}

    def register(self, provider: BaseSearchProvider) -> None:
        """Register a search provider."""
        name = provider.manifest.name
        self._providers[name] = provider
        logger.info(f"Registered search provider '{name}'")

    def get(self, name: str) -> Optional[BaseSearchProvider]:
        """Retrieve provider by name."""
        return self._providers.get(name)

    def list_names(self) -> List[str]:
        """List names of registered search providers."""
        return list(self._providers.keys())

    async def list_available_names(self) -> List[str]:
        """List names of currently available search providers."""
        available = []
        for name, provider in self._providers.items():
            try:
                if await provider.is_available():
                    available.append(name)
            except Exception:
                continue
        return available
