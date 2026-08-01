"""
Abstract contract for LLM tool schema exporters.
"""

from abc import ABC, abstractmethod
from typing import Any, List
from jarvis.tools.schemas import ToolSpec


class BaseSchemaExporter(ABC):
    """Abstract interface for converting core ToolSpec list into provider-specific schemas."""

    @abstractmethod
    def export(self, specs: List[ToolSpec]) -> Any:
        """Export tool specifications into targeted LLM format."""
        pass
