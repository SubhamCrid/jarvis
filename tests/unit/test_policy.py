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


def test_tool_policy_strict_vs_permissive_modes(tmp_path):
    from jarvis.tools.config import ToolsConfig
    from jarvis.tools.policy import ToolPolicyEngine
    from jarvis.tools.schemas import ToolSpec, ToolManifest, PermissionLevel, SideEffectLevel
    from pathlib import Path

    ws_root = (tmp_path / "workspace").resolve()
    ws_root.mkdir()
    outside_dir = (tmp_path / "outside").resolve()
    outside_dir.mkdir()
    target_file = outside_dir / "target.txt"

    write_spec = ToolSpec(
        manifest=ToolManifest(
            name="write_file",
            permission_level=PermissionLevel.WRITE,
            side_effect_level=SideEffectLevel.MEDIUM,
            read_only=False,
        )
    )

    # 1. STRICT Mode
    cfg_strict = ToolsConfig(workspace_root=ws_root, policy_mode="STRICT")
    engine_strict = ToolPolicyEngine(cfg_strict)
    dec_strict = engine_strict.evaluate(write_spec, {"path": str(target_file), "content": "data"})
    # In STRICT mode, writes outside workspace_root require confirmation
    assert dec_strict.allowed is True
    assert dec_strict.requires_confirmation is True

    # 2. PERMISSIVE Mode (Unrestricted Access)
    cfg_permissive = ToolsConfig(workspace_root=ws_root, policy_mode="PERMISSIVE")
    engine_permissive = ToolPolicyEngine(cfg_permissive)
    dec_permissive = engine_permissive.evaluate(write_spec, {"path": str(target_file), "content": "data"})
    # In PERMISSIVE mode, unrestricted access is auto-approved without confirmation
    assert dec_permissive.allowed is True
    assert dec_permissive.requires_confirmation is False
    assert "PERMISSIVE" in dec_permissive.reason

