"""
Wikipedia search provider implementation using open MediaWiki API endpoint.
Zero API key required.
"""

import logging
from typing import List, Optional
from urllib.parse import quote_plus
from jarvis.core.base import HealthStatus, ServiceStatus
from jarvis.internet.exceptions import ProviderError
from jarvis.internet.interfaces.search import SearchProvider
from jarvis.internet.schemas import SearchHit
from jarvis.core.base import CancellationToken

logger = logging.getLogger("jarvis.internet.providers.search.wikipedia")


class WikipediaSearchProvider(SearchProvider):
    name = "wikipedia"
    version = "1.0.0"

    def __init__(self) -> None:
        self._status = ServiceStatus.UNINITIALIZED

    async def initialize(self) -> bool:
        self._status = ServiceStatus.RUNNING
        return True

    async def health(self) -> HealthStatus:
        return HealthStatus(status=self._status, message="Wikipedia SearchProvider operational")

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        pass

    async def search(
        self,
        query: str,
        max_results: int = 5,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[SearchHit]:
        """Query Wikipedia API endpoint."""
        import httpx

        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote_plus(query)}&format=json&utf8=1"
        headers = {"User-Agent": "JarvisAssistant/1.0 (https://github.com/jarvis)"}

        try:
            async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
                if cancellation_token and cancellation_token.is_cancelled():
                    return []

                res = await client.get(url)
                if res.status_code != 200:
                    raise ProviderError(f"Wikipedia returned status code {res.status_code}")

                data = res.json()
                raw_results = data.get("query", {}).get("search", [])

                hits: List[SearchHit] = []
                for i, item in enumerate(raw_results[:max_results]):
                    page_id = item.get("pageid")
                    title = item.get("title", "")
                    snippet_html = item.get("snippet", "")
                    clean_snippet = snippet_html.replace('<span class="searchmatch">', "").replace("</span>", "").strip()

                    page_url = f"https://en.wikipedia.org/wiki/{quote_plus(title.replace(' ', '_'))}"

                    hits.append(
                        SearchHit(
                            title=title,
                            url=page_url,
                            snippet=clean_snippet,
                            engine="wikipedia",
                            score=round(1.0 - (i * 0.1), 2),
                        )
                    )

                return hits

        except Exception as e:
            logger.warning(f"Wikipedia search failed ({e}).")
            if isinstance(e, ProviderError):
                raise
            raise ProviderError(f"Wikipedia search failed: {e}") from e
