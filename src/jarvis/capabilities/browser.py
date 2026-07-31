"""
BrowserCapability placeholder for future browser automation expansion.
"""

from typing import Dict, Any
from jarvis.capabilities.base import BaseCapability, PermissionEnum
from jarvis.core.base import ServiceStatus, HealthStatus


class BrowserCapability(BaseCapability):
    """Placeholder for future Browser capability (Camoufox / Playwright)."""

    name = "browser"
    required_permissions = [PermissionEnum.INTERNET]

    def __init__(self) -> None:
        self._status = ServiceStatus.UNINITIALIZED

    async def initialize(self) -> bool:
        self._status = ServiceStatus.STOPPED
        return True

    async def health(self) -> HealthStatus:
        return HealthStatus(status=self._status, message="Browser capability placeholder (inactive)")

    async def execute(self, action: str, params: Dict[str, Any], session_id: str) -> Any:
        raise NotImplementedError("Browser capability will be activated in future milestone.")

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        pass
