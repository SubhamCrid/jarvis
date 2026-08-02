"""
SessionManagerProtocol contract.
Abstract interface for universal authenticated session management.
"""

from abc import ABC, abstractmethod
from typing import Optional
from jarvis.internet.sessions.schemas import SessionCredential


class SessionManagerProtocol(ABC):
    """Abstract interface for session managers."""

    @abstractmethod
    async def get_session(self, domain: str, session_type: str = "HTTP") -> Optional[SessionCredential]:
        """Retrieve active valid session credential for a domain."""
        pass

    @abstractmethod
    async def save_session(self, credential: SessionCredential) -> None:
        """Store or update session credential."""
        pass

    @abstractmethod
    async def remove_session(self, domain: str) -> None:
        """Purge session credential for a domain."""
        pass
