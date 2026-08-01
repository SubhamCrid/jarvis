"""
Base abstract contract for backend tool adapters.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
from jarvis.tools.schemas import ExecutionContext, ToolSpec


class BaseToolAdapter(ABC):
    """Abstract interface for modular tool adapters."""

    @property
    @abstractmethod
    def spec(self) -> ToolSpec:
        """Return the ToolSpec metadata for this tool adapter."""
        pass

    @abstractmethod
    async def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        """Execute the tool's backend logic with clean parameters and runtime context."""
        pass
