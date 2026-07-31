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
            mp3_buffer = bytearray()
            async for chunk in communicate.stream():
                if self._cancelled:
                    logger.info("EdgeTTS synthesis stream cancelled.")
                    break
                if chunk["type"] == "audio" and chunk["data"]:
                    mp3_buffer.extend(chunk["data"])

            if mp3_buffer and not self._cancelled:
                # Decode MP3 to 16-bit LE PCM via ffmpeg
                import subprocess
                try:
                    p = subprocess.Popen(
                        ['ffmpeg', '-i', 'pipe:0', '-f', 's16le', '-ac', '1', '-ar', str(self.sample_rate), 'pipe:1'],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL
                    )
                    pcm_data, _ = p.communicate(input=bytes(mp3_buffer))
                    if pcm_data:
                        # Chunk PCM data into 4096-byte blocks
                        chunk_size = 4096
                        for i in range(0, len(pcm_data), chunk_size):
                            if self._cancelled:
                                break
                            block = pcm_data[i:i + chunk_size]
                            yield AudioChunk(data=block, sample_rate=self.sample_rate)
                except Exception as ff_err:
                    logger.warning(f"ffmpeg PCM decoding failed, yielding raw MP3 chunks: {ff_err}")
                    yield AudioChunk(data=bytes(mp3_buffer), sample_rate=self.sample_rate)

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
