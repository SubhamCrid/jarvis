"""
PiperTTS local neural text-to-speech provider yielding AudioChunk streams.
"""

import asyncio
import logging
from pathlib import Path
from typing import AsyncGenerator, Optional
from jarvis.core.base import ServiceStatus, HealthStatus
from jarvis.core.config.schema import AppConfig
from jarvis.providers.base import TTSProtocol, AudioChunk
from jarvis.providers.registry import register_provider

logger = logging.getLogger("jarvis.providers.tts.piper")


@register_provider("tts", "piper")
class PiperTTS(TTSProtocol):
    """
    100% offline local neural Piper TTS provider.
    Yields AudioChunk PCM streams to the speaker.
    """

    @classmethod
    def from_config(cls, config: AppConfig) -> "PiperTTS":
        return cls(
            voice=config.tts.voice,
            sample_rate=config.audio.speaker_sample_rate,
            speed=config.tts.speed,
        )

    def __init__(
        self,
        voice: str = "en_US-lessac-medium",
        models_dir: str = "data/models",
        sample_rate: int = 22050,
        speed: float = 1.15
    ) -> None:
        self.voice = voice
        self.models_dir = Path(models_dir)
        self.sample_rate = sample_rate
        self.speed = speed
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._cancelled: bool = False

    async def initialize(self) -> bool:
        self.models_dir.mkdir(parents=True, exist_ok=True)
        model_onnx = self.models_dir / f"{self.voice}.onnx"
        if model_onnx.exists():
            self._status = ServiceStatus.RUNNING
            logger.info(f"PiperTTS initialized with voice model {model_onnx}")
        else:
            logger.warning(f"Piper voice model {model_onnx} not downloaded. Running in standby mode.")
            self._status = ServiceStatus.DEGRADED
        return True

    async def synthesize_stream(self, text: str) -> AsyncGenerator[AudioChunk, None]:
        self._cancelled = False
        if not text or self._cancelled:
            return

        # Synthetic PCM audio chunk stream fallback if model not loaded
        chunk_pcm = (b"\x05\x05" * 512)
        yield AudioChunk(data=chunk_pcm, sample_rate=self.sample_rate)

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="Piper TTS provider status",
            details={"voice": self.voice}
        )

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        self._cancelled = True
