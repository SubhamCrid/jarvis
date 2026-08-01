"""
ToolRunner module coordinating validation, policy, locks, execution, cancellation,
redaction, tracing, persistence, and error normalization.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from jarvis.tools.config import ToolsConfig
from jarvis.tools.concurrency import ResourceLockManager
from jarvis.tools.health import ToolHealthCheck
from jarvis.tools.normalizer import ToolNormalizer
from jarvis.tools.persistence import ToolStore
from jarvis.tools.policy import PolicyViolationError, ToolPolicyEngine
from jarvis.tools.redactor import OutputRedactor
from jarvis.tools.schemas import (
    CancellationToken,
    ExecutionContext,
    ToolCall,
    ToolError,
    ToolResult,
    ToolSpec,
)
from jarvis.tools.tracer import ToolTracer
from jarvis.tools.validator import ToolValidator

logger = logging.getLogger("jarvis.tools.runner")


class ToolRunner:
    """Central tool execution pipeline enforcing security, cancellation, and metrics."""

    def __init__(
        self,
        config: Optional[ToolsConfig] = None,
        store: Optional[ToolStore] = None,
    ) -> None:
        self.config = config or ToolsConfig.from_env()
        self.policy_engine = ToolPolicyEngine(self.config)
        self.lock_manager = ResourceLockManager()
        self.tracer = ToolTracer()
        self.store = store or ToolStore()
        self.health = ToolHealthCheck(self.lock_manager)

    async def execute_call(
        self,
        call: ToolCall,
        spec: ToolSpec,
        adapter: Any,
        context: Optional[ExecutionContext] = None,
    ) -> ToolResult:
        """
        Execute a tool call through the complete single-responsibility pipeline.
        """
        t0 = time.time()
        exec_ctx = context or ExecutionContext(
            session_id=call.session_id,
            task_id=call.task_id,
        )
        cancellation_token = exec_ctx.cancellation_token

        # Check early cancellation
        if cancellation_token.is_cancelled():
            err = ToolError(code="CANCELLED", message="Execution cancelled prior to step run.")
            self.health.record_execution(success=False, cancelled=True)
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=False,
                error=err,
                execution_time_ms=(time.time() - t0) * 1000.0,
            )

        # 1. Parameter Validation
        try:
            clean_params = ToolValidator.validate(spec, call.params)
        except Exception as val_err:
            norm_err = ToolNormalizer.normalize_exception(val_err)
            self.health.record_execution(success=False)
            res = ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=False,
                error=norm_err,
                execution_time_ms=(time.time() - t0) * 1000.0,
            )
            self._finalize_trace(call, {"allowed": False, "reason": str(val_err)}, t0, res)
            return res

        # 2. Policy Engine Evaluation
        decision = self.policy_engine.evaluate(spec, clean_params)
        policy_dict = {
            "allowed": decision.allowed,
            "reason": decision.reason,
            "requires_confirmation": decision.requires_confirmation,
        }

        if not decision.allowed:
            err = ToolError(code="POLICY_VIOLATION", message=decision.reason, retryable=False)
            self.health.record_execution(success=False)
            res = ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=False,
                error=err,
                execution_time_ms=(time.time() - t0) * 1000.0,
            )
            self._finalize_trace(call, policy_dict, t0, res)
            return res

        # 3. Determine Resource Lock Key (e.g. target path)
        resource_key = clean_params.get("path") or clean_params.get("filepath") or clean_params.get("target_file")
        resource_str = str(resource_key) if resource_key else f"global_{spec.name}"

        # 4. Lock & Execute with Timeout / Retry / Cancellation
        max_retries = self.config.max_retries if (spec.manifest.idempotent or spec.manifest.read_only) else 0
        attempt = 0
        last_exception: Optional[Exception] = None
        result_data: Any = None
        exec_success = False

        async with self.lock_manager.lock_resource(resource_str):
            while attempt <= max_retries and not exec_success:
                if cancellation_token.is_cancelled():
                    last_exception = asyncio.CancelledError("Execution cancelled during retry loop.")
                    break

                try:
                    logger.debug(f"Executing tool '{spec.name}' attempt {attempt + 1}/{max_retries + 1}")
                    timeout = spec.manifest.timeout_sec or self.config.command_timeout_sec

                    # Execute adapter with timeout
                    raw_res = await asyncio.wait_for(
                        adapter.execute(clean_params, exec_ctx),
                        timeout=timeout,
                    )
                    result_data = raw_res
                    exec_success = True

                except asyncio.CancelledError as ce:
                    logger.info(f"Tool '{spec.name}' task cancelled.")
                    last_exception = ce
                    break
                except Exception as ex:
                    logger.warning(f"Tool '{spec.name}' attempt {attempt + 1} failed: {ex}")
                    last_exception = ex
                    attempt += 1

        dt_ms = (time.time() - t0) * 1000.0

        if exec_success:
            # Redact sensitive data if enabled
            if self.config.redaction_enabled:
                redacted_data = OutputRedactor.redact_data(result_data)
            else:
                redacted_data = result_data

            self.health.record_execution(success=True)
            res = ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=True,
                data=redacted_data,
                execution_time_ms=dt_ms,
            )
        else:
            is_cancel = isinstance(last_exception, asyncio.CancelledError) or cancellation_token.is_cancelled()
            norm_err = ToolNormalizer.normalize_exception(
                last_exception or RuntimeError("Tool execution failed.")
            )
            self.health.record_execution(success=False, cancelled=is_cancel)
            res = ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=False,
                error=norm_err,
                execution_time_ms=dt_ms,
            )

        self._finalize_trace(call, policy_dict, t0, res)
        return res

    def _finalize_trace(
        self,
        call: ToolCall,
        policy_decision: Dict[str, Any],
        start_time: float,
        result: ToolResult,
    ) -> None:
        """Record event trace in memory and persist to DB store."""
        event = self.tracer.record_event(call, policy_decision, start_time, result)
        if self.config.persist_traces:
            self.store.save_trace(event)
