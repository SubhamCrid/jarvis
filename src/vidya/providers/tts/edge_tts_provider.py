"""
EdgeTTS provider for natural, free online streaming speech synthesis.
"""

import asyncio
import logging
from typing import AsyncGenerator
from vidya.core.base import ServiceStatus, HealthStatus
from vidya.providers.base import TTSProtocol, AudioChunk

logger = logging.getLogger("vidya.providers.tts.edge_tts")


class EdgeTTSProvider(TTSProtocol):
    """
    Microsoft Edge TTS provider using free neural voices.
    Yields MP3/PCM AudioChunk streams.
    """

    def __init__(self, voice: str = "en-US-AvaNeural", sample_rate: int = 24000) -> None:
        self.voice = voice
        self.sample_rate = sample_rate
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._cancelled: bool = False

    async def initialize(self) -> bool:
        try:
            import edge_tts  # type: ignore
            self._edge_tts = edge_tts
            self._status = ServiceStatus.RUNNING
            logger.info(f"EdgeTTSProvider initialized with voice {self.voice}")
            return True
        except ImportError:
            logger.warning("edge-tts package not found. Degrading status.")
            self._status = ServiceStatus.DEGRADED
            return False

    async def synthesize_stream(self, text: str) -> AsyncGenerator[AudioChunk, None]:
        self._cancelled = False
        if not text or self._cancelled:
            return

        try:
            communicate = self._edge_tts.Communicate(text, self.voice)
            async for chunk in communicate.stream():
                if self._cancelled:
                    logger.info("EdgeTTS synthesis stream cancelled.")
                    break
                if chunk["type"] == "audio" and chunk["data"]:
                    yield AudioChunk(data=chunk["data"], sample_rate=self.sample_rate)
        except asyncio.CancelledError:
            self._cancelled = True
            raise
        except Exception as e:
            logger.error(f"Error in EdgeTTS synthesis: {e}")

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="EdgeTTS provider status",
            details={"voice": self.voice}
        )

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        self._cancelled = True
