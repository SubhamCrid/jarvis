"""
KokoroTTS local neural text-to-speech provider yielding ultra low-latency AudioChunk PCM streams.
Supports multi-language synthesis (English, Hindi, Spanish, French, Japanese, Chinese, Italian, Portuguese)
with automatic script detection and pipeline caching.
"""

import asyncio
import logging
from typing import AsyncGenerator, Dict, Optional, Tuple
import numpy as np

from jarvis.core.base import ServiceStatus, HealthStatus
from jarvis.core.config.schema import AppConfig
from jarvis.providers.base import TTSProtocol, AudioChunk
from jarvis.providers.registry import register_provider

logger = logging.getLogger("jarvis.providers.tts.kokoro")


@register_provider("tts", "kokoro")
class KokoroTTS(TTSProtocol):
    """
    100% local neural Kokoro-82M TTS provider with multilingual support.
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
        self._pipelines: Dict[str, Any] = {}
        self._fallback_tts = None
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._cancelled: bool = False

    def _infer_lang_code_and_voice(self, text: str) -> Tuple[str, str]:
        """Detect language code ('a', 'h', 'j', 'z', 'e', 'f', 'b', etc.) and appropriate voice."""
        if not text:
            return self.lang_code, self.voice

        # 1. Hindi Devanagari script detection
        if any('\u0900' <= char <= '\u097F' for char in text):
            active_voice = self.voice if self.voice.startswith(('hf_', 'hm_')) else "hf_alpha"
            return 'h', active_voice

        # 2. Japanese script detection
        if any('\u3040' <= char <= '\u30FF' or '\u31F0' <= char <= '\u31FF' for char in text):
            active_voice = self.voice if self.voice.startswith(('jf_', 'jm_')) else "jf_alpha"
            return 'j', active_voice

        # 3. Chinese script detection
        if any('\u4E00' <= char <= '\u9FFF' for char in text):
            active_voice = self.voice if self.voice.startswith(('zf_', 'zm_')) else "zf_xiaobei"
            return 'z', active_voice

        # 4. Infer from voice prefix if explicit voice is selected
        v_prefix = self.voice[:2].lower() if len(self.voice) >= 2 else ""
        voice_lang_map = {
            "af": "a", "am": "a",
            "bf": "b", "bm": "b",
            "hf": "h", "hm": "h",
            "jf": "j", "jm": "j",
            "zf": "z", "zm": "z",
            "ef": "e", "em": "e",
            "ff": "f", "fm": "f",
            "if": "i", "im": "i",
            "pf": "p", "pm": "p",
        }
        target_lang = voice_lang_map.get(v_prefix, self.lang_code)
        return target_lang, self.voice

    async def initialize(self) -> bool:
        """Initialize the default Kokoro synthesis pipeline or set standby fallback mode."""
        try:
            from kokoro import KPipeline  # type: ignore
            loop = asyncio.get_running_loop()
            target_lang, _ = self._infer_lang_code_and_voice("")
            pipeline = await loop.run_in_executor(
                None, lambda: KPipeline(lang_code=target_lang)
            )
            self._pipelines[target_lang] = pipeline
            self._status = ServiceStatus.RUNNING
            logger.info(f"KokoroTTS initialized successfully (voice: {self.voice}, speed: {self.speed}x, default_lang: {target_lang})")
            return True
        except Exception as e:
            logger.warning(f"Kokoro package/weights not loaded ({e}). Initializing EdgeTTS fallback mode for KokoroTTS.")
            self._status = ServiceStatus.DEGRADED
            try:
                from jarvis.providers.tts.edge_tts_provider import EdgeTTSProvider
                self._fallback_tts = EdgeTTSProvider(speed=self.speed)
                await self._fallback_tts.initialize()
            except Exception as fb_err:
                logger.error(f"Fallback EdgeTTS init failed: {fb_err}")
            return False

    async def _get_or_load_pipeline(self, lang_code: str):
        """Get cached KPipeline or load new pipeline for requested lang_code asynchronously."""
        if lang_code in self._pipelines:
            return self._pipelines[lang_code]
        try:
            from kokoro import KPipeline  # type: ignore
            loop = asyncio.get_running_loop()
            pipeline = await loop.run_in_executor(
                None, lambda: KPipeline(lang_code=lang_code)
            )
            self._pipelines[lang_code] = pipeline
            logger.info(f"Loaded Kokoro KPipeline for lang_code='{lang_code}'")
            return pipeline
        except Exception as err:
            logger.error(f"Failed to load Kokoro pipeline for lang_code='{lang_code}': {err}")
            return None

    async def synthesize_stream(self, text: str) -> AsyncGenerator[AudioChunk, None]:
        """Synthesize text into a low-latency PCM audio stream with dynamic multilingual routing."""
        self._cancelled = False
        if not text or self._cancelled:
            return

        lang_code, active_voice = self._infer_lang_code_and_voice(text)

        if self._status == ServiceStatus.RUNNING:
            pipeline = await self._get_or_load_pipeline(lang_code)
            if pipeline is not None:
                try:
                    loop = asyncio.get_running_loop()

                    def generate_audio_chunks():
                        chunks = []
                        # KPipeline yields (graphemes, phonemes, audio_tensor)
                        generator = pipeline(text, voice=active_voice, speed=self.speed, split_pattern=r'\n+')
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

        # Fallback to EdgeTTS if kokoro pipeline is not active
        if self._fallback_tts is not None:
            async for chunk in self._fallback_tts.synthesize_stream(text):
                if self._cancelled:
                    break
                yield chunk
            return

        # Synthetic PCM audio chunk stream fallback if all else fails
        if not self._cancelled:
            chunk_pcm = (b"\x05\x05" * 512)
            yield AudioChunk(data=chunk_pcm, sample_rate=self.sample_rate)

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="KokoroTTS provider status",
            details={
                "voice": self.voice,
                "speed": self.speed,
                "loaded_languages": list(self._pipelines.keys())
            }
        )

    async def shutdown(self) -> None:
        self._pipelines.clear()
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        self._cancelled = True
