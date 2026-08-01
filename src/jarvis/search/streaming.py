"""
Async generator for real-time progressive result streaming.
"""

import asyncio
from typing import Any, AsyncGenerator, List, Optional
from jarvis.search.schemas import SearchMatch, SearchQuery
from jarvis.tools.schemas import CancellationToken


class SearchStreamGenerator:
    """Streams SearchMatch objects in real-time as provider batches arrive."""

    @classmethod
    async def stream_results(
        cls,
        query: SearchQuery,
        providers: List[Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AsyncGenerator[SearchMatch, None]:
        """Asynchronously stream results from providers as they become available."""
        seen_paths = set()

        for provider in providers:
            if cancellation_token and cancellation_token.is_cancelled():
                break

            try:
                matches = await provider.search(query, cancellation_token)
                for match in matches:
                    if cancellation_token and cancellation_token.is_cancelled():
                        break

                    if match.path not in seen_paths:
                        seen_paths.add(match.path)
                        yield match
                        await asyncio.sleep(0.001)  # Yield control to event loop
            except Exception:
                continue
