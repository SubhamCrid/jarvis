"""
MockLLM provider for unit tests and local execution without active model endpoints.
"""

import asyncio
from typing import AsyncGenerator, Optional, List, Dict
from vidya.core.base import ServiceStatus, HealthStatus
from vidya.providers.base import LLMProtocol


class MockLLM(LLMProtocol):
    """Synthetic LLM provider streaming token chunks."""

    def __init__(self, response: str = "I am Vidya, your local voice assistant. How can I help you today?") -> None:
        self.response = response
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._cancelled: bool = False

    async def initialize(self) -> bool:
        self._status = ServiceStatus.RUNNING
        self._cancelled = False
        return True

    async def generate_stream(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[str, None]:
        self._cancelled = False
        words = self.response.split(" ")
        for i, word in enumerate(words):
            if self._cancelled:
                break
            await asyncio.sleep(0.02)  # Simulate token generation latency
            token = word + (" " if i < len(words) - 1 else "")
            yield token

    async def health(self) -> HealthStatus:
        return HealthStatus(status=self._status, message="Mock LLM active")

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        self._cancelled = True
