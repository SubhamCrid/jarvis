"""
ChatterboxTTS local neural text-to-speech provider with multilingual synthesis and emotion exaggeration controls.
Supports 23+ languages, zero-shot voice cloning, CFG weight & exaggeration sliders, and optional EdgeTTS fallback mode.
"""

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, Optional
import numpy as np

from jarvis.core.base import ServiceStatus, HealthStatus
from jarvis.core.config.schema import AppConfig
from jarvis.providers.base import TTSProtocol, AudioChunk
from jarvis.providers.registry import register_provider

logger = logging.getLogger("jarvis.providers.tts.chatterbox")


@register_provider("tts", "chatterbox")
class ChatterboxTTS(TTSProtocol):
    """
    Local neural Chatterbox TTS Multilingual provider (Resemble AI).
    Yields PCM AudioChunk streams with tunable CFG weight and emotion exaggeration.
    """

    @classmethod
    def from_config(cls, config: AppConfig) -> "ChatterboxTTS":
        return cls(
            voice=config.tts.voice if config.tts.voice else "en_female",
            sample_rate=config.audio.speaker_sample_rate if config.audio.speaker_sample_rate else 24000,
            speed=config.tts.speed,
            cfg_weight=getattr(config.tts, "cfg_weight", 0.5),
            exaggeration=getattr(config.tts, "exaggeration", 0.5),
            enable_fallback=getattr(config.tts, "enable_fallback", False),
        )

    def __init__(
        self,
        voice: str = "en_female",
        sample_rate: int = 24000,
        speed: float = 1.0,
        cfg_weight: float = 0.5,
        exaggeration: float = 0.5,
        enable_fallback: bool = False,
        device: str = "auto",
    ) -> None:
        self.voice = voice
        self.sample_rate = sample_rate
        self.speed = speed
        self.cfg_weight = cfg_weight
        self.exaggeration = exaggeration
        self.enable_fallback = enable_fallback
        self.device = device

        self._model: Optional[Any] = None
        self._fallback_tts: Optional[Any] = None
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._cancelled: bool = False

    def _infer_language_id(self, text: str) -> str:
        """Infer target language_id ('en', 'hi', 'ja', 'zh', 'fr', 'es', 'de', 'ru', 'ar', etc.) from text script or voice prefix."""
        if not text:
            return "en"

        # Script based detection
        if any('\u0900' <= char <= '\u097F' for char in text):
            return "hi"
        if any('\u3040' <= char <= '\u30FF' or '\u31F0' <= char <= '\u31FF' for char in text):
            return "ja"
        if any('\u4E00' <= char <= '\u9FFF' for char in text):
            return "zh"
        if any('\u0400' <= char <= '\u04FF' for char in text):
            return "ru"
        if any('\u0600' <= char <= '\u06FF' for char in text):
            return "ar"

        # Voice prefix based detection
        v_lower = self.voice.lower()
        if v_lower.startswith("hi"):
            return "hi"
        elif v_lower.startswith("ja"):
            return "ja"
        elif v_lower.startswith("zh"):
            return "zh"
        elif v_lower.startswith("fr"):
            return "fr"
        elif v_lower.startswith("es"):
            return "es"
        elif v_lower.startswith("de"):
            return "de"
        elif v_lower.startswith("ru"):
            return "ru"
        elif v_lower.startswith("ar"):
            return "ar"

        return "en"

    def _determine_device(self) -> str:
        if self.device != "auto":
            return self.device
        try:
            import torch  # type: ignore
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    async def initialize(self) -> bool:
        """Initialize Chatterbox Multilingual TTS model or fallback mode if enabled."""
        try:
            target_device = self._determine_device()
            loop = asyncio.get_running_loop()

            def _load():
                try:
                    from chatterbox.mtl_tts import ChatterboxMultilingualTTS  # type: ignore
                    return ChatterboxMultilingualTTS.from_pretrained(device=target_device)
                except ImportError:
                    from chatterbox.tts import ChatterboxTTS as PyChatterboxTTS  # type: ignore
                    return PyChatterboxTTS.from_pretrained(device=target_device)

            self._model = await loop.run_in_executor(None, _load)
            if hasattr(self._model, "sr") and self._model.sr:
                self.sample_rate = int(self._model.sr)
            self._status = ServiceStatus.RUNNING
            logger.info(f"ChatterboxTTS initialized on {target_device} (voice: {self.voice}, speed: {self.speed}x, cfg_weight: {self.cfg_weight}, exaggeration: {self.exaggeration})")
            return True
        except Exception as e:
            logger.warning(f"Chatterbox package/weights not loaded ({e}).")
            self._status = ServiceStatus.DEGRADED
            if self.enable_fallback:
                logger.info("Initializing EdgeTTS fallback mode for ChatterboxTTS.")
                try:
                    from jarvis.providers.tts.edge_tts_provider import EdgeTTSProvider
                    self._fallback_tts = EdgeTTSProvider(speed=self.speed)
                    await self._fallback_tts.initialize()
                except Exception as fb_err:
                    logger.error(f"Fallback EdgeTTS init failed: {fb_err}")
            else:
                logger.info("TTS Fallback is disabled. Running ChatterboxTTS without fallback engine.")
            return False

    async def synthesize_stream(self, text: str) -> AsyncGenerator[AudioChunk, None]:
        """Synthesize text into PCM audio chunk stream using Chatterbox or fallback."""
        self._cancelled = False
        if not text or self._cancelled:
            return

        lang_id = self._infer_language_id(text)

        if self._status == ServiceStatus.RUNNING and self._model is not None:
            try:
                loop = asyncio.get_running_loop()

                def _generate():
                    kwargs: Dict[str, Any] = {}
                    if hasattr(self._model, "generate"):
                        import inspect
                        sig = inspect.signature(self._model.generate)
                        if "language_id" in sig.parameters:
                            kwargs["language_id"] = lang_id
                        if "cfg_weight" in sig.parameters:
                            kwargs["cfg_weight"] = self.cfg_weight
                        if "exaggeration" in sig.parameters:
                            kwargs["exaggeration"] = self.exaggeration
                        return self._model.generate(text, **kwargs)
                    return None

                raw_audio = await loop.run_in_executor(None, _generate)

                if raw_audio is not None and not self._cancelled:
                    # Convert tensor/ndarray float audio to 16-bit LE PCM
                    if hasattr(raw_audio, "cpu"):
                        raw_audio = raw_audio.cpu().numpy()
                    if hasattr(raw_audio, "squeeze"):
                        raw_audio = raw_audio.squeeze()

                    audio_arr = np.asarray(raw_audio, dtype=np.float32)
                    # Normalize audio amplitude
                    max_val = np.max(np.abs(audio_arr))
                    if max_val > 0:
                        audio_arr = audio_arr / max_val
                    pcm_data = (audio_arr * 32767.0).astype(np.int16).tobytes()

                    # Stream PCM audio in 2048-byte chunks (~46ms per chunk at 24kHz)
                    chunk_size = 2048
                    for i in range(0, len(pcm_data), chunk_size):
                        if self._cancelled:
                            break
                        chunk = pcm_data[i:i + chunk_size]
                        yield AudioChunk(data=chunk, sample_rate=self.sample_rate)
                    return
            except Exception as err:
                logger.error(f"ChatterboxTTS synthesis failed: {err}")

        # Fallback handling
        if self._fallback_tts is not None and not self._cancelled:
            async for chunk in self._fallback_tts.synthesize_stream(text):
                if self._cancelled:
                    break
                yield chunk
        elif self._status != ServiceStatus.RUNNING:
            logger.warning("ChatterboxTTS is degraded and fallback is disabled; outputting silent standby chunk.")
            chunk_pcm = b"\x00\x00" * 512
            yield AudioChunk(data=chunk_pcm, sample_rate=self.sample_rate)

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="Chatterbox TTS provider status",
            details={
                "voice": self.voice,
                "cfg_weight": self.cfg_weight,
                "exaggeration": self.exaggeration,
                "enable_fallback": self.enable_fallback,
                "fallback_active": self._fallback_tts is not None,
            }
        )

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED
        self._model = None
        if self._fallback_tts and hasattr(self._fallback_tts, "shutdown"):
            await self._fallback_tts.shutdown()

    async def cancel(self) -> None:
        self._cancelled = True
        if self._fallback_tts and hasattr(self._fallback_tts, "cancel"):
            await self._fallback_tts.cancel()
