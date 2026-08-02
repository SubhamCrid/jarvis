"""
BrowserProvider contract.
Interface for browser automation engines (Camoufox, Playwright, browser-use).
Exposes BrowserCapabilities metadata.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from jarvis.core.base import CancellationToken
from jarvis.internet.interfaces.base import BaseInternetProvider, ProviderType
from jarvis.internet.schemas import BrowserCapabilities, ExtractedDocument


class BrowserProvider(BaseInternetProvider, ABC):
    """Abstract interface for browser automation providers."""

    provider_type = ProviderType.BROWSER

    @property
    @abstractmethod
    def capabilities(self) -> BrowserCapabilities:
        """Return advertised browser capabilities."""
        pass

    @abstractmethod
    async def render_and_extract(
        self,
        url: str,
        timeout_sec: float = 30.0,
        session_type: str = "ephemeral",
        cancellation_token: Optional[CancellationToken] = None,
    ) -> ExtractedDocument:
        """Render JavaScript-heavy web page in browser context and extract clean document."""
        pass

    @abstractmethod
    async def execute_action(
        self,
        action: str,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Any:
        """Execute explicit browser automation action (click, fill, screenshot, evaluate)."""
        pass
