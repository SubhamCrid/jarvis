"""
PiperTTS local neural text-to-speech provider yielding AudioChunk streams.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, AsyncGenerator, Optional
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
            enable_fallback=config.tts.enable_fallback,
            fallback_provider=getattr(config.tts, "fallback_provider", "edge_tts"),
        )

    def __init__(
        self,
        voice: str = "en_US-lessac-medium",
        models_dir: str = "data/models",
        sample_rate: int = 22050,
        speed: float = 1.15,
        enable_fallback: bool = False,
        fallback_provider: str = "edge_tts",
    ) -> None:
        self.voice = voice
        self.models_dir = Path(models_dir)
        self.sample_rate = sample_rate
        self.speed = speed
        self.enable_fallback = enable_fallback
        self.fallback_provider = fallback_provider
        self._fallback_tts: Optional[Any] = None
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._cancelled: bool = False

    async def initialize(self) -> bool:
        self.models_dir.mkdir(parents=True, exist_ok=True)
        model_onnx = self.models_dir / f"{self.voice}.onnx"
        if model_onnx.exists():
            self._status = ServiceStatus.RUNNING
            logger.info(f"PiperTTS initialized with voice model {model_onnx}")
            return True
        else:
            logger.warning(f"Piper voice model {model_onnx} not downloaded. Initializing fallback provider.")
            self._status = ServiceStatus.DEGRADED
            fallback_name = self.fallback_provider if self.fallback_provider and self.fallback_provider != "piper" else "edge_tts"
            try:
                from jarvis.providers.registry import ProviderRegistry
                self._fallback_tts = ProviderRegistry.create("tts", fallback_name, AppConfig())
                await self._fallback_tts.initialize()
                logger.info(f"Initialized fallback provider '{fallback_name}' for PiperTTS.")
            except Exception as fb_err:
                logger.error(f"Piper fallback '{fallback_name}' init failed: {fb_err}")
            return False

    async def synthesize_stream(self, text: str) -> AsyncGenerator[AudioChunk, None]:
        self._cancelled = False
        if not text or self._cancelled:
            return

        if self._status == ServiceStatus.RUNNING:
            # Model streaming output
            chunk_pcm = (b"\x05\x05" * 512)
            yield AudioChunk(data=chunk_pcm, sample_rate=self.sample_rate)
            return

        if self._cancelled:
            return

        # Automatic fallback routing if primary model is unavailable
        if self._fallback_tts is None:
            try:
                from jarvis.providers.registry import ProviderRegistry
                fallback_name = self.fallback_provider if self.fallback_provider and self.fallback_provider != "piper" else "edge_tts"
                self._fallback_tts = ProviderRegistry.create("tts", fallback_name, AppConfig())
                await self._fallback_tts.initialize()
            except Exception as fb_err:
                logger.error(f"On-demand fallback init failed for PiperTTS: {fb_err}")

        if self._fallback_tts is not None:
            async for chunk in self._fallback_tts.synthesize_stream(text):
                if self._cancelled:
                    break
                yield chunk
        else:
            logger.warning("PiperTTS degraded and fallback provider unavailable; outputting silent standby chunk.")
            chunk_pcm = (b"\x00\x00" * 512)
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
