"""
Schemas and dataclasses for Policy & Security Platform (jarvis.policy).
"""

import time
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from jarvis.resource.schemas import ResourcePermission


class TrustLevel(str, Enum):
    UNTRUSTED = "untrusted"
    SANDBOXED = "sandboxed"
    USER_CONFIRMED = "user_confirmed"
    FULL_TRUST = "full_trust"


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRES_APPROVAL = "requires_approval"
    CHALLENGE = "challenge"


class SecurityContext(BaseModel):
    """Execution context containing user identity, session, and active trust credentials."""

    model_config = ConfigDict(frozen=True)

    user_id: str = "default_user"
    session_id: str = "default_session"
    trust_level: TrustLevel = TrustLevel.USER_CONFIRMED
    granted_permissions: List[ResourcePermission] = Field(
        default_factory=lambda: [
            ResourcePermission.READ,
            ResourcePermission.WRITE,
            ResourcePermission.EXECUTE,
        ]
    )


class PolicyRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str
    name: str
    target_capability: str = "*"
    target_action: str = "*"
    required_trust_level: TrustLevel = TrustLevel.SANDBOXED
    required_permissions: List[ResourcePermission] = Field(default_factory=list)
    decision: PolicyDecision = PolicyDecision.ALLOW
    description: str = ""


class PolicyEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: PolicyDecision
    reason: str
    rule_id: Optional[str] = None
    evaluated_at: float = Field(default_factory=time.time)


class AuditEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    audit_id: str
    security_context: SecurityContext
    capability_name: str
    action_name: str
    decision: PolicyDecision
    reason: str
    timestamp: float = Field(default_factory=time.time)

