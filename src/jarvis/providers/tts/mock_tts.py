"""
MockTTS provider for fast testing without speech synthesis hardware/binary dependencies.
"""

import asyncio
from typing import AsyncGenerator
from vidya.core.base import ServiceStatus, HealthStatus
from vidya.core.config.schema import AppConfig
from vidya.providers.base import TTSProtocol, AudioChunk
from vidya.providers.registry import register_provider


@register_provider("tts", "mock")
class MockTTS(TTSProtocol):
    """Synthetic TTS provider yielding AudioChunk objects."""

    @classmethod
    def from_config(cls, config: AppConfig) -> "MockTTS":
        return cls(sample_rate=config.audio.speaker_sample_rate)

    def __init__(self, sample_rate: int = 22050) -> None:
        self.sample_rate = sample_rate
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._cancelled: bool = False

    async def initialize(self) -> bool:
        self._status = ServiceStatus.RUNNING
        self._cancelled = False
        return True

    async def synthesize_stream(self, text: str) -> AsyncGenerator[AudioChunk, None]:
        self._cancelled = False
        if not text:
            return

        # Generate 2 synthetic audio chunks for the text
        for i in range(2):
            if self._cancelled:
                break
            await asyncio.sleep(0.03)  # Simulate TTFA and synthesis latency
            dummy_pcm = (b"\x00\x10\x00\x20" * 256)
            yield AudioChunk(data=dummy_pcm, sample_rate=self.sample_rate)

    async def health(self) -> HealthStatus:
        return HealthStatus(status=self._status, message="Mock TTS active")

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        self._cancelled = True
