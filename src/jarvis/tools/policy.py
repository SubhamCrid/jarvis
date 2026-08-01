"""
ToolPolicyEngine enforcing security levels, permission gates, and execution safety rules.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from jarvis.tools.config import ToolsConfig
from jarvis.tools.sandbox import PathSandbox
from jarvis.tools.schemas import PermissionLevel, SideEffectLevel, ToolSpec


class PolicyViolationError(PermissionError):
    """Raised when a tool execution request violates safety policy rules."""

    pass


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
    requires_confirmation: bool = False


class ToolPolicyEngine:
    """Evaluates safety policies for tool requests based on configuration and security manifests."""

    FORBIDDEN_COMMANDS = {
        "rm", "del", "format", "mkfs", "dd", "shutdown", "reboot",
        "poweroff", "dropdb", "truncate", "chmod", "chown", "sudo"
    }

    def __init__(self, config: ToolsConfig) -> None:
        self.config = config
        self.sandbox = PathSandbox(config.workspace_root)

    def evaluate(self, spec: ToolSpec, params: Dict[str, Any]) -> PolicyDecision:
        """
        Evaluate if a tool execution is allowed under current policy rules.
        """
        manifest = spec.manifest

        # 1. Command specific checks for shell execution tools (run FIRST)
        if "command" in params or "argv" in params:
            argv = params.get("argv")
            cmd_str = params.get("command")

            if argv and isinstance(argv, list):
                executable = argv[0].lower() if argv else ""
                if executable in self.FORBIDDEN_COMMANDS:
                    return PolicyDecision(
                        allowed=False,
                        reason=f"Command '{executable}' is forbidden by security policy.",
                    )
            elif cmd_str and isinstance(cmd_str, str):
                first_word = cmd_str.strip().split()[0].lower() if cmd_str.strip() else ""
                if first_word in self.FORBIDDEN_COMMANDS:
                    return PolicyDecision(
                        allowed=False,
                        reason=f"Command '{first_word}' is forbidden by security policy.",
                    )

        # 2. READ_ONLY tools auto-allowed in all modes
        if manifest.permission_level == PermissionLevel.READ_ONLY or manifest.read_only:
            return PolicyDecision(allowed=True, reason="READ_ONLY tool auto-approved.")

        # 3. Strict policy mode checks
        if self.config.policy_mode == "STRICT":
            if manifest.permission_level in (PermissionLevel.RISKY, PermissionLevel.ADMIN):
                return PolicyDecision(
                    allowed=True,
                    reason=f"{manifest.permission_level.value.upper()} tool requires confirmation in STRICT mode.",
                    requires_confirmation=True,
                )
            if manifest.side_effect_level in (SideEffectLevel.HIGH, SideEffectLevel.DESTRUCTIVE):
                return PolicyDecision(
                    allowed=True,
                    reason=f"{manifest.side_effect_level.value.upper()} side-effect requires user confirmation.",
                    requires_confirmation=True,
                )

        return PolicyDecision(allowed=True, reason="Action approved by policy engine.")
