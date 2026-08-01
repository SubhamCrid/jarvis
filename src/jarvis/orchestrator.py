"""
Assistant orchestrator container responsible for dynamic dependency injection,
lifecycle control, task routing across voice capabilities, tool platform, search platform,
memory platform, policy engine, context manager, agent runtime, and hardware providers.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from jarvis.capabilities.registry import CapabilityRegistry
from jarvis.capabilities.voice_assistant import VoiceAssistantCapability
from jarvis.core.base import BaseServiceProtocol, HealthStatus, ServiceStatus
from jarvis.core.bus import MessageBus
from jarvis.core.config.loader import load_config
from jarvis.core.config.schema import AppConfig
from jarvis.core.container import ServiceContainer
from jarvis.core.executor import TaskExecutor
from jarvis.core.fsm import VoiceFSM
from jarvis.core.observability import ObservabilityService
from jarvis.core.planner import SimplePlanner
from jarvis.core.task_manager import TaskManager
from jarvis.policy.engine import PolicyEngine
from jarvis.context.manager import ContextManager
from jarvis.memory.coordinator import MemoryCoordinator
from jarvis.runtime.executor import AgentRuntime
from jarvis.providers import ProviderRegistry
from jarvis.search.adapter import SearchToolAdapter
from jarvis.search.capability import SearchCapability
from jarvis.search.pipeline import SearchPipelineEngine
from jarvis.tools.capability import ToolsCapability
from jarvis.tools.config import ToolsConfig
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.runner import ToolRunner

logger = logging.getLogger("jarvis.orchestrator")


class AssistantOrchestrator(BaseServiceProtocol):
    """
    Central dependency orchestrator managing dynamic system provider instantiation via ProviderRegistry,
    capability registration, tool execution platform, search platform, memory platform, policy platform,
    context platform, agent runtime platform, lifecycle startup/shutdown, and task delegation.
    """

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        container: Optional[ServiceContainer] = None,
    ) -> None:
        self.config = config or load_config()
        self.container = container or ServiceContainer()
        self._status = ServiceStatus.UNINITIALIZED

        # Resolve core shared platforms from ServiceContainer
        self.bus = self.container.resolve(MessageBus)
        self.policy_engine = self.container.resolve(PolicyEngine)
        self.context_manager = self.container.resolve(ContextManager)
        self.capability_registry = self.container.resolve(CapabilityRegistry)
        self.memory_coordinator = self.container.resolve(MemoryCoordinator)
        self.agent_runtime = self.container.resolve(AgentRuntime)

        self.fsm = VoiceFSM()
        self.task_manager = TaskManager()
        self.planner = SimplePlanner()
        self.executor = TaskExecutor()
        self.observability = ObservabilityService()

        # Tool & Search platform resolution
        self.tools_config = self.container.tools_config
        self.tool_registry = self.container.tool_registry
        self.tool_runner = self.container.tool_runner
        self.tools_capability: Optional[ToolsCapability] = None

        self.search_engine = self.container.search_engine
        self.search_capability: Optional[SearchCapability] = None

        self.audio_session: Any = None
        self.wakeword: Any = None
        self.stt: Any = None
        self.llm: Any = None
        self.tts: Any = None
        self.session_store: Any = None
        self.voice_capability: Optional[VoiceAssistantCapability] = None

    async def initialize(self) -> bool:
        """Dynamically instantiate providers via ProviderRegistry and wire capability dependencies."""
        logger.info("Initializing AssistantOrchestrator dependencies via ServiceContainer...")
        await self.container.initialize()

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

        # Initialize Voice capability
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
            tool_registry=self.tool_registry,
            tool_runner=self.tool_runner,
            vad_threshold=self.config.vad.energy_threshold,
            silence_duration_ms=self.config.vad.silence_duration_ms,
            max_history_turns=self.config.session.max_history_turns,
        )
        await self.voice_capability.initialize()
        self.capability_registry.register(self.voice_capability)

        # Register SearchToolAdapter into ToolRegistry
        search_adapter = SearchToolAdapter(self.search_engine)
        self.tool_registry.register(search_adapter.spec, search_adapter)

        # Initialize Tools capability
        self.tools_capability = ToolsCapability(self.tool_registry, self.tool_runner)
        await self.tools_capability.initialize()
        self.capability_registry.register(self.tools_capability)

        # Initialize Search capability
        self.search_capability = SearchCapability(self.search_engine)
        await self.search_capability.initialize()
        self.capability_registry.register(self.search_capability)

        self._status = ServiceStatus.RUNNING
        logger.info(
            "AssistantOrchestrator successfully initialized with Policy, Context, Memory, Runtime, Voice, Tools, and Search platforms."
        )
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
        tts_provider: Optional[str] = None,
        tts_voice: Optional[str] = None,
        tts_speed: Optional[float] = None,
        tts_cfg_weight: Optional[float] = None,
        tts_exaggeration: Optional[float] = None,
        tts_enable_fallback: Optional[bool] = None,
        tts_fallback_provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update runtime configuration settings dynamically."""
        updated: Dict[str, Any] = {}
        if self.voice_capability and silence_duration_ms is not None:
            self.voice_capability.vad.silence_duration_ms = int(silence_duration_ms)
            self.config.vad.silence_duration_ms = int(silence_duration_ms)
            updated["silence_duration_ms"] = int(silence_duration_ms)

        if tts_fallback_provider is not None:
            val_fb_prov = str(tts_fallback_provider).strip()
            self.config.tts.fallback_provider = val_fb_prov
            if self.tts:
                setattr(self.tts, "fallback_provider", val_fb_prov)
                # Re-initialize fallback engine if active provider is degraded and fallback enabled
                if getattr(self.tts, "enable_fallback", False) and getattr(self.tts, "_status", None) != ServiceStatus.RUNNING:
                    try:
                        from jarvis.providers.registry import ProviderRegistry
                        fb = ProviderRegistry.create("tts", val_fb_prov, self.config)
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(fb.initialize())
                        except RuntimeError:
                            asyncio.run(fb.initialize())
                        setattr(self.tts, "_fallback_tts", fb)
                    except Exception as fb_err:
                        logger.error(f"Failed to dynamically switch fallback provider to '{val_fb_prov}': {fb_err}")
            updated["tts_fallback_provider"] = val_fb_prov

        if tts_enable_fallback is not None:
            val_bool = bool(tts_enable_fallback)
            self.config.tts.enable_fallback = val_bool
            if self.tts:
                setattr(self.tts, "enable_fallback", val_bool)
                if not val_bool:
                    setattr(self.tts, "_fallback_tts", None)
                elif getattr(self.tts, "_status", None) != ServiceStatus.RUNNING and getattr(self.tts, "_fallback_tts", None) is None:
                    try:
                        from jarvis.providers.registry import ProviderRegistry
                        fb_name = getattr(self.tts, "fallback_provider", "edge_tts")
                        fb = ProviderRegistry.create("tts", fb_name, self.config)
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(fb.initialize())
                        except RuntimeError:
                            asyncio.run(fb.initialize())
                        setattr(self.tts, "_fallback_tts", fb)
                    except Exception as fb_err:
                        logger.error(f"Failed to dynamically initialize fallback for active TTS: {fb_err}")
            updated["tts_enable_fallback"] = val_bool

        if tts_cfg_weight is not None:
            val_float = float(tts_cfg_weight)
            self.config.tts.cfg_weight = val_float
            if self.tts:
                setattr(self.tts, "cfg_weight", val_float)
            updated["tts_cfg_weight"] = val_float

        if tts_exaggeration is not None:
            val_float = float(tts_exaggeration)
            self.config.tts.exaggeration = val_float
            if self.tts:
                setattr(self.tts, "exaggeration", val_float)
            updated["tts_exaggeration"] = val_float

        if tts_provider and tts_provider != self.config.tts.provider:
            self.config.tts.provider = str(tts_provider)
            try:
                from jarvis.providers.registry import ProviderRegistry
                new_tts = ProviderRegistry.create("tts", str(tts_provider), self.config)
                # Initialize in background or current loop
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(new_tts.initialize())
                except RuntimeError:
                    asyncio.run(new_tts.initialize())
                self.tts = new_tts
                if self.voice_capability:
                    self.voice_capability.tts = new_tts
                updated["tts_provider"] = str(tts_provider)
            except Exception as e:
                logger.error(f"Failed to dynamically switch TTS provider to '{tts_provider}': {e}")

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
        tool_health_info = None
        if self.tools_capability:
            tool_h = await self.tools_capability.health()
            tool_health_info = tool_h.details

        search_health_info = None
        if self.search_capability:
            search_h = await self.search_capability.health()
            search_health_info = search_h.details

        return HealthStatus(
            status=self._status,
            message="Assistant Orchestrator status",
            details={
                "registered_capabilities": self.capability_registry.list_capabilities(),
                "fsm_state": self.fsm.state.value if self.fsm else "N/A",
                "registered_providers": ProviderRegistry.list_providers(),
                "tool_platform_health": tool_health_info,
                "search_platform_health": search_health_info,
                "policy_rules_count": len(self.policy_engine._rules),
            },
        )

    async def shutdown(self) -> None:
        """Gracefully shut down orchestrator services and hardware streams."""
        logger.info("Shutting down AssistantOrchestrator...")
        await self.cancel()
        if self.voice_capability:
            await self.voice_capability.shutdown()
        if self.tools_capability:
            await self.tools_capability.shutdown()
        if self.search_capability:
            await self.search_capability.shutdown()
        await self.agent_runtime.shutdown()
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        await self.executor.cancel()
        await self.agent_runtime.cancel()
        if self.voice_capability:
            await self.voice_capability.cancel()
        if self.tools_capability:
            await self.tools_capability.cancel()
        if self.search_capability:
            await self.search_capability.cancel()
