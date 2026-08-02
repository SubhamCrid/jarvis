"""
TrafilaturaExtractionProvider implementation.
Extracts clean Markdown main content from raw HTML while stripping ads, scripts, navbars, and footers.
Falls back safely to BeautifulSoup/Regex if trafilatura is not installed.
"""

import logging
import re
from typing import Optional
from jarvis.core.base import HealthStatus, ServiceStatus
from jarvis.internet.interfaces.extraction import ExtractionProvider
from jarvis.internet.schemas import ExtractedDocument, FetchedPage

logger = logging.getLogger("jarvis.internet.providers.extraction.trafilatura")


class TrafilaturaExtractionProvider(ExtractionProvider):
    name = "trafilatura"
    version = "1.0.0"

    def __init__(self) -> None:
        self._status = ServiceStatus.UNINITIALIZED

    async def initialize(self) -> bool:
        self._status = ServiceStatus.RUNNING
        return True

    async def health(self) -> HealthStatus:
        return HealthStatus(status=self._status, message="TrafilaturaExtractionProvider operational")

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        pass

    async def extract(
        self,
        page: FetchedPage,
        max_tokens: int = 2048,
    ) -> ExtractedDocument:
        """Extract clean text/markdown from page.raw_content."""
        title = self._extract_title(page.raw_content)
        clean_text = ""

        try:
            import trafilatura
            downloaded = trafilatura.extract(
                page.raw_content,
                include_links=True,
                include_formatting=True,
                output_format="markdown",
            )
            if downloaded:
                clean_text = downloaded
        except ImportError:
            logger.debug("Trafilatura package not installed; using fallback HTML text stripper.")

        if not clean_text:
            clean_text = self._fallback_strip_html(page.raw_content)

        # Truncate to max_tokens estimate (~4 chars per token)
        max_chars = max_tokens * 4
        if len(clean_text) > max_chars:
            clean_text = clean_text[:max_chars] + "\n\n...[content truncated to token budget]"

        token_count = len(clean_text.split())

        return ExtractedDocument(
            url=page.url,
            title=title,
            clean_markdown=clean_text,
            token_count=token_count,
            extractor_used="trafilatura",
        )

    def _extract_title(self, html: str) -> str:
        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
        return "Web Document"

    def _fallback_strip_html(self, html: str) -> str:
        # Strip script and style blocks
        clean = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<style[^>]*>.*?</style>", "", clean, flags=re.DOTALL | re.IGNORECASE)
        # Strip HTML tags
        clean = re.sub(r"<[^>]+>", " ", clean)
        # Normalize whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean
