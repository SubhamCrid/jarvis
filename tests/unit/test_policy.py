"""
Unit tests for jarvis.policy platform.
"""

import pytest
from jarvis.policy import (
    PolicyEngine,
    PolicyRule,
    PolicyDecision,
    SecurityContext,
    TrustLevel,
)
from jarvis.resource.schemas import ResourcePermission


def test_policy_engine_allow_default():
    engine = PolicyEngine()
    ctx = SecurityContext()

    res = engine.evaluate_action(
        capability_name="tools",
        action_name="file_read",
        security_context=ctx,
    )
    assert res.decision == PolicyDecision.ALLOW


def test_policy_engine_permission_denial():
    engine = PolicyEngine()
    # Context with READ permission only
    ctx = SecurityContext(granted_permissions=[ResourcePermission.READ])

    res = engine.evaluate_action(
        capability_name="tools",
        action_name="file_write",
        security_context=ctx,
        required_permissions=[ResourcePermission.WRITE],
    )
    assert res.decision == PolicyDecision.DENY
    assert "Missing required permission" in res.reason


def test_policy_engine_approval_required():
    engine = PolicyEngine()
    ctx = SecurityContext()

    res = engine.evaluate_action(
        capability_name="tools",
        action_name="file_delete",
        security_context=ctx,
    )
    assert res.decision == PolicyDecision.REQUIRES_APPROVAL


def test_policy_engine_audit_trail():
    engine = PolicyEngine()
    ctx = SecurityContext()

    engine.evaluate_action("search", "execute", security_context=ctx)
    logs = engine.get_audit_log()
    assert len(logs) >= 1
    assert logs[-1].capability_name == "search"
