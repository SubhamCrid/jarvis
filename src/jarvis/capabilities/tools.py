"""
ToolsCapability container integrating the tool execution platform into CapabilityRegistry,
and re-exporting compatibility abstractions from jarvis.tools.
"""

import logging
from typing import Any, Dict

from jarvis.capabilities.base import BaseCapability, PermissionEnum
from jarvis.core.base import HealthStatus, ServiceStatus
from jarvis.tools.adapters.file_tools import (
    ListDirectoryTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)
from jarvis.tools.adapters.shell_tools import RunCommandSafeTool
from jarvis.tools.adapters.base import BaseToolAdapter
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.runner import ToolRunner
from jarvis.tools.schemas import ToolCall, ToolSpec, ToolResult, ToolError

logger = logging.getLogger("jarvis.capabilities.tools")


class ToolsCapability(BaseCapability):
    """Capability container holding ToolRegistry and ToolRunner for orchestrator execution."""

    name = "tools"
    required_permissions = [PermissionEnum.SHELL, PermissionEnum.FILESYSTEM]

    def __init__(self, registry: ToolRegistry, runner: ToolRunner) -> None:
        self.registry = registry
        self.runner = runner
        self._status = ServiceStatus.UNINITIALIZED

    async def initialize(self) -> bool:
        """Register default backend tool adapters if not already registered."""
        workspace_root = self.runner.config.workspace_root

        if "read_file" not in self.registry.list_names():
            read_tool = ReadFileTool(workspace_root)
            write_tool = WriteFileTool(workspace_root)
            list_tool = ListDirectoryTool(workspace_root)
            search_tool = SearchFilesTool(workspace_root)
            shell_tool = RunCommandSafeTool(workspace_root)

            self.registry.register(read_tool.spec, read_tool)
            self.registry.register(write_tool.spec, write_tool)
            self.registry.register(list_tool.spec, list_tool)
            self.registry.register(search_tool.spec, search_tool)
            self.registry.register(shell_tool.spec, shell_tool)

        self._status = ServiceStatus.RUNNING
        logger.info(f"ToolsCapability initialized with {len(self.registry.list_names())} tools.")
        return True

    async def health(self) -> HealthStatus:
        metrics = self.runner.health.get_health_metrics(self.registry.list_names())
        return HealthStatus(
            status=self._status,
            message="Tool Execution Platform status",
            details={
                "total_calls": metrics.total_calls,
                "successful_calls": metrics.successful_calls,
                "failed_calls": metrics.failed_calls,
                "active_locks": metrics.active_locks,
                "registered_tools": metrics.registered_tools,
            },
        )

    async def execute(self, action: str, params: Dict[str, Any], session_id: str) -> Any:
        """Execute a tool action by resolving name in ToolRegistry and running via ToolRunner."""
        tool_tuple = self.registry.get_tool(action)
        if not tool_tuple:
            raise ValueError(f"Tool '{action}' is not registered in ToolRegistry.")

        spec, adapter = tool_tuple
        call = ToolCall(
            tool_name=action,
            params=params,
            session_id=session_id,
        )

        return await self.runner.execute_call(call, spec, adapter)

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        pass


__all__ = [
    "ToolsCapability",
    "ToolSpec",
    "ToolCall",
    "ToolResult",
    "ToolError",
    "ToolRegistry",
    "ToolRunner",
    "BaseToolAdapter",
]
