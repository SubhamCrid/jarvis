"""
VerificationProvider contract.
Interface for cross-source fact consensus and veracity checking.
"""

from abc import ABC, abstractmethod
from typing import List
from jarvis.internet.interfaces.base import BaseInternetProvider, ProviderType
from jarvis.internet.schemas import ExtractedDocument, VerificationResult


class VerificationProvider(BaseInternetProvider, ABC):
    """Abstract interface for fact verification providers."""

    provider_type = ProviderType.VERIFICATION

    @abstractmethod
    async def verify(
        self,
        documents: List[ExtractedDocument],
        query: str,
    ) -> VerificationResult:
        """Verify factual consistency across multiple extracted documents."""
        pass
