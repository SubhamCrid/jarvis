"""
PipelineMiddleware interface and logging/telemetry middleware chains.
"""

import logging
from abc import ABC, abstractmethod
from jarvis.internet.budget import ExecutionBudget
from jarvis.internet.pipeline.context import ExecutionContext
from jarvis.internet.pipeline.stage import PipelineStage

logger = logging.getLogger("jarvis.internet.pipeline.middleware")


class PipelineMiddleware(ABC):
    """Abstract middleware intercepting pre- and post- stage execution."""

    @abstractmethod
    async def before_stage(self, stage: PipelineStage, context: ExecutionContext, budget: ExecutionBudget) -> None:
        pass

    @abstractmethod
    async def after_stage(self, stage: PipelineStage, context: ExecutionContext, budget: ExecutionBudget) -> None:
        pass


class LoggingTelemetryMiddleware(PipelineMiddleware):
    """Default middleware emitting execution logs and state tracking."""

    async def before_stage(self, stage: PipelineStage, context: ExecutionContext, budget: ExecutionBudget) -> None:
        logger.info(f"[{context.execution_id}] Starting pipeline stage: '{stage.name}'")

    async def after_stage(self, stage: PipelineStage, context: ExecutionContext, budget: ExecutionBudget) -> None:
        logger.info(f"[{context.execution_id}] Completed pipeline stage: '{stage.name}'")
