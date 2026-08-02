"""
PipelineEngine executing declarative PipelineStage sequences with middleware chains and budget limits.
"""

import logging
import time
from typing import List, Optional
from jarvis.internet.budget import ExecutionBudget
from jarvis.internet.pipeline.context import ContextExecutionState, ExecutionContext
from jarvis.internet.pipeline.middleware import LoggingTelemetryMiddleware, PipelineMiddleware
from jarvis.internet.pipeline.stage import PipelineStage
from jarvis.internet.schemas import InternetResult

logger = logging.getLogger("jarvis.internet.pipeline.engine")


class DeclarativePipeline:
    """Declarative pipeline composition executing a sequence of stages."""

    def __init__(self, *stages: PipelineStage, middlewares: Optional[List[PipelineMiddleware]] = None) -> None:
        self.stages = list(stages)
        self.middlewares = middlewares or [LoggingTelemetryMiddleware()]

    async def execute(self, context: ExecutionContext, budget: ExecutionBudget) -> ExecutionContext:
        """Execute stage sequence in order with middleware interception."""
        for stage in self.stages:
            if context.cancellation_token and context.cancellation_token.is_cancelled():
                context.state = ContextExecutionState.CANCELLED
                logger.info(f"[{context.execution_id}] Pipeline execution cancelled.")
                break

            for mw in self.middlewares:
                await mw.before_stage(stage, context, budget)

            context = await stage.process(context, budget)

            for mw in self.middlewares:
                await mw.after_stage(stage, context, budget)

        return context


class PipelineEngine:
    """Orchestrates pipeline construction and execution for InternetPlatform."""

    def __init__(self, middlewares: Optional[List[PipelineMiddleware]] = None) -> None:
        self.middlewares = middlewares or [LoggingTelemetryMiddleware()]

    async def run_pipeline(
        self,
        pipeline: DeclarativePipeline,
        context: ExecutionContext,
        budget: ExecutionBudget,
    ) -> InternetResult:
        """Run declarative pipeline and return final InternetResult."""
        start_t = time.time()
        pipeline.middlewares = self.middlewares

        try:
            executed_ctx = await pipeline.execute(context, budget)
            duration_ms = (time.time() - start_t) * 1000.0

            return InternetResult(
                query=executed_ctx.query,
                strategy_used=executed_ctx.metadata.get("strategy", "DeclarativePipeline"),
                documents=executed_ctx.final_documents,
                verification=executed_ctx.verification_result,
                execution_time_ms=round(duration_ms, 2),
                offline_fallback_used=executed_ctx.metadata.get("offline_fallback", False),
                metadata={"execution_id": executed_ctx.execution_id, "trace_id": executed_ctx.trace_id},
            )
        except Exception as e:
            duration_ms = (time.time() - start_t) * 1000.0
            logger.error(f"[{context.execution_id}] Pipeline Engine execution error: {e}")
            context.state = ContextExecutionState.FAILED
            return InternetResult(
                query=context.query,
                strategy_used="FailedPipeline",
                documents=[],
                execution_time_ms=round(duration_ms, 2),
                metadata={"error": str(e), "execution_id": context.execution_id},
            )
