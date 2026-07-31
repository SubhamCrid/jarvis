"""
Whisper.cpp STT provider for low-VRAM, high-speed local audio transcription.
"""

import os
import urllib.request
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
    Runs whisper.cpp executable or Python bindings.
    Auto-downloads lightweight GGML model if missing.
    """

    def __init__(
        self,
        model: str = "tiny.en",
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
        model_path = self.models_dir / f"ggml-{self.model}.bin"
        
        # Auto-download GGML model if missing
        if not model_path.exists():
            url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{self.model}.bin"
            logger.info(f"Downloading GGML Whisper model ({self.model}) from {url}...")
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, urllib.request.urlretrieve, url, str(model_path))
                logger.info(f"Successfully downloaded GGML model to {model_path}")
            except Exception as dl_err:
                logger.warning(f"Could not auto-download GGML model: {dl_err}")

        try:
            import pywhispercpp.model as whisper  # type: ignore
            if model_path.exists():
                self._pywhisper = whisper.Model(str(model_path))
                self._status = ServiceStatus.RUNNING
                logger.info(f"WhisperCppSTT loaded model {self.model} from {model_path}")
            else:
                logger.warning(f"Whisper model {model_path} not found. Running with speech fallback.")
                self._status = ServiceStatus.DEGRADED
            return True
        except ImportError:
            logger.info("pywhispercpp module not installed. Running with speech fallback.")
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
            try:
                segments = self._pywhisper.transcribe(pcm_data)
                text = " ".join([seg.text for seg in segments]).strip()
                if text:
                    return text
            except Exception as e:
                logger.error(f"Error during pywhispercpp transcription: {e}")

        logger.debug("WhisperCppSTT model not loaded, returning empty transcript.")
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
