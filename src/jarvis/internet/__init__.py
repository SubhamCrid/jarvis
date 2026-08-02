"""
jarvis.internet package initialization.
Foundational Internet Intelligence Platform for Jarvis voice assistant framework.
"""

from jarvis.internet.platform import InternetPlatform
from jarvis.internet.config import InternetConfig, load_internet_config
from jarvis.internet.schemas import (
    SearchHit,
    FetchedPage,
    ExtractedDocument,
    Citation,
    VerificationResult,
    InternetDocument,
    InternetResult,
    BrowserCapabilities,
)
from jarvis.internet.exceptions import (
    InternetError,
    ProviderError,
    SSRFPolicyError,
    BrowserTaskError,
)

__version__ = "1.0.0"

__all__ = [
    "InternetPlatform",
    "InternetConfig",
    "load_internet_config",
    "SearchHit",
    "FetchedPage",
    "ExtractedDocument",
    "Citation",
    "VerificationResult",
    "InternetDocument",
    "InternetResult",
    "BrowserCapabilities",
    "InternetError",
    "ProviderError",
    "SSRFPolicyError",
    "BrowserTaskError",
]
