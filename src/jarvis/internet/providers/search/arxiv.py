"""
ArXiv research paper search provider implementation using open ArXiv API endpoint.
Zero API key required.
"""

import logging
import xml.etree.ElementTree as ET
from typing import List, Optional
from urllib.parse import quote_plus
from jarvis.core.base import HealthStatus, ServiceStatus
from jarvis.internet.exceptions import ProviderError
from jarvis.internet.interfaces.search import SearchProvider
from jarvis.internet.schemas import SearchHit
from jarvis.core.base import CancellationToken

logger = logging.getLogger("jarvis.internet.providers.search.arxiv")


class ArXivSearchProvider(SearchProvider):
    name = "arxiv"
    version = "1.0.0"

    def __init__(self) -> None:
        self._status = ServiceStatus.UNINITIALIZED

    async def initialize(self) -> bool:
        self._status = ServiceStatus.RUNNING
        return True

    async def health(self) -> HealthStatus:
        return HealthStatus(status=self._status, message="ArXiv SearchProvider operational")

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
        """Query ArXiv API endpoint."""
        import httpx

        url = f"http://export.arxiv.org/api/query?search_query=all:{quote_plus(query)}&start=0&max_results={max_results}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if cancellation_token and cancellation_token.is_cancelled():
                    return []

                res = await client.get(url)
                if res.status_code != 200:
                    raise ProviderError(f"ArXiv returned status code {res.status_code}")

                root = ET.fromstring(res.text)
                ns = {"atom": "http://www.w3.org/2005/Atom"}

                hits: List[SearchHit] = []
                for i, entry in enumerate(root.findall("atom:entry", ns)):
                    title_elem = entry.find("atom:title", ns)
                    summary_elem = entry.find("atom:summary", ns)
                    id_elem = entry.find("atom:id", ns)

                    title = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else "ArXiv Paper"
                    summary = summary_elem.text.strip().replace("\n", " ") if summary_elem is not None and summary_elem.text else ""
                    paper_id = id_elem.text.strip() if id_elem is not None and id_elem.text else ""

                    hits.append(
                        SearchHit(
                            title=title,
                            url=paper_id,
                            snippet=summary[:300] + ("..." if len(summary) > 300 else ""),
                            engine="arxiv",
                            score=round(1.0 - (i * 0.1), 2),
                        )
                    )

                return hits

        except Exception as e:
            logger.warning(f"ArXiv search failed ({e}).")
            if isinstance(e, ProviderError):
                raise
            raise ProviderError(f"ArXiv search failed: {e}") from e
