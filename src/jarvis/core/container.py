"""
ServiceContainer as the application composition root using constructor dependency injection.
"""

import logging
from typing import Any, Dict, Optional, Type, TypeVar
from jarvis.core.bus import MessageBus
from jarvis.policy.engine import PolicyEngine
from jarvis.context.manager import ContextManager
from jarvis.capabilities.registry import CapabilityRegistry
from jarvis.memory.coordinator import MemoryCoordinator
from jarvis.memory.capability import MemoryCapability
from jarvis.runtime.capability_router import CapabilityRouter
from jarvis.runtime.executor import AgentRuntime
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.runner import ToolRunner
from jarvis.tools.config import ToolsConfig
from jarvis.search.pipeline import SearchPipelineEngine
from jarvis.internet.platform import InternetPlatform

logger = logging.getLogger("jarvis.core.container")

T = TypeVar("T")


class ServiceContainer:
    """
    Application composition root managing singleton service registration,
    constructor dependency injection, and lifecycle wiring.
    """

    def __init__(self) -> None:
        self._services: Dict[Type[Any], Any] = {}

        # 1. Instantiate Core Shared Platforms
        self.bus = MessageBus()
        self.policy_engine = PolicyEngine()
        self.context_manager = ContextManager()
        self.capability_registry = CapabilityRegistry()

        # 2. Instantiate Search, Tools & Internet Platforms
        self.tools_config = ToolsConfig.from_env()
        self.tool_registry = ToolRegistry()
        self.tool_runner = ToolRunner(config=self.tools_config)
        self.search_engine = SearchPipelineEngine()
        self.internet_platform = InternetPlatform()

        # 3. Instantiate Memory Platform
        self.memory_coordinator = MemoryCoordinator()
        self.memory_capability = MemoryCapability(self.memory_coordinator)

        # 4. Instantiate Agent Runtime Platform
        self.capability_router = CapabilityRouter(registry=self.capability_registry)
        self.runtime = AgentRuntime(
            router=self.capability_router,
            policy_engine=self.policy_engine,
        )

        # Register services into container map
        self.register_service(MessageBus, self.bus)
        self.register_service(PolicyEngine, self.policy_engine)
        self.register_service(ContextManager, self.context_manager)
        self.register_service(CapabilityRegistry, self.capability_registry)
        self.register_service(MemoryCoordinator, self.memory_coordinator)
        self.register_service(MemoryCapability, self.memory_capability)
        self.register_service(AgentRuntime, self.runtime)
        self.register_service(ToolRegistry, self.tool_registry)
        self.register_service(ToolRunner, self.tool_runner)
        self.register_service(SearchPipelineEngine, self.search_engine)
        self.register_service(InternetPlatform, self.internet_platform)

    def register_service(self, service_type: Type[T], instance: T) -> None:
        self._services[service_type] = instance

    def resolve(self, service_type: Type[T]) -> T:
        if service_type not in self._services:
            raise KeyError(f"Service of type '{service_type.__name__}' is not registered in ServiceContainer.")
        return self._services[service_type]

    async def initialize(self) -> None:
        logger.info("Initializing ServiceContainer dependencies...")
        await self.internet_platform.initialize()
        await self.memory_coordinator.initialize_defaults()
        await self.memory_capability.initialize()
        self.capability_registry.register(self.memory_capability)
        await self.runtime.initialize()
        logger.info("ServiceContainer fully initialized.")

