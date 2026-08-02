"""
Typed exception hierarchy for jarvis.internet platform.
All errors inherit from InternetError for clean, structured exception handling.
"""

from typing import Any, Dict, Optional


class InternetError(Exception):
    """Base exception for all jarvis.internet errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ProviderError(InternetError):
    """Raised when an external or internal provider fails."""

    pass


class ProviderNotFoundError(ProviderError):
    """Raised when a requested provider is not registered in ProviderRegistry."""

    pass


class ProviderUnavailableError(ProviderError):
    """Raised when a provider is in DEGRADED or OPEN circuit breaker state."""

    pass


class RateLimitError(ProviderError):
    """Raised when a provider or domain rate limit is exceeded."""

    pass


class ContentExtractionError(InternetError):
    """Raised when HTML/text extraction fails."""

    pass


class VerificationError(InternetError):
    """Raised when multi-source content verification fails."""

    pass


class SSRFPolicyError(InternetError):
    """Raised when a URL targets loopback, private subnets, or metadata endpoints."""

    pass


class PolicyViolationError(InternetError):
    """Raised when a request violates domain trust or privacy policy rules."""

    pass


class ResourceExhaustedError(InternetError):
    """Raised when ExecutionBudget byte, token, or request limits are breached."""

    pass


class BrowserTaskError(InternetError):
    """Raised when browser automation fails, crashes, or times out."""

    pass


class BrowserCrashError(BrowserTaskError):
    """Raised when the browser subprocess panics or crashes."""

    pass
