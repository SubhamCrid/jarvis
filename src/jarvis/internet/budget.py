"""
Thread-safe ExecutionBudget for resource accounting across pipeline stages.
Tracks RAM bytes, Token counts, RPS, and Browser page contexts.
"""

import asyncio
from jarvis.internet.exceptions import ResourceExhaustedError


class ExecutionBudget:
    """
    Shared, thread-safe budget object passed into pipeline stages to prevent resource exhaustion.
    """

    def __init__(
        self,
        max_tokens: int = 2048,
        max_bytes: int = 524288,
        timeout_sec: float = 10.0,
        max_requests: int = 5,
        max_browser_contexts: int = 1,
    ) -> None:
        self.max_tokens = max_tokens
        self.remaining_tokens = max_tokens

        self.max_bytes = max_bytes
        self.remaining_bytes = max_bytes

        self.timeout_sec = timeout_sec

        self.max_requests = max_requests
        self.remaining_requests = max_requests

        self.max_browser_contexts = max_browser_contexts
        self.remaining_browser_contexts = max_browser_contexts

        self._lock = asyncio.Lock()

    async def consume_tokens(self, num_tokens: int) -> None:
        async with self._lock:
            if num_tokens > self.remaining_tokens:
                raise ResourceExhaustedError(
                    f"Token budget exhausted ({num_tokens} requested, {self.remaining_tokens} remaining)."
                )
            self.remaining_tokens -= num_tokens

    async def consume_bytes(self, num_bytes: int) -> None:
        async with self._lock:
            if num_bytes > self.remaining_bytes:
                raise ResourceExhaustedError(
                    f"Byte payload budget exhausted ({num_bytes} requested, {self.remaining_bytes} remaining)."
                )
            self.remaining_bytes -= num_bytes

    async def consume_request(self) -> None:
        async with self._lock:
            if self.remaining_requests <= 0:
                raise ResourceExhaustedError("Maximum concurrent requests limit reached.")
            self.remaining_requests -= 1

    async def consume_browser_context(self) -> None:
        async with self._lock:
            if self.remaining_browser_contexts <= 0:
                raise ResourceExhaustedError("Maximum concurrent browser contexts limit reached.")
            self.remaining_browser_contexts -= 1
