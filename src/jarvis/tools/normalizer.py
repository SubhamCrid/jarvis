"""
ToolNormalizer for standardizing all tool errors into predictable ToolError formats.
"""

import asyncio
from typing import Any, Dict
from jarvis.tools.policy import PolicyViolationError
from jarvis.tools.sandbox import PathTraversalError
from jarvis.tools.schemas import ToolError
from jarvis.tools.validator import ValidationError


class ToolNormalizer:
    """Standardizes Python exceptions into structured, machine-readable ToolError contracts."""

    @staticmethod
    def normalize_exception(err: Exception) -> ToolError:
        """Convert any exception into a normalized ToolError instance."""
        if isinstance(err, ValidationError):
            return ToolError(
                code="VALIDATION_ERROR",
                message=str(err),
                retryable=False,
            )
        elif isinstance(err, PathTraversalError):
            return ToolError(
                code="PATH_TRAVERSAL_BLOCKED",
                message=str(err),
                retryable=False,
            )
        elif isinstance(err, PolicyViolationError):
            return ToolError(
                code="POLICY_VIOLATION",
                message=str(err),
                retryable=False,
            )
        elif isinstance(err, FileNotFoundError):
            return ToolError(
                code="FILE_NOT_FOUND",
                message=str(err),
                retryable=False,
            )
        elif isinstance(err, PermissionError):
            return ToolError(
                code="PERMISSION_DENIED",
                message=str(err),
                retryable=False,
            )
        elif isinstance(err, (asyncio.TimeoutError, TimeoutError)):
            return ToolError(
                code="TIMEOUT",
                message=f"Tool execution timed out: {err}",
                retryable=True,
            )
        elif isinstance(err, asyncio.CancelledError):
            return ToolError(
                code="CANCELLED",
                message="Tool execution was explicitly cancelled.",
                retryable=False,
            )
        else:
            return ToolError(
                code="EXECUTION_ERROR",
                message=f"Unexpected error ({type(err).__name__}): {err}",
                retryable=True,
                details={"exception_type": type(err).__name__},
            )
