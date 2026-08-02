"""
PipelineStage abstract interface for declarative pipeline composition.
"""

from abc import ABC, abstractmethod
from jarvis.internet.budget import ExecutionBudget
from jarvis.internet.pipeline.context import ExecutionContext


class PipelineStage(ABC):
    """Abstract interface for a single stage in an InternetPipeline."""

    name: str = "base_stage"

    @abstractmethod
    async def process(self, context: ExecutionContext, budget: ExecutionBudget) -> ExecutionContext:
        """Process pipeline stage with context and budget constraints."""
        pass
