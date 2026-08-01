"""
MockWakeWord provider for testing wake word detection and automated triggers.
"""

from jarvis.core.base import ServiceStatus, HealthStatus
from jarvis.core.config.schema import AppConfig
from jarvis.providers.base import WakeWordProtocol
from jarvis.providers.registry import register_provider


@register_provider("wakeword", "mock")
class MockWakeWord(WakeWordProtocol):
    """Synthetic wake word detector with trigger toggle."""

    @classmethod
    def from_config(cls, config: AppConfig) -> "MockWakeWord":
        return cls(threshold=config.wakeword.threshold)

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._force_trigger: bool = False

    def trigger_wake(self) -> None:
        """Programmatically trigger wake event for automated testing."""
        self._force_trigger = True

    def reset(self) -> None:
        self._force_trigger = False

    async def detect(self, pcm_data: bytes) -> bool:
        if self._force_trigger:
            self._force_trigger = False
            return True
        return False

    async def initialize(self) -> bool:
        self._status = ServiceStatus.RUNNING
        return True

    async def health(self) -> HealthStatus:
        return HealthStatus(status=self._status, message="Mock Wake Word active")

    async def shutdown(self) -> None:
        self._force_trigger = False
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        self._force_trigger = False

