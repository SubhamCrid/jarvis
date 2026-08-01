"""
Pure ToolRegistry for registering tool specs and looking up backend adapters.
Completely model-agnostic and provider-agnostic.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from jarvis.tools.schemas import ToolManifest, ToolSpec

logger = logging.getLogger("jarvis.tools.registry")


class ToolRegistry:
    """Central registry storing versioned tool specifications and adapter mappings."""

    def __init__(self) -> None:
        self._specs: Dict[str, ToolSpec] = {}
        self._adapters: Dict[str, Any] = {}

    def register(self, spec: ToolSpec, adapter: Any) -> None:
        """Register a tool specification and its corresponding backend adapter."""
        name = spec.manifest.name
        self._specs[name] = spec
        self._adapters[name] = adapter
        logger.info(f"Registered tool '{name}' (version: {spec.manifest.version})")

    def get_spec(self, name: str) -> Optional[ToolSpec]:
        """Retrieve ToolSpec by tool name."""
        return self._specs.get(name)

    def get_adapter(self, name: str) -> Optional[Any]:
        """Retrieve backend adapter by tool name."""
        return self._adapters.get(name)

    def get_tool(self, name: str) -> Optional[Tuple[ToolSpec, Any]]:
        """Retrieve (ToolSpec, Adapter) tuple by tool name."""
        spec = self._specs.get(name)
        adapter = self._adapters.get(name)
        if spec and adapter:
            return spec, adapter
        return None

    def list_specs(self) -> List[ToolSpec]:
        """List all registered ToolSpec instances."""
        return list(self._specs.values())

    def list_names(self) -> List[str]:
        """List names of all registered tools."""
        return list(self._specs.keys())

    def unregister(self, name: str) -> bool:
        """Remove a tool registration."""
        if name in self._specs:
            del self._specs[name]
            self._adapters.pop(name, None)
            return True
        return False
