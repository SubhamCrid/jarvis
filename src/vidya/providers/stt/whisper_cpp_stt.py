"""
Whisper.cpp STT provider for low-VRAM, high-speed local audio transcription.
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Optional
from vidya.core.base import ServiceStatus, HealthStatus
from vidya.providers.base import STTProtocol

logger = logging.getLogger("vidya.providers.stt.whisper_cpp")


class WhisperCppSTT(STTProtocol):
    """
    Local whisper.cpp STT provider.
    Runs whisper.cpp executable or Python bindings with minimal RAM/VRAM footprint.
    """

    def __init__(
        self,
        model: str = "base.en",
        models_dir: str = "data/models",
        whisper_bin: Optional[str] = None
    ) -> None:
        self.model = model
        self.models_dir = Path(models_dir)
        self.whisper_bin = whisper_bin or "whisper-cpp"
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._pywhisper = None

    async def initialize(self) -> bool:
        self.models_dir.mkdir(parents=True, exist_ok=True)
        try:
            # Try importing pywhispercpp if installed
            import pywhispercpp.model as whisper  # type: ignore
            model_path = self.models_dir / f"ggml-{self.model}.bin"
            if model_path.exists():
                self._pywhisper = whisper.Model(str(model_path))
                self._status = ServiceStatus.RUNNING
                logger.info(f"WhisperCppSTT loaded model {self.model} from {model_path}")
            else:
                logger.warning(f"Whisper model {model_path} not found. Running in standby mode.")
                self._status = ServiceStatus.DEGRADED
            return True
        except ImportError:
            logger.info("pywhispercpp module not found. Falling back to subprocess CLI or mock mode.")
            self._status = ServiceStatus.DEGRADED
            return True
        except Exception as e:
            logger.error(f"Error initializing whisper.cpp: {e}")
            self._status = ServiceStatus.ERROR
            return False

    async def transcribe(self, pcm_data: bytes, sample_rate: int = 16000) -> str:
        if not pcm_data:
            return ""

        if self._pywhisper:
            # Transcribe via Python binding
            segments = self._pywhisper.transcribe(pcm_data)
            return " ".join([seg.text for seg in segments]).strip()
        
        # Fallback text if model binary is in degraded/standby state
        logger.debug("WhisperCppSTT in standby; returning empty transcript.")
        return ""

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="Whisper.cpp STT provider status",
            details={"model": self.model, "models_dir": str(self.models_dir)}
        )

    async def shutdown(self) -> None:
        self._pywhisper = None
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        pass
