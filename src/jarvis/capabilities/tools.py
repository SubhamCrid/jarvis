"""
ToolProtocol and BaseTool abstraction for single executable action units composed by capabilities.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from vidya.core.base import BaseServiceProtocol


class ToolProtocol(BaseServiceProtocol, ABC):
    """
    Protocol for discrete executable action units (e.g. TranscribeTool, SynthesizeTool, NavigateTool).
    """

    name: str = "base_tool"
    description: str = ""
    parameters_schema: Dict[str, Any] = {}

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Any:
        """Execute tool action with parameters."""
        pass
