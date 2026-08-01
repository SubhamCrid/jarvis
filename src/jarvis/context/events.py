"""
Immutable domain events for Ephemeral Context Platform.
"""

from dataclasses import dataclass, field
import datetime


def current_iso_timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@dataclass(frozen=True)
class ContextUpdated:
    event_version: str = "1.0"
    key: str = ""
    scope: str = "ephemeral"
    session_id: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class ContextExpired:
    event_version: str = "1.0"
    key: str = ""
    scope: str = "ephemeral"
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class ContextCleared:
    event_version: str = "1.0"
    scope: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)
