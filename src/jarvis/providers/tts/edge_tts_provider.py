"""
EdgeTTS provider for natural, free online streaming speech synthesis.
"""

import asyncio
import logging
from typing import Any, AsyncGenerator, Optional
from jarvis.core.base import ServiceStatus, HealthStatus
from jarvis.core.config.schema import AppConfig
from jarvis.providers.base import TTSProtocol, AudioChunk
from jarvis.providers.registry import register_provider

logger = logging.getLogger("jarvis.providers.tts.edge_tts")


@register_provider("tts", "edge_tts")
class EdgeTTSProvider(TTSProtocol):
    """
    Microsoft Edge TTS provider using free neural voices.
    Yields MP3/PCM AudioChunk streams.
    """

    @classmethod
    def from_config(cls, config: AppConfig) -> "EdgeTTSProvider":
        return cls(
            voice=config.tts.voice,
            sample_rate=config.audio.speaker_sample_rate,
            speed=config.tts.speed,
            auto_switch_voice=config.tts.auto_switch_voice,
            enable_fallback=config.tts.enable_fallback,
            fallback_provider=getattr(config.tts, "fallback_provider", "mock"),
        )

    def __init__(
        self,
        voice: str = "en-US-AvaMultilingualNeural",
        sample_rate: int = 24000,
        speed: float = 1.15,
        auto_switch_voice: bool = False,
        enable_fallback: bool = False,
        fallback_provider: str = "mock",
    ) -> None:
        self.voice = voice
        self.sample_rate = sample_rate
        self.speed = speed
        self.auto_switch_voice = auto_switch_voice
        self.enable_fallback = enable_fallback
        self.fallback_provider = fallback_provider
        self._fallback_tts: Optional[Any] = None
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._cancelled: bool = False

    def _get_rate_str(self) -> str:
        """Format speed float (e.g. 1.25) into EdgeTTS rate string (e.g. '+25%')."""
        pct = int(round((self.speed - 1.0) * 100))
        return f"{pct:+d}%"

    def _select_voice_for_text(self, text: str) -> str:
        """Select appropriate voice based on text script if auto_switch_voice is enabled."""
        if not self.auto_switch_voice or not text:
            return self.voice
        if any('\u0900' <= char <= '\u097F' for char in text):
            return "hi-IN-SwaraNeural"
        return self.voice

    async def initialize(self) -> bool:
        try:
            import edge_tts  # type: ignore
            self._edge_tts = edge_tts
            self._status = ServiceStatus.RUNNING
            logger.info(f"EdgeTTSProvider initialized (voice: {self.voice}, speed: {self.speed}x, rate: {self._get_rate_str()})")
            return True
        except ImportError:
            logger.warning("edge-tts package not found. Degrading status.")
            self._status = ServiceStatus.DEGRADED
            if self.enable_fallback and self.fallback_provider and self.fallback_provider != "edge_tts":
                try:
                    from jarvis.providers.registry import ProviderRegistry
                    self._fallback_tts = ProviderRegistry.create("tts", self.fallback_provider, AppConfig())
                    await self._fallback_tts.initialize()
                except Exception as fb_err:
                    logger.error(f"EdgeTTS fallback '{self.fallback_provider}' init failed: {fb_err}")
            return False

    async def synthesize_stream(self, text: str) -> AsyncGenerator[AudioChunk, None]:
        self._cancelled = False
        if not text or self._cancelled:
            return

        if self._status == ServiceStatus.RUNNING and hasattr(self, "_edge_tts"):
            try:
                active_voice = self._select_voice_for_text(text)
                rate_str = self._get_rate_str()
                communicate = self._edge_tts.Communicate(text, active_voice, rate=rate_str)
                mp3_buffer = bytearray()
                async for chunk in communicate.stream():
                    if self._cancelled:
                        logger.info("EdgeTTS synthesis stream cancelled during downloading.")
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
                        if pcm_data and not self._cancelled:
                            silence_bytes = b"\x00" * int(self.sample_rate * 0.08 * 2)
                            full_pcm = silence_bytes + pcm_data
                            chunk_size = 4096
                            for i in range(0, len(full_pcm), chunk_size):
                                if self._cancelled:
                                    break
                                block = full_pcm[i:i + chunk_size]
                                yield AudioChunk(data=block, sample_rate=self.sample_rate)
                            return
                    except Exception as ff_err:
                        if not self._cancelled:
                            logger.warning(f"ffmpeg PCM decoding failed, yielding raw MP3 chunks: {ff_err}")
                            yield AudioChunk(data=bytes(mp3_buffer), sample_rate=self.sample_rate)
                            return

            except asyncio.CancelledError:
                self._cancelled = True
                raise
            except Exception as e:
                logger.error(f"Error in EdgeTTS synthesis: {e}")

        if self._fallback_tts is not None and not self._cancelled:
            async for chunk in self._fallback_tts.synthesize_stream(text):
                if self._cancelled:
                    break
                yield chunk
        elif self._status != ServiceStatus.RUNNING:
            logger.warning("EdgeTTSProvider is degraded and fallback is disabled; outputting silent standby chunk.")
            chunk_pcm = b"\x00\x00" * 512
            yield AudioChunk(data=chunk_pcm, sample_rate=self.sample_rate)

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="EdgeTTS provider status",
            details={"voice": self.voice, "speed": self.speed}
        )

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        self._cancelled = True
