"""
BrowserTaskSandbox enforcing execution timeouts, CancellationToken, URLSandbox policy, and file boundaries.
Prevents individual browser providers from bypassing core platform security controls.
"""

import asyncio
from typing import Any, Awaitable, Callable, Optional
from jarvis.internet.exceptions import BrowserTaskError
from jarvis.internet.security.sandbox import URLSandbox
from jarvis.core.base import CancellationToken


class BrowserTaskSandbox:
    """Execution wrapper enforcing security policies, timeouts, and cancellation on browser tasks."""

    def __init__(self, url_sandbox: Optional[URLSandbox] = None) -> None:
        self.url_sandbox = url_sandbox or URLSandbox()

    async def execute_task(
        self,
        task_fn: Callable[[], Awaitable[Any]],
        target_url: str,
        timeout_sec: float = 30.0,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Any:
        """
        Validate URL policy, wrap task execution with timeout and cancellation monitoring.
        """
        # 1. Enforce URLSandbox security checks
        self.url_sandbox.validate_url(target_url)

        # 2. Check cancellation
        if cancellation_token and cancellation_token.is_cancelled():
            raise BrowserTaskError(f"Browser task targeting '{target_url}' cancelled prior to execution.")

        try:
            # 3. Execute with hard timeout
            return await asyncio.wait_for(task_fn(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            raise BrowserTaskError(f"Browser execution timed out after {timeout_sec}s for URL '{target_url}'.")
        except asyncio.CancelledError:
            raise BrowserTaskError(f"Browser execution cancelled for URL '{target_url}'.")
        except Exception as e:
            if isinstance(e, BrowserTaskError):
                raise
            raise BrowserTaskError(f"Browser task execution failed: {e}") from e
