"""
ExtractionProvider contract.
Interface for extracting clean markdown/text from HTML pages.
"""

from abc import ABC, abstractmethod
from typing import Optional
from jarvis.internet.interfaces.base import BaseInternetProvider, ProviderType
from jarvis.internet.schemas import ExtractedDocument, FetchedPage


class ExtractionProvider(BaseInternetProvider, ABC):
    """Abstract interface for text extraction providers."""

    provider_type = ProviderType.EXTRACTION

    @abstractmethod
    async def extract(
        self,
        page: FetchedPage,
        max_tokens: int = 2048,
    ) -> ExtractedDocument:
        """Extract clean markdown and metadata from raw fetched page."""
        pass
