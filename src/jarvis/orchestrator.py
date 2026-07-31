"""
Assistant orchestrator container responsible for dynamic dependency injection,
lifecycle control, and task routing across voice capabilities and hardware providers.
"""

import logging
from typing import Any, Dict, Optional

from jarvis.capabilities.registry import CapabilityRegistry
from jarvis.capabilities.voice_assistant import VoiceAssistantCapability
from jarvis.core.base import BaseServiceProtocol, HealthStatus, ServiceStatus
from jarvis.core.bus import MessageBus
from jarvis.core.config.loader import load_config
from jarvis.core.config.schema import AppConfig
from jarvis.core.executor import TaskExecutor
from jarvis.core.fsm import VoiceFSM
from jarvis.core.observability import ObservabilityService
from jarvis.core.planner import SimplePlanner
from jarvis.core.task_manager import TaskManager
from jarvis.providers import ProviderRegistry

logger = logging.getLogger("jarvis.orchestrator")


class AssistantOrchestrator(BaseServiceProtocol):
    """
    Central dependency orchestrator managing dynamic system provider instantiation via ProviderRegistry,
    capability registration, lifecycle startup/shutdown, and task delegation.
    """

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self.config = config or load_config()
        self._status = ServiceStatus.UNINITIALIZED

        self.bus = MessageBus()
        self.fsm = VoiceFSM()
        self.task_manager = TaskManager()
        self.planner = SimplePlanner()
        self.executor = TaskExecutor()
        self.observability = ObservabilityService()
        self.capability_registry = CapabilityRegistry()

        self.audio_session: Any = None
        self.wakeword: Any = None
        self.stt: Any = None
        self.llm: Any = None
        self.tts: Any = None
        self.session_store: Any = None
        self.voice_capability: Optional[VoiceAssistantCapability] = None

    async def initialize(self) -> bool:
        """Dynamically instantiate providers via ProviderRegistry and wire capability dependencies."""
        logger.info("Initializing AssistantOrchestrator dependencies via ProviderRegistry...")

        is_test = self.config.system.environment == "test"

        audio_name = "mock" if is_test else getattr(self.config.audio, "provider", "sounddevice")
        wakeword_name = "mock" if (is_test or self.config.wakeword.provider == "mock") else self.config.wakeword.provider
        stt_name = "mock" if (is_test or self.config.stt.provider == "mock") else self.config.stt.provider
        llm_name = "mock" if (is_test or self.config.llm.provider == "mock") else self.config.llm.provider
        tts_name = "mock" if (is_test or self.config.tts.provider == "mock") else self.config.tts.provider
        storage_name = "sqlite"

        # Instantiate providers dynamically via ProviderRegistry
        self.audio_session = ProviderRegistry.create("audio", audio_name, self.config)
        self.wakeword = ProviderRegistry.create("wakeword", wakeword_name, self.config)

        # STT fallback logic: try primary -> faster_whisper -> mock
        try:
            self.stt = ProviderRegistry.create("stt", stt_name, self.config)
        except Exception as stt_err:
            logger.warning(f"Primary STT provider '{stt_name}' failed to create ({stt_err}). Falling back to 'faster_whisper'.")
            try:
                self.stt = ProviderRegistry.create("stt", "faster_whisper", self.config)
            except Exception as fw_err:
                logger.warning(f"Fallback STT 'faster_whisper' failed ({fw_err}). Falling back to 'mock'.")
                self.stt = ProviderRegistry.create("stt", "mock", self.config)

        self.llm = ProviderRegistry.create("llm", llm_name, self.config)
        self.tts = ProviderRegistry.create("tts", tts_name, self.config)
        self.session_store = ProviderRegistry.create("storage", storage_name, self.config)

        self.voice_capability = VoiceAssistantCapability(
            fsm=self.fsm,
            bus=self.bus,
            audio_session=self.audio_session,
            wakeword=self.wakeword,
            stt=self.stt,
            llm=self.llm,
            tts=self.tts,
            session_store=self.session_store,
            observability=self.observability,
            vad_threshold=self.config.vad.energy_threshold,
            silence_duration_ms=self.config.vad.silence_duration_ms,
            max_history_turns=self.config.session.max_history_turns,
        )

        await self.voice_capability.initialize()
        self.capability_registry.register(self.voice_capability)

        self._status = ServiceStatus.RUNNING
        logger.info("AssistantOrchestrator successfully initialized.")
        return True

    async def start(self) -> None:
        """Start hardware listening streams."""
        if self.audio_session:
            await self.audio_session.start_listening()
        logger.info(
            f"Jarvis Assistant active; listening for wake word '{self.config.wakeword.model_name}'..."
        )

    async def process_task(self, session_id: str, task_type: str, payload: Dict[str, Any]) -> Any:
        """Delegate incoming session task through task manager, planner, and task executor."""
        task = self.task_manager.create_task(session_id, task_type, payload)
        plan = self.planner.create_plan(task)

        return await self.executor.execute_plan(
            plan=plan,
            capability_registry=self.capability_registry,
            session_id=session_id,
        )

    def update_settings(
        self,
        silence_duration_ms: Optional[int] = None,
        tts_voice: Optional[str] = None,
        tts_speed: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Update runtime configuration settings dynamically."""
        updated: Dict[str, Any] = {}
        if self.voice_capability and silence_duration_ms is not None:
            self.voice_capability.vad.silence_duration_ms = int(silence_duration_ms)
            self.config.vad.silence_duration_ms = int(silence_duration_ms)
            updated["silence_duration_ms"] = int(silence_duration_ms)

        if self.tts:
            if tts_voice:
                setattr(self.tts, "voice", str(tts_voice))
                self.config.tts.voice = str(tts_voice)
                updated["tts_voice"] = str(tts_voice)
            if tts_speed is not None:
                setattr(self.tts, "speed", float(tts_speed))
                self.config.tts.speed = float(tts_speed)
                updated["tts_speed"] = float(tts_speed)

        logger.info(f"Updated runtime settings: {updated}")
        return updated

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="Assistant Orchestrator status",
            details={
                "registered_capabilities": self.capability_registry.list_capabilities(),
                "fsm_state": self.fsm.state.value if self.fsm else "N/A",
                "registered_providers": ProviderRegistry.list_providers(),
            },
        )

    async def shutdown(self) -> None:
        """Gracefully shut down orchestrator services and hardware streams."""
        logger.info("Shutting down AssistantOrchestrator...")
        await self.cancel()
        if self.voice_capability:
            await self.voice_capability.shutdown()
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        await self.executor.cancel()
        if self.voice_capability:
            await self.voice_capability.cancel()
