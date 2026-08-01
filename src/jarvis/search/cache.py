"""
TTL/LRU SearchCache for caching SearchResponse instances.
"""

import time
from typing import Dict, Optional, Tuple
from jarvis.search.schemas import SearchResponse


class SearchCache:
    """In-memory search result cache with TTL expiration."""

    def __init__(self, ttl_sec: float = 60.0, max_entries: int = 200) -> None:
        self.ttl_sec = ttl_sec
        self.max_entries = max_entries
        self._cache: Dict[str, Tuple[float, SearchResponse]] = {}

    def get(self, cache_key: str) -> Optional[SearchResponse]:
        """Retrieve cached SearchResponse if valid and not expired."""
        if cache_key not in self._cache:
            return None

        timestamp, response = self._cache[cache_key]
        if time.time() - timestamp > self.ttl_sec:
            del self._cache[cache_key]
            return None

        # Return a copy marked as cached
        response_copy = response.model_copy()
        response_copy.cached = True
        return response_copy

    def put(self, cache_key: str, response: SearchResponse) -> None:
        """Store a SearchResponse in cache."""
        if len(self._cache) >= self.max_entries:
            # Evict oldest entry
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]

        self._cache[cache_key] = (time.time(), response)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    def size(self) -> int:
        """Return total active entries count."""
        return len(self._cache)
