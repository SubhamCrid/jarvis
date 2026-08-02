"""
High-speed Mock Providers for 100% offline testing.
"""

from typing import Any, Dict, List, Optional
from jarvis.core.base import HealthStatus, ServiceStatus
from jarvis.internet.interfaces.browser import BrowserProvider
from jarvis.internet.interfaces.extraction import ExtractionProvider
from jarvis.internet.interfaces.fetch import FetchProvider
from jarvis.internet.interfaces.search import SearchProvider
from jarvis.internet.interfaces.verification import VerificationProvider
from jarvis.internet.schemas import (
    BrowserCapabilities,
    ExtractedDocument,
    FetchedPage,
    SearchHit,
    VerificationResult,
)
from jarvis.core.base import CancellationToken


class MockSearchProvider(SearchProvider):
    name = "mock"
    version = "1.0.0"

    def __init__(self, mock_hits: Optional[List[SearchHit]] = None) -> None:
        self.mock_hits = mock_hits or [
            SearchHit(
                title="Mock Search Result 1",
                url="https://example.com/mock1",
                snippet="This is a mock search snippet for offline testing.",
                engine="mock",
                score=0.95,
            ),
            SearchHit(
                title="Mock Search Result 2",
                url="https://example.com/mock2",
                snippet="Another mock search snippet providing information.",
                engine="mock",
                score=0.85,
            ),
        ]
        self._status = ServiceStatus.RUNNING

    async def initialize(self) -> bool:
        return True

    async def health(self) -> HealthStatus:
        return HealthStatus(status=ServiceStatus.RUNNING, message="Mock SearchProvider operational")

    async def shutdown(self) -> None:
        pass

    async def cancel(self) -> None:
        pass

    async def search(
        self,
        query: str,
        max_results: int = 5,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[SearchHit]:
        return self.mock_hits[:max_results]


class MockFetchProvider(FetchProvider):
    name = "mock"
    version = "1.0.0"

    async def initialize(self) -> bool:
        return True

    async def health(self) -> HealthStatus:
        return HealthStatus(status=ServiceStatus.RUNNING, message="Mock FetchProvider operational")

    async def shutdown(self) -> None:
        pass

    async def cancel(self) -> None:
        pass

    async def fetch(
        self,
        url: str,
        timeout_sec: float = 10.0,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> FetchedPage:
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="text/html",
            raw_content=f"<html><body><h1>Mock Page for {url}</h1><p>Mock extracted body text.</p></body></html>",
            execution_time_ms=5.0,
        )


class MockExtractionProvider(ExtractionProvider):
    name = "mock"
    version = "1.0.0"

    async def initialize(self) -> bool:
        return True

    async def health(self) -> HealthStatus:
        return HealthStatus(status=ServiceStatus.RUNNING, message="Mock ExtractionProvider operational")

    async def shutdown(self) -> None:
        pass

    async def cancel(self) -> None:
        pass

    async def extract(
        self,
        page: FetchedPage,
        max_tokens: int = 2048,
    ) -> ExtractedDocument:
        return ExtractedDocument(
            url=page.url,
            title="Mock Extracted Title",
            clean_markdown=f"# Mock Extracted Title\n\nMock markdown content extracted from {page.url}.",
            token_count=50,
            extractor_used="mock",
        )


class MockBrowserProvider(BrowserProvider):
    name = "mock"
    version = "1.0.0"

    @property
    def capabilities(self) -> BrowserCapabilities:
        return BrowserCapabilities(
            supports_extensions=False,
            supports_persistent_profiles=True,
            supports_downloads=True,
            supports_headful=False,
            supports_streaming_dom=True,
            stealth_level="high",
        )

    async def initialize(self) -> bool:
        return True

    async def health(self) -> HealthStatus:
        return HealthStatus(status=ServiceStatus.RUNNING, message="Mock BrowserProvider operational")

    async def shutdown(self) -> None:
        pass

    async def cancel(self) -> None:
        pass

    async def render_and_extract(
        self,
        url: str,
        timeout_sec: float = 30.0,
        session_type: str = "ephemeral",
        cancellation_token: Optional[CancellationToken] = None,
    ) -> ExtractedDocument:
        return ExtractedDocument(
            url=url,
            title="Mock Rendered SPA Page",
            clean_markdown=f"# Rendered SPA Page\n\nMock rendered dynamic SPA text from {url}.",
            token_count=60,
            extractor_used="mock_browser",
        )

    async def execute_action(
        self,
        action: str,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Any:
        return {"status": "success", "action": action}
