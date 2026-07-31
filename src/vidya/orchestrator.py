"""
Assistant orchestrator container responsible for dependency injection, lifecycle control,
and task routing across voice capabilities and hardware providers.
"""

import logging
from typing import Any, Dict, Optional

from vidya.capabilities.registry import CapabilityRegistry
from vidya.capabilities.voice_assistant import VoiceAssistantCapability
from vidya.core.base import BaseServiceProtocol, HealthStatus, ServiceStatus
from vidya.core.bus import MessageBus
from vidya.core.config.loader import load_config
from vidya.core.config.schema import AppConfig
from vidya.core.executor import TaskExecutor
from vidya.core.fsm import VoiceFSM
from vidya.core.observability import ObservabilityService
from vidya.core.planner import SimplePlanner
from vidya.core.task_manager import TaskManager

from vidya.providers.audio.mock_audio import MockAudioSession
from vidya.providers.audio.sounddevice_session import SoundDeviceAudioSession
from vidya.providers.llm.mock_llm import MockLLM
from vidya.providers.llm.ollama_llm import OllamaLLM
from vidya.providers.storage.session_store import SQLiteSessionStore
from vidya.providers.stt.faster_whisper_stt import FasterWhisperSTT
from vidya.providers.stt.mock_stt import MockSTT
from vidya.providers.stt.whisper_cpp_stt import WhisperCppSTT
from vidya.providers.tts.edge_tts_provider import EdgeTTSProvider
from vidya.providers.tts.mock_tts import MockTTS
from vidya.providers.tts.piper_tts import PiperTTS
from vidya.providers.wakeword.mock_wakeword import MockWakeWord
from vidya.providers.wakeword.openwakeword_provider import OpenWakeWordProvider

logger = logging.getLogger("vidya.orchestrator")


class AssistantOrchestrator(BaseServiceProtocol):
    """
    Central dependency orchestrator managing system provider instantiation,
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
        """Instantiate providers based on system configuration and wire capability dependencies."""
        logger.info("Initializing AssistantOrchestrator dependencies...")

        if self.config.system.environment == "test":
            self.audio_session = MockAudioSession(sample_rate=self.config.audio.sample_rate)
        else:
            self.audio_session = SoundDeviceAudioSession(
                sample_rate=self.config.audio.sample_rate,
                speaker_sample_rate=self.config.audio.speaker_sample_rate,
            )

        if self.config.wakeword.provider == "mock" or self.config.system.environment == "test":
            self.wakeword = MockWakeWord(threshold=self.config.wakeword.threshold)
        else:
            self.wakeword = OpenWakeWordProvider(
                model_name=self.config.wakeword.model_name,
                threshold=self.config.wakeword.threshold,
            )

        if self.config.stt.provider == "mock" or self.config.system.environment == "test":
            self.stt = MockSTT()
        elif self.config.stt.provider == "whisper_cpp":
            try:
                import pywhispercpp  # type: ignore
                self.stt = WhisperCppSTT(model=self.config.stt.model)
            except ImportError:
                logger.info("pywhispercpp uninstalled; using FasterWhisperSTT backend.")
                self.stt = FasterWhisperSTT(model=self.config.stt.model)
        elif self.config.stt.provider == "faster_whisper":
            self.stt = FasterWhisperSTT(model=self.config.stt.model)
        else:
            self.stt = FasterWhisperSTT(model=self.config.stt.model)

        if self.config.llm.provider == "mock" or self.config.system.environment == "test":
            self.llm = MockLLM()
        else:
            self.llm = OllamaLLM(
                model=self.config.llm.model,
                system_prompt=self.config.llm.system_prompt,
                temperature=self.config.llm.temperature,
                max_tokens=self.config.llm.max_tokens,
            )

        if self.config.tts.provider == "edge_tts":
            self.tts = EdgeTTSProvider(
                voice=self.config.tts.voice,
                sample_rate=self.config.audio.speaker_sample_rate,
                speed=self.config.tts.speed,
                auto_switch_voice=self.config.tts.auto_switch_voice,
            )
        elif self.config.tts.provider == "mock" or self.config.system.environment == "test":
            self.tts = MockTTS(sample_rate=self.config.audio.speaker_sample_rate)
        else:
            self.tts = PiperTTS(
                voice=self.config.tts.voice,
                sample_rate=self.config.audio.speaker_sample_rate,
                speed=self.config.tts.speed,
            )

        self.session_store = SQLiteSessionStore(
            db_path=f"{self.config.system.data_dir}/sessions/vidya.db"
        )

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
            f"Vidya Assistant active; listening for wake word '{self.config.wakeword.model_name}'..."
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

