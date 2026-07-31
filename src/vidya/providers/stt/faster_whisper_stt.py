"""
Faster-Whisper STT provider using CTranslate2 for ultra-fast local transcription.
"""

import io
import asyncio
import logging
import numpy as np
from pathlib import Path
from typing import Optional
from vidya.core.base import ServiceStatus, HealthStatus
from vidya.providers.base import STTProtocol

logger = logging.getLogger("vidya.providers.stt.faster_whisper")


class FasterWhisperSTT(STTProtocol):
    """
    Local Faster-Whisper STT provider powered by CTranslate2.
    Optimized for low VRAM and CPU/CUDA inference.
    """

    def __init__(
        self,
        model: str = "tiny.en",
        device: str = "cpu",
        compute_type: str = "int8"
    ) -> None:
        self.model = model
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
                return WhisperModel(self.model, device=self.device, compute_type=self.compute_type)

            self._fw_model = await loop.run_in_executor(None, _load)
            self._status = ServiceStatus.RUNNING
            logger.info(f"FasterWhisperSTT initialized successfully with model '{self.model}'.")
            return True
        except ImportError:
            logger.warning("faster-whisper package not installed. Running in degraded mode.")
            self._status = ServiceStatus.DEGRADED
            return True
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
                    segments, _ = self._fw_model.transcribe(audio_np, beam_size=2, language="en")
                    return " ".join([seg.text for seg in segments]).strip()

                text = await loop.run_in_executor(None, _run_transcribe)
                if text:
                    logger.info(f"FasterWhisper STT transcribed: '{text}'")
                    return text
            except Exception as e:
                logger.error(f"Error during FasterWhisper transcription: {e}")

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
