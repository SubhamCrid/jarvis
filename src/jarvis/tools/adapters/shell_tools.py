"""
Modular safe shell command tool using subprocess execv (argv-based, shell=False).
Supports clean subprocess cancellation on barge-in or stop signals.
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from jarvis.tools.adapters.base import BaseToolAdapter
from jarvis.tools.sandbox import PathSandbox
from jarvis.tools.schemas import (
    ExecutionContext,
    PermissionLevel,
    SideEffectLevel,
    ToolManifest,
    ToolSpec,
)


class RunCommandSafeTool(BaseToolAdapter):
    """Executes permitted CLI commands via subprocess.execv array (no shell=True)."""

    ALLOWED_EXECUTABLES = {
        "dir", "ls", "git", "pytest", "python", "python3", "echo", "cat",
        "type", "node", "npm", "pip", "whoami", "ver", "pwd", "tree"
    }

    def __init__(self, workspace_root: Optional[Path] = None) -> None:
        self.sandbox = PathSandbox(workspace_root or Path.cwd())

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            manifest=ToolManifest(
                name="run_command_safe",
                version="1.0.0",
                description="Run a safe command-line tool via argv array (no shell=True).",
                permission_level=PermissionLevel.RISKY,
                idempotent=False,
                read_only=False,
                side_effect_level=SideEffectLevel.MEDIUM,
                timeout_sec=30.0,
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "argv": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Command and arguments array (e.g. ['git', 'status']).",
                    },
                    "cwd": {"type": "string", "description": "Optional subdirectory working directory.", "default": "."},
                },
                "required": ["argv"],
            },
        )

    async def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        argv: List[str] = params.get("argv", [])
        if not argv:
            raise ValueError("Argv array cannot be empty.")

        binary = argv[0].lower()
        # Remove file extension if present (e.g., python.exe -> python)
        base_binary = Path(binary).stem.lower()

        if base_binary not in self.ALLOWED_EXECUTABLES:
            raise PermissionError(f"Executable '{binary}' is not in the permitted command whitelist.")

        raw_cwd = params.get("cwd", ".")
        resolved_cwd = self.sandbox.validate_and_resolve(raw_cwd, must_exist=True)

        # Environment variable allowlist filter
        clean_env = {
            k: v for k, v in os.environ.items()
            if k.upper() in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "HOME", "LANG", "LC_ALL")
        }

        # Create subprocess using execv (shell=False)
        proc = await asyncio.create_subprocess_exec(
            argv[0],
            *argv[1:],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(resolved_cwd),
            env=clean_env,
        )

        try:
            # Monitor process completion while checking cancellation token
            stdout_bytes, stderr_bytes = await proc.communicate()
        except asyncio.CancelledError:
            # Terminate and kill subprocess cleanly on cancellation
            if proc.returncode is None:
                try:
                    proc.terminate()
                    await asyncio.sleep(0.1)
                    if proc.returncode is None:
                        proc.kill()
                except Exception:
                    pass
            raise

        stdout_str = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr_str = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        return {
            "argv": argv,
            "exit_code": proc.returncode,
            "stdout": stdout_str[:65536],  # Capped at 64 KB
            "stderr": stderr_str[:65536],
            "success": proc.returncode == 0,
        }
