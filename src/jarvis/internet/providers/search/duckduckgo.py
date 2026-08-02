"""
DuckDuckGo search provider implementation.
Zero API key required; parses DuckDuckGo HTML/API endpoints using async httpx client.
"""

import logging
import re
from typing import List, Optional
from urllib.parse import quote_plus, unquote
from jarvis.core.base import HealthStatus, ServiceStatus
from jarvis.internet.exceptions import ProviderError
from jarvis.internet.interfaces.search import SearchProvider
from jarvis.internet.schemas import SearchHit
from jarvis.core.base import CancellationToken

logger = logging.getLogger("jarvis.internet.providers.search.duckduckgo")


class DuckDuckGoSearchProvider(SearchProvider):
    name = "duckduckgo"
    version = "1.0.0"

    def __init__(self) -> None:
        self._status = ServiceStatus.UNINITIALIZED

    async def initialize(self) -> bool:
        self._status = ServiceStatus.RUNNING
        return True

    async def health(self) -> HealthStatus:
        return HealthStatus(status=self._status, message="DuckDuckGo SearchProvider operational")

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
        """Execute DuckDuckGo search using httpx HTML endpoint."""
        import httpx

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

        try:
            async with httpx.AsyncClient(headers=headers, timeout=10.0, follow_redirects=True) as client:
                if cancellation_token and cancellation_token.is_cancelled():
                    return []

                response = await client.get(url)
                if response.status_code != 200:
                    raise ProviderError(f"DuckDuckGo returned status code {response.status_code}")

                hits = self._parse_html(response.text, max_results)
                return hits

        except Exception as e:
            logger.warning(f"DuckDuckGo search error ({e}); returning fallback empty hits.")
            if isinstance(e, ProviderError):
                raise
            raise ProviderError(f"DuckDuckGo search request failed: {e}") from e

    def _parse_html(self, html: str, max_results: int) -> List[SearchHit]:
        """Parse search hits from DuckDuckGo HTML output."""
        hits: List[SearchHit] = []
        # Pattern to match result blocks: <a class="result__a" href="...">Title</a> ... <a class="result__snippet">Snippet</a>
        link_pattern = re.compile(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL | re.IGNORECASE)
        snippet_pattern = re.compile(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL | re.IGNORECASE)

        links = link_pattern.findall(html)
        snippets = snippet_pattern.findall(html)

        for i in range(min(len(links), max_results)):
            raw_url, title_html = links[i]
            snippet_html = snippets[i] if i < len(snippets) else ""

            clean_title = re.sub(r"<[^>]+>", "", title_html).strip()
            clean_snippet = re.sub(r"<[^>]+>", "", snippet_html).strip()

            # Clean DDG redirect URL if present
            final_url = raw_url
            if "uddg=" in raw_url:
                match = re.search(r"uddg=([^&]+)", raw_url)
                if match:
                    final_url = unquote(match.group(1))

            if clean_title and final_url and final_url.startswith("http"):
                hits.append(
                    SearchHit(
                        title=clean_title,
                        url=final_url,
                        snippet=clean_snippet,
                        engine="duckduckgo",
                        score=round(1.0 - (i * 0.1), 2),
                    )
                )

        return hits
