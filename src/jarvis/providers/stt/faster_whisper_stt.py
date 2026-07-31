"""
Faster-Whisper STT provider using CTranslate2 for ultra-fast local transcription.
"""

import io
import asyncio
import logging
import numpy as np
from pathlib import Path
from typing import Optional

from jarvis.core.base import HealthStatus, ServiceStatus
from jarvis.core.config.schema import AppConfig
from jarvis.providers.base import STTProtocol
from jarvis.providers.registry import register_provider

logger = logging.getLogger("jarvis.providers.stt.faster_whisper")


@register_provider("stt", "faster_whisper")
class FasterWhisperSTT(STTProtocol):
    """
    Local Faster-Whisper STT provider powered by CTranslate2.
    Optimized for low VRAM and CPU/CUDA inference.
    """

    @classmethod
    def from_config(cls, config: AppConfig) -> "FasterWhisperSTT":
        return cls(
            model=config.stt.model,
            language=config.stt.language,
            device=config.stt.device if hasattr(config.stt, "device") else "auto",
            compute_type=config.stt.compute_type if hasattr(config.stt, "compute_type") else "int8",
        )

    def __init__(
        self,
        model: str = "base",
        language: Optional[str] = "auto",
        device: str = "cpu",
        compute_type: str = "int8"
    ) -> None:
        self.model = model
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._fw_model = None

    async def initialize(self) -> bool:
        try:
            from faster_whisper import WhisperModel  # type: ignore
            loop = asyncio.get_running_loop()
            
            logger.info(f"Loading Faster-Whisper model '{self.model}' on {self.device} ({self.compute_type})...")
            def _load():
                try:
                    m = WhisperModel(self.model, device=self.device, compute_type=self.compute_type)
                    # Warm-up dry run to verify CUDA / CTranslate2 libraries load
                    dummy = np.zeros(1600, dtype=np.float32)
                    list(m.transcribe(dummy, beam_size=1)[0])
                    return m
                except Exception as cuda_err:
                    if self.device != "cpu":
                        logger.warning(
                            f"FasterWhisper failed on '{self.device}' ({cuda_err}). Falling back to 'cpu'."
                        )
                        self.device = "cpu"
                        self.compute_type = "int8"
                        m_cpu = WhisperModel(self.model, device="cpu", compute_type="int8")
                        dummy = np.zeros(1600, dtype=np.float32)
                        list(m_cpu.transcribe(dummy, beam_size=1)[0])
                        return m_cpu
                    raise

            self._fw_model = await loop.run_in_executor(None, _load)
            self._status = ServiceStatus.RUNNING
            logger.info(f"FasterWhisperSTT initialized successfully with model '{self.model}' on {self.device}.")
            return True
        except ImportError:
            logger.warning("faster-whisper package not installed.")
            self._status = ServiceStatus.ERROR
            return False
        except Exception as e:
            logger.error(f"Error loading faster-whisper model: {e}")
            self._status = ServiceStatus.ERROR
            return False

    async def transcribe(self, pcm_data: bytes, sample_rate: int = 16000) -> str:
        if not pcm_data or len(pcm_data) < 3200:  # Ignore tiny clicks (<0.1s)
            return ""

        # Convert 16-bit PCM bytes to float32 numpy array [-1.0, 1.0]
        try:
            audio_np = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
        except Exception as conv_err:
            logger.error(f"Error converting PCM data to float32 numpy array: {conv_err}")
            return ""

        if self._fw_model:
            try:
                loop = asyncio.get_running_loop()
                def _run_transcribe():
                    lang = None if self.language in ("auto", None, "", "Auto") else self.language
                    segments, _ = self._fw_model.transcribe(audio_np, beam_size=2, language=lang)
                    return " ".join([seg.text for seg in segments]).strip()

                text = await loop.run_in_executor(None, _run_transcribe)
                if text:
                    logger.info(f"FasterWhisper STT transcribed: '{text}'")
                    return text
            except Exception as e:
                logger.error(f"Error during FasterWhisper transcription on {self.device}: {e}")
                if self.device != "cpu":
                    logger.warning("Attempting emergency CPU fallback for FasterWhisper...")
                    try:
                        from faster_whisper import WhisperModel  # type: ignore
                        self.device = "cpu"
                        self.compute_type = "int8"
                        self._fw_model = WhisperModel(self.model, device="cpu", compute_type="int8")
                        segments, _ = self._fw_model.transcribe(audio_np, beam_size=2, language=None)
                        text = " ".join([seg.text for seg in segments]).strip()
                        if text:
                            logger.info(f"FasterWhisper CPU fallback transcribed: '{text}'")
                            return text
                    except Exception as fallback_err:
                        logger.error(f"FasterWhisper CPU fallback also failed: {fallback_err}")

        logger.debug("FasterWhisper returned empty transcript.")
        return ""

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="FasterWhisper STT provider status",
            details={"model": self.model, "device": self.device}
        )

    async def shutdown(self) -> None:
        self._fw_model = None
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        pass
