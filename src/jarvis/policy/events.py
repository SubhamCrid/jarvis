"""
Immutable domain events for Policy & Security Platform.
"""

from dataclasses import dataclass, field
import datetime
from jarvis.policy.schemas import PolicyDecision, SecurityContext


def current_iso_timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@dataclass(frozen=True)
class PolicyEvaluated:
    event_version: str = "1.0"
    capability_name: str = ""
    action_name: str = ""
    decision: str = "allow"
    reason: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class PermissionDenied:
    event_version: str = "1.0"
    capability_name: str = ""
    action_name: str = ""
    reason: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)


@dataclass(frozen=True)
class ApprovalRequired:
    event_version: str = "1.0"
    request_id: str = ""
    capability_name: str = ""
    action_name: str = ""
    timestamp: str = field(default_factory=current_iso_timestamp)
