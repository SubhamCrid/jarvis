"""
Universal Session schemas supporting HTTP, Browser, OAuth, API, CLI, and SSH authenticated sessions.
"""

import time
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from jarvis.internet.ids import SessionId


class SessionCredential(BaseModel):
    """Credential container (cookies, auth headers, OAuth tokens, SSH key paths)."""

    version: int = 1
    session_id: str = Field(default_factory=lambda: SessionId().value)
    domain: str
    session_type: str = "HTTP"  # HTTP, BROWSER, OAUTH, API, CLI, SSH
    cookies: Dict[str, str] = Field(default_factory=dict)
    headers: Dict[str, str] = Field(default_factory=dict)
    tokens: Dict[str, str] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
