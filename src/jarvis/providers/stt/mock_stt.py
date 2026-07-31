"""
MockSTT provider for fast, reproducible unit testing without model inference.
"""

import asyncio
from typing import Optional
from jarvis.core.base import ServiceStatus, HealthStatus
from jarvis.core.config.schema import AppConfig
from jarvis.providers.base import STTProtocol
from jarvis.providers.registry import register_provider


@register_provider("stt", "mock")
class MockSTT(STTProtocol):
    """Synthetic STT provider returning pre-configured transcripts."""

    @classmethod
    def from_config(cls, config: AppConfig) -> "MockSTT":
        return cls()

    def __init__(self, response_text: str = "Hello Jarvis, how are you?") -> None:
        self.response_text = response_text
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED

    async def transcribe(self, pcm_data: bytes, sample_rate: int = 16000) -> str:
        # Simulate slight STT latency
        await asyncio.sleep(0.05)
        return self.response_text

    async def initialize(self) -> bool:
        self._status = ServiceStatus.RUNNING
        return True

    async def health(self) -> HealthStatus:
        return HealthStatus(status=self._status, message="Mock STT running")

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        pass
