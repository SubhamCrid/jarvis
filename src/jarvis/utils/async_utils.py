"""
Async Utilities and Bounded Queue Helpers for Pipeline Backpressure.
"""

import asyncio
import logging
from typing import TypeVar, Generic, Optional, List

logger = logging.getLogger("jarvis.utils.async_utils")

T = TypeVar("T")


class BoundedQueue(Generic[T]):
    """
    Wrapper around asyncio.Queue with explicit backpressure and cancellation support.
    """

    def __init__(self, maxsize: int = 50) -> None:
        self.maxsize = maxsize
        self._queue: asyncio.Queue[T] = asyncio.Queue(maxsize=maxsize)

    async def put(self, item: T, timeout: Optional[float] = None) -> bool:
        """
        Put item in queue. Applies backpressure if full.
        Returns True if successful, False if timeout occurred.
        """
        try:
            if timeout is None:
                await self._queue.put(item)
            else:
                await asyncio.wait_for(self._queue.put(item), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Queue put timed out after {timeout}s (queue full: {self._queue.full()})")
            return False

    async def get(self, timeout: Optional[float] = None) -> Optional[T]:
        """
        Get item from queue. Returns None if timeout occurs.
        """
        try:
            if timeout is None:
                return await self._queue.get()
            else:
                return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def task_done(self) -> None:
        try:
            self._queue.task_done()
        except ValueError:
            pass

    def clear(self) -> int:
        """Flush and clear all pending items from queue immediately on interruption."""
        cleared_count = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                cleared_count += 1
            except (asyncio.QueueEmpty, ValueError):
                break
        return cleared_count

    def size(self) -> int:
        return self._queue.qsize()

    def full(self) -> bool:
        return self._queue.full()

    def empty(self) -> bool:
        return self._queue.empty()


async def safe_cancel_task(task: Optional[asyncio.Task]) -> None:
    """Safely cancel an async task and await its completion to avoid unhandled errors."""
    if task and not task.done():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
