"""
Central runtime configuration for Jarvis tool execution platform.
Keeps all tool runtime policies, timeouts, sandboxing rules, and redaction toggles configurable.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ToolsConfig:
    """Central configuration parameters governing tool safety, execution, and sandboxing."""

    workspace_root: Path = field(default_factory=lambda: Path(os.getcwd()).resolve())
    policy_mode: str = "STRICT"  # STRICT, BALANCED, PERMISSIVE
    command_timeout_sec: float = 30.0
    max_retries: int = 2
    redaction_enabled: bool = True
    max_output_bytes: int = 65536  # 64 KB max output truncation limit
    allowed_env_vars: List[str] = field(
        default_factory=lambda: ["PATH", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "HOME", "LANG", "LC_ALL"]
    )
    max_concurrent_tools: int = 5
    persist_traces: bool = True

    @classmethod
    def from_env(cls, workspace_root: Optional[Path] = None) -> "ToolsConfig":
        """Instantiate config reading overrides from environment variables (JARVIS_TOOLS_*)."""
        ws_root = workspace_root or Path(os.getenv("JARVIS_TOOLS_WORKSPACE_ROOT", os.getcwd())).resolve()
        policy_mode = os.getenv("JARVIS_TOOLS_POLICY_MODE", "STRICT").upper()
        timeout = float(os.getenv("JARVIS_TOOLS_COMMAND_TIMEOUT_SEC", "30.0"))
        max_retries = int(os.getenv("JARVIS_TOOLS_MAX_RETRIES", "2"))
        redaction = os.getenv("JARVIS_TOOLS_REDACTION_ENABLED", "true").lower() in ("true", "1", "yes")
        max_output = int(os.getenv("JARVIS_TOOLS_MAX_OUTPUT_BYTES", "65536"))

        return cls(
            workspace_root=ws_root,
            policy_mode=policy_mode,
            command_timeout_sec=timeout,
            max_retries=max_retries,
            redaction_enabled=redaction,
            max_output_bytes=max_output,
        )
