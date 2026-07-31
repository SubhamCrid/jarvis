"""
OpenWakeWord detector provider for local wake word detection ("Jarvis").
"""

import logging
import numpy as np
from jarvis.core.base import ServiceStatus, HealthStatus
from jarvis.core.config.schema import AppConfig
from jarvis.providers.base import WakeWordProtocol
from jarvis.providers.registry import register_provider

logger = logging.getLogger("jarvis.providers.wakeword.openwakeword")


@register_provider("wakeword", "openwakeword")
class OpenWakeWordProvider(WakeWordProtocol):
    """
    OpenWakeWord local detector provider.
    Runs ONNX/TFLite models with high accuracy and low latency.
    """

    @classmethod
    def from_config(cls, config: AppConfig) -> "OpenWakeWordProvider":
        return cls(
            model_name=config.wakeword.model_name,
            threshold=config.wakeword.threshold,
        )

    def __init__(self, model_name: str = "jarvis", threshold: float = 0.5) -> None:
        self.model_name = model_name
        self.threshold = threshold
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._oww_model = None

    async def initialize(self) -> bool:
        try:
            import openwakeword  # type: ignore
            from openwakeword.model import Model  # type: ignore
            openwakeword.utils.download_models()
            try:
                self._oww_model = Model(wakeword_models=[self.model_name], inference_framework="onnx")
            except Exception:
                self._oww_model = Model(inference_framework="onnx")
            self._status = ServiceStatus.RUNNING
            logger.info(f"OpenWakeWordProvider initialized successfully with model '{self.model_name}'.")
            return True
        except ImportError:
            logger.warning("openwakeword package not installed. Running in degraded mode.")
            self._status = ServiceStatus.DEGRADED
            return True
        except Exception as e:
            logger.error(f"Error initializing OpenWakeWordProvider: {e}")
            self._status = ServiceStatus.ERROR
            return False

    async def detect(self, pcm_data: bytes) -> bool:
        if not pcm_data or self._status != ServiceStatus.RUNNING or not self._oww_model:
            return False

        try:
            audio_data = np.frombuffer(pcm_data, dtype=np.int16)
            prediction = self._oww_model.predict(audio_data)
            for model_key, score in prediction.items():
                if score >= self.threshold:
                    logger.info(f"Wake word detected! ({model_key}: score={score:.2f})")
                    return True
        except Exception as e:
            logger.error(f"Error predicting wake word: {e}")

        return False

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="OpenWakeWord detector status",
            details={"model": self.model_name, "threshold": self.threshold}
        )

    async def shutdown(self) -> None:
        self._oww_model = None
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        pass
