"""
Search Event Bus for emitting indexing progress, provider status, and cache events.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Type

logger = logging.getLogger("jarvis.search.events")


@dataclass
class BaseSearchEvent:
    event_type: str
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IndexStarted(BaseSearchEvent):
    event_type: str = "index_started"


@dataclass
class IndexProgress(BaseSearchEvent):
    event_type: str = "index_progress"
    indexed_count: int = 0
    total_count: int = 0


@dataclass
class IndexCompleted(BaseSearchEvent):
    event_type: str = "index_completed"
    total_indexed: int = 0
    duration_ms: float = 0.0


@dataclass
class ProviderOffline(BaseSearchEvent):
    event_type: str = "provider_offline"
    provider_name: str = ""
    reason: str = ""


@dataclass
class CacheCleared(BaseSearchEvent):
    event_type: str = "cache_cleared"


class SearchEventBus:
    """Asynchronous event bus for Search Platform notifications."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[BaseSearchEvent], Any]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[BaseSearchEvent], Any]) -> None:
        """Subscribe handler to a specific search event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def publish(self, event: BaseSearchEvent) -> None:
        """Publish an event to all registered handlers."""
        logger.debug(f"SearchEventBus publish: {event.event_type} {event.details}")
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in SearchEventBus handler for '{event.event_type}': {e}")
