"""
Resource concurrency lock manager preventing race conditions and file corruption.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict


class ResourceLockManager:
    """Manages fine-grained per-resource locks (e.g. file paths, database entries)."""

    def __init__(self) -> None:
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def get_lock(self, resource_key: str) -> asyncio.Lock:
        """Retrieve or create an asyncio.Lock for a specific resource key."""
        async with self._global_lock:
            if resource_key not in self._locks:
                self._locks[resource_key] = asyncio.Lock()
            return self._locks[resource_key]

    @asynccontextmanager
    async def lock_resource(self, resource_key: str) -> AsyncGenerator[None, None]:
        """Async context manager acquiring the lock for target resource_key."""
        lock = await self.get_lock(resource_key)
        async with lock:
            yield

    def active_locks_count(self) -> int:
        """Return total number of active resource locks tracked."""
        return len(self._locks)
