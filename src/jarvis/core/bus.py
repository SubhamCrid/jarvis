"""
Typed message bus and immutable event schema definitions for the Jarvis framework.
"""

import asyncio
import datetime
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Type, TypeVar

logger = logging.getLogger("jarvis.core.bus")


def current_iso_timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@dataclass(frozen=True)
class WakeDetected:
    event_version: str = "1.0"
    timestamp: str = field(default_factory=current_iso_timestamp)
    score: float = 1.0
    model_name: str = "openwakeword"


@dataclass(frozen=True)
class SpeechStarted:
    event_version: str = "1.0"
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class SpeechEnded:
    event_version: str = "1.0"
    timestamp: str = field(default_factory=current_iso_timestamp)
    duration_ms: float = 0.0


@dataclass(frozen=True)
class TranscriptReady:
    event_version: str = "1.0"
    timestamp: str = field(default_factory=current_iso_timestamp)
    text: str = ""
    confidence: float = 1.0
    is_final: bool = True


@dataclass(frozen=True)
class TokenGenerated:
    event_version: str = "1.0"
    timestamp: str = field(default_factory=current_iso_timestamp)
    token: str = ""
    accumulated_text: str = ""


@dataclass(frozen=True)
class SentenceReady:
    event_version: str = "1.0"
    timestamp: str = field(default_factory=current_iso_timestamp)
    sentence: str = ""
    sentence_index: int = 0


@dataclass(frozen=True)
class AudioChunkReady:
    event_version: str = "1.0"
    timestamp: str = field(default_factory=current_iso_timestamp)
    audio_bytes: bytes = b""
    sample_rate: int = 22050
    channels: int = 1
    source: str = "tts"


@dataclass(frozen=True)
class PlaybackFinished:
    event_version: str = "1.0"
    timestamp: str = field(default_factory=current_iso_timestamp)
    duration_ms: float = 0.0


@dataclass(frozen=True)
class TaskCompleted:
    event_version: str = "1.0"
    task_id: str = ""
    result: Any = None
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class TaskCancelled:
    event_version: str = "1.0"
    task_id: str = ""
    reason: str = "User interruption"
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class ErrorOccurred:
    event_version: str = "1.0"
    component: str = ""
    error_type: str = "GeneralError"
    message: str = ""
    exception: Optional[Exception] = None
    timestamp: str = field(default_factory=current_iso_timestamp)


# Additional cross-platform immutable domain events
@dataclass(frozen=True)
class SearchFinished:
    event_version: str = "1.0"
    query: str = ""
    total_found: int = 0
    execution_time_ms: float = 0.0
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class ToolCompleted:
    event_version: str = "1.0"
    tool_name: str = ""
    execution_id: str = ""
    success: bool = True
    result: Any = None
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class BrowserOpened:
    event_version: str = "1.0"
    url: str = ""
    session_id: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class MemoryStored:
    event_version: str = "1.0"
    memory_id: str = ""
    memory_type: str = ""
    session_id: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class VoiceInterrupted:
    event_version: str = "1.0"
    reason: str = "Barge-in"
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class FileChanged:
    event_version: str = "1.0"
    path: str = ""
    change_type: str = "modified"  # created, modified, deleted
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class ResourceActionExecuted:
    event_version: str = "1.0"
    resource_id: str = ""
    action_name: str = ""
    capability_name: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)


T = TypeVar("T")
EventHandler = Callable[[Any], Awaitable[None]]


class MessageBus:
    """
    In-memory asynchronous pub/sub message bus routing domain events
    to subscribed handlers with tracked background task lifecycles.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[Type[Any], List[EventHandler]] = {}
        self._global_subscribers: List[EventHandler] = []
        self._background_tasks: Set[asyncio.Task] = set()

    def subscribe(self, event_type: Type[T], handler: Callable[[T], Awaitable[None]]) -> None:
        """Subscribe an asynchronous handler to a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)  # type: ignore

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe an asynchronous handler to receive all domain events."""
        if handler not in self._global_subscribers:
            self._global_subscribers.append(handler)

    def unsubscribe(self, event_type: Type[T], handler: Callable[[T], Awaitable[None]]) -> None:
        """Unsubscribe an event handler from a specific event type."""
        if event_type in self._subscribers and handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)  # type: ignore

    async def publish(self, event: Any) -> None:
        """Publish a domain event asynchronously to all registered handlers."""
        event_type = type(event)
        handlers = self._subscribers.get(event_type, []).copy() + self._global_subscribers.copy()

        if not handlers:
            return

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    task = asyncio.create_task(self._safe_execute(handler, event))
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
                else:
                    handler(event)
            except Exception as e:
                logger.error(
                    f"Error publishing event {event_type.__name__} to handler: {e}",
                    exc_info=True,
                )

    async def _safe_execute(self, handler: EventHandler, event: Any) -> None:
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                f"Async exception in event handler for {type(event).__name__}: {e}",
                exc_info=True,
            )
