"""
MemoryCapability wrapper integrating MemoryCoordinator into the Jarvis Capability Platform.
"""

from typing import Any, Dict, List
from jarvis.capabilities.base import BaseCapability
from jarvis.core.base import HealthStatus, ServiceStatus
from jarvis.memory.coordinator import MemoryCoordinator
from jarvis.memory.schemas import MemoryQuery, MemoryStoreRequest, MemoryType
from jarvis.resource.schemas import ResourcePermission, ActionDescriptor


class MemoryCapability(BaseCapability):
    """
    Capability wrapper exposing Memory Platform operations via the BaseCapability interface.
    """

    name: str = "memory"
    description: str = "Multi-type Memory Platform capability"
    required_permissions: List[ResourcePermission] = [
        ResourcePermission.READ,
        ResourcePermission.WRITE,
    ]

    def __init__(self, coordinator: MemoryCoordinator) -> None:
        self.coordinator = coordinator
        self._status = ServiceStatus.UNINITIALIZED

    async def initialize(self) -> bool:
        await self.coordinator.initialize_defaults()
        self._status = ServiceStatus.RUNNING
        return True

    async def execute(self, action: str, params: Dict[str, Any], session_id: str) -> Any:
        if action in ("store", "remember"):
            m_type_str = params.get("memory_type", "working")
            m_type = MemoryType(m_type_str)
            req = MemoryStoreRequest(
                key=params["key"],
                content=params["content"],
                memory_type=m_type,
                metadata=params.get("metadata", {}),
                session_id=session_id,
            )
            item = await self.coordinator.store(req)
            return item.model_dump()

        elif action in ("query", "search", "retrieve"):
            query_text = params.get("query", params.get("query_text", ""))
            m_types_str = params.get("memory_types", ["working", "semantic"])
            m_types = [MemoryType(t) for t in m_types_str]
            q = MemoryQuery(query_text=query_text, memory_types=m_types, session_id=session_id)
            resources = await self.coordinator.query_as_resources(q)
            return [r.model_dump() for r in resources]

        raise ValueError(f"Unknown memory action: '{action}'")

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="Memory Capability active",
            details={"registered_providers": len(self.coordinator._providers)},
        )

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        pass
