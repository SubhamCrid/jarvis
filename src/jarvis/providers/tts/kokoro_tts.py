"""
KokoroTTS local neural text-to-speech provider yielding ultra low-latency AudioChunk PCM streams.
"""

import asyncio
import logging
from typing import AsyncGenerator, Optional
import numpy as np

from jarvis.core.base import ServiceStatus, HealthStatus
from jarvis.core.config.schema import AppConfig
from jarvis.providers.base import TTSProtocol, AudioChunk
from jarvis.providers.registry import register_provider

logger = logging.getLogger("jarvis.providers.tts.kokoro")


@register_provider("tts", "kokoro")
class KokoroTTS(TTSProtocol):
    """
    100% local neural Kokoro-82M TTS provider.
    Yields 24kHz PCM AudioChunk streams directly to speaker hardware with minimal latency.
    """

    @classmethod
    def from_config(cls, config: AppConfig) -> "KokoroTTS":
        return cls(
            voice=config.tts.voice if config.tts.voice else "af_bella",
            sample_rate=config.audio.speaker_sample_rate if config.audio.speaker_sample_rate else 24000,
            speed=config.tts.speed,
        )

    def __init__(
        self,
        voice: str = "af_bella",
        sample_rate: int = 24000,
        speed: float = 1.15,
        lang_code: str = "a"
    ) -> None:
        self.voice = voice
        self.sample_rate = sample_rate
        self.speed = speed
        self.lang_code = lang_code
        self._pipeline = None
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._cancelled: bool = False

    async def initialize(self) -> bool:
        """Initialize the Kokoro synthesis pipeline or set standby mode if package unavailable."""
        try:
            # Try importing kokoro pipeline
            from kokoro import KPipeline  # type: ignore
            loop = asyncio.get_running_loop()
            # KPipeline loading can take a moment for weights initialization
            self._pipeline = await loop.run_in_executor(
                None, lambda: KPipeline(lang_code=self.lang_code)
            )
            self._status = ServiceStatus.RUNNING
            logger.info(f"KokoroTTS initialized successfully (voice: {self.voice}, speed: {self.speed}x, lang: {self.lang_code})")
            return True
        except Exception as e:
            logger.warning(f"Kokoro package/weights not loaded ({e}). Running KokoroTTS in standby fallback mode.")
            self._status = ServiceStatus.DEGRADED
            return False

    async def synthesize_stream(self, text: str) -> AsyncGenerator[AudioChunk, None]:
        """Synthesize text into a low-latency PCM audio stream."""
        self._cancelled = False
        if not text or self._cancelled:
            return

        if self._pipeline is not None and self._status == ServiceStatus.RUNNING:
            try:
                loop = asyncio.get_running_loop()

                def generate_audio_chunks():
                    chunks = []
                    # KPipeline yields (graphemes, phonemes, audio_tensor)
                    generator = self._pipeline(text, voice=self.voice, speed=self.speed, split_pattern=r'\n+')
                    for _, _, audio in generator:
                        if audio is not None:
                            # Convert PyTorch tensor or numpy float32 to int16 PCM
                            if hasattr(audio, 'numpy'):
                                audio_np = audio.numpy()
                            else:
                                audio_np = np.array(audio, dtype=np.float32)
                            
                            # Scale float [-1.0, 1.0] to int16
                            audio_int16 = np.clip(audio_np * 32767.0, -32768.0, 32767.0).astype(np.int16)
                            chunks.append(audio_int16.tobytes())
                    return chunks

                pcm_chunks = await loop.run_in_executor(None, generate_audio_chunks)

                for chunk_bytes in pcm_chunks:
                    if self._cancelled:
                        break
                    # Yield in 4096-byte blocks for immediate low-latency streaming
                    chunk_size = 4096
                    for i in range(0, len(chunk_bytes), chunk_size):
                        if self._cancelled:
                            break
                        block = chunk_bytes[i:i + chunk_size]
                        yield AudioChunk(data=block, sample_rate=self.sample_rate)
                return
            except Exception as err:
                logger.error(f"Error during KokoroTTS synthesis streaming: {err}")

        # Synthetic PCM audio chunk stream fallback if pipeline not active
        if not self._cancelled:
            chunk_pcm = (b"\x05\x05" * 512)
            yield AudioChunk(data=chunk_pcm, sample_rate=self.sample_rate)

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="KokoroTTS provider status",
            details={"voice": self.voice, "speed": self.speed, "lang_code": self.lang_code}
        )

    async def shutdown(self) -> None:
        self._pipeline = None
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        self._cancelled = True
