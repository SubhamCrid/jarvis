"""
Thin AssistantOrchestrator.
Confined strictly to 4 duties:
1. Initialize components
2. Wire dependencies
3. Start and stop services
4. Delegate requests
Zero business logic.
"""

import logging
from typing import Optional, Dict, Any
from vidya.core.config.loader import load_config
from vidya.core.config.schema import AppConfig
from vidya.core.base import BaseServiceProtocol, ServiceStatus, HealthStatus
from vidya.core.fsm import VoiceFSM
from vidya.core.bus import MessageBus
from vidya.core.task_manager import TaskManager, Task
from vidya.core.planner import SimplePlanner
from vidya.core.executor import TaskExecutor
from vidya.core.observability import ObservabilityService
from vidya.capabilities.registry import CapabilityRegistry
from vidya.capabilities.voice_assistant import VoiceAssistantCapability

# Providers
from vidya.providers.audio.mock_audio import MockAudioSession
from vidya.providers.audio.sounddevice_session import SoundDeviceAudioSession
from vidya.providers.wakeword.mock_wakeword import MockWakeWord
from vidya.providers.wakeword.openwakeword_provider import OpenWakeWordProvider
from vidya.providers.stt.mock_stt import MockSTT
from vidya.providers.stt.whisper_cpp_stt import WhisperCppSTT
from vidya.providers.llm.mock_llm import MockLLM
from vidya.providers.llm.ollama_llm import OllamaLLM
from vidya.providers.tts.mock_tts import MockTTS
from vidya.providers.tts.piper_tts import PiperTTS
from vidya.providers.storage.session_store import SQLiteSessionStore

logger = logging.getLogger("vidya.orchestrator")


class AssistantOrchestrator(BaseServiceProtocol):
    """
    Thin Assistant Orchestrator.
    Wires system dependencies and routes execution through TaskManager, Planner, TaskExecutor,
    and CapabilityRegistry.
    """

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self.config = config or load_config()
        self._status = ServiceStatus.UNINITIALIZED

        # 1. Framework Core
        self.bus = MessageBus()
        self.fsm = VoiceFSM()
        self.task_manager = TaskManager()
        self.planner = SimplePlanner()
        self.executor = TaskExecutor()
        self.observability = ObservabilityService()
        self.capability_registry = CapabilityRegistry()

        # Service references
        self.audio_session = None
        self.wakeword = None
        self.stt = None
        self.llm = None
        self.tts = None
        self.session_store = None
        self.voice_capability = None

    async def initialize(self) -> bool:
        """Duty 1 & 2: Initialize components and wire dependencies."""
        logger.info("Initializing AssistantOrchestrator and wiring dependencies...")

        # 1. Instantiate Providers based on Configuration
        # Audio Session
        if self.config.system.environment == "test":
            self.audio_session = MockAudioSession(sample_rate=self.config.audio.sample_rate)
        else:
            self.audio_session = SoundDeviceAudioSession(
                sample_rate=self.config.audio.sample_rate,
                speaker_sample_rate=self.config.audio.speaker_sample_rate
            )

        # Wake Word
        if self.config.wakeword.provider == "mock" or self.config.system.environment == "test":
            self.wakeword = MockWakeWord(threshold=self.config.wakeword.threshold)
        else:
            self.wakeword = OpenWakeWordProvider(
                model_name=self.config.wakeword.model_name,
                threshold=self.config.wakeword.threshold
            )

        # STT
        if self.config.stt.provider == "mock" or self.config.system.environment == "test":
            self.stt = MockSTT()
        else:
            self.stt = WhisperCppSTT(model=self.config.stt.model, models_dir=self.config.system.data_dir + "/models")

        # LLM
        if self.config.llm.provider == "mock" or self.config.system.environment == "test":
            self.llm = MockLLM()
        else:
            self.llm = OllamaLLM(model=self.config.llm.model, system_prompt=self.config.llm.system_prompt)

        # TTS
        if self.config.tts.provider == "mock" or self.config.system.environment == "test":
            self.tts = MockTTS(sample_rate=self.config.audio.speaker_sample_rate)
        else:
            self.tts = PiperTTS(voice=self.config.tts.voice, sample_rate=self.config.audio.speaker_sample_rate)

        # Storage
        self.session_store = SQLiteSessionStore(
            db_path=f"{self.config.system.data_dir}/sessions/vidya.db"
        )

        # 2. Instantiate and Wire Primary Voice Assistant Capability
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
            silence_duration_ms=self.config.vad.silence_duration_ms
        )

        # Initialize Voice Capability
        await self.voice_capability.initialize()

        # Register capability
        self.capability_registry.register(self.voice_capability)

        self._status = ServiceStatus.RUNNING
        logger.info("AssistantOrchestrator initialization complete.")
        return True

    async def start(self) -> None:
        """Duty 3: Start listening and main operations."""
        if self.audio_session:
            await self.audio_session.start_listening()
        logger.info("Vidya Desktop Assistant is ACTIVE and listening for wake word 'Vidya'...")

    async def process_task(self, session_id: str, task_type: str, payload: Dict[str, Any]) -> Any:
        """Duty 4: Delegate requests to TaskManager -> Planner -> TaskExecutor -> Capability."""
        task = self.task_manager.create_task(session_id, task_type, payload)
        plan = self.planner.create_plan(task)
        
        result = await self.executor.execute_plan(
            plan=plan,
            capability_registry=self.capability_registry,
            session_id=session_id
        )
        return result

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="Assistant Orchestrator status",
            details={
                "registered_capabilities": self.capability_registry.list_capabilities(),
                "fsm_state": self.fsm.state.value if self.fsm else "N/A"
            }
        )

    async def shutdown(self) -> None:
        """Duty 3: Graceful service shutdown."""
        logger.info("Shutting down AssistantOrchestrator...")
        await self.cancel()
        if self.voice_capability:
            await self.voice_capability.shutdown()
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        await self.executor.cancel()
        if self.voice_capability:
            await self.voice_capability.cancel()
