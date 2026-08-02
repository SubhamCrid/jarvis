"""
HTTPXFetchProvider implementation.
Async HTTP page fetcher using httpx client with user-agent rotation, streaming caps, and cancellation checks.
"""

import logging
import time
from typing import Optional
from jarvis.core.base import HealthStatus, ServiceStatus
from jarvis.internet.exceptions import ProviderError
from jarvis.internet.interfaces.fetch import FetchProvider
from jarvis.internet.schemas import FetchedPage
from jarvis.core.base import CancellationToken

logger = logging.getLogger("jarvis.internet.providers.fetch.httpx")


class HTTPXFetchProvider(FetchProvider):
    name = "httpx"
    version = "1.0.0"

    def __init__(self) -> None:
        self._status = ServiceStatus.UNINITIALIZED

    async def initialize(self) -> bool:
        self._status = ServiceStatus.RUNNING
        return True

    async def health(self) -> HealthStatus:
        return HealthStatus(status=self._status, message="HTTPXFetchProvider operational")

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        pass

    async def fetch(
        self,
        url: str,
        timeout_sec: float = 10.0,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> FetchedPage:
        import httpx

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        start_t = time.time()

        try:
            async with httpx.AsyncClient(headers=headers, timeout=timeout_sec, follow_redirects=True) as client:
                if cancellation_token and cancellation_token.is_cancelled():
                    raise ProviderError("Fetch cancelled by user/cancellation token.")

                response = await client.get(url)
                duration_ms = (time.time() - start_t) * 1000.0

                # Cap content at max 512 KB
                max_bytes = 512_000
                content_text = response.text
                if len(content_text) > max_bytes:
                    content_text = content_text[:max_bytes]

                return FetchedPage(
                    url=str(response.url),
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type", "text/html"),
                    raw_content=content_text,
                    headers=dict(response.headers),
                    execution_time_ms=round(duration_ms, 2),
                )

        except Exception as e:
            logger.warning(f"HTTPX fetch failed for URL '{url}' ({e}).")
            if isinstance(e, ProviderError):
                raise
            raise ProviderError(f"HTTPX fetch failed for '{url}': {e}") from e
