"""
Modular backend file system tools with PathSandbox confinement.
"""

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


def _format_path(sandbox: PathSandbox, path: Path) -> str:
    try:
        return str(path.relative_to(sandbox.workspace_root))
    except ValueError:
        try:
            return str(path.relative_to(sandbox.home_root))
        except ValueError:
            return str(path)


class ReadFileTool(BaseToolAdapter):
    """Tool for reading file contents safely within workspace bounds."""

    def __init__(self, workspace_root: Optional[Path] = None) -> None:
        self.sandbox = PathSandbox(workspace_root or Path.cwd())

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            manifest=ToolManifest(
                name="read_file",
                version="1.0.0",
                description="Read contents of a file within workspace or system directory (Desktop, Downloads, Documents).",
                permission_level=PermissionLevel.READ_ONLY,
                idempotent=True,
                read_only=True,
                side_effect_level=SideEffectLevel.NONE,
                timeout_sec=10.0,
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative or named path to file (e.g. notes.txt, Desktop/yo.txt)."},
                    "start_line": {"type": "integer", "description": "Optional starting line (1-indexed)."},
                    "end_line": {"type": "integer", "description": "Optional ending line (1-indexed)."},
                },
                "required": ["path"],
            },
        )

    async def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        raw_path = params["path"]
        resolved_path = self.sandbox.validate_and_resolve(raw_path, must_exist=True)

        if not resolved_path.is_file():
            raise ValueError(f"Path '{raw_path}' is a directory, not a file.")

        content = resolved_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()

        start_line = params.get("start_line")
        end_line = params.get("end_line")

        if start_line is not None or end_line is not None:
            s_idx = max(0, (start_line or 1) - 1)
            e_idx = end_line if end_line is not None else len(lines)
            selected_lines = lines[s_idx:e_idx]
            final_text = "\n".join(selected_lines)
        else:
            final_text = content

        return {
            "path": _format_path(self.sandbox, resolved_path),
            "total_lines": len(lines),
            "content": final_text,
        }


class WriteFileTool(BaseToolAdapter):
    """Tool for creating or overwriting files safely within workspace bounds."""

    def __init__(self, workspace_root: Optional[Path] = None) -> None:
        self.sandbox = PathSandbox(workspace_root or Path.cwd())

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            manifest=ToolManifest(
                name="write_file",
                version="1.0.0",
                description="Write content to a file inside the workspace directory.",
                permission_level=PermissionLevel.WRITE,
                idempotent=False,
                read_only=False,
                side_effect_level=SideEffectLevel.MEDIUM,
                timeout_sec=15.0,
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to destination file."},
                    "content": {"type": "string", "description": "Content string to write."},
                },
                "required": ["path", "content"],
            },
        )

    async def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        raw_path = params["path"]
        content = params["content"]

        resolved_path = self.sandbox.validate_and_resolve(raw_path, must_exist=False)
        resolved_path.parent.mkdir(parents=True, exist_ok=True)

        resolved_path.write_text(content, encoding="utf-8")
        bytes_written = len(content.encode("utf-8"))

        return {
            "path": _format_path(self.sandbox, resolved_path),
            "bytes_written": bytes_written,
            "success": True,
        }


class ListDirectoryTool(BaseToolAdapter):
    """Tool for listing directory contents safely within workspace bounds."""

    def __init__(self, workspace_root: Optional[Path] = None) -> None:
        self.sandbox = PathSandbox(workspace_root or Path.cwd())

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            manifest=ToolManifest(
                name="list_directory",
                version="1.0.0",
                description="List files and folders in a workspace directory.",
                permission_level=PermissionLevel.READ_ONLY,
                idempotent=True,
                read_only=True,
                side_effect_level=SideEffectLevel.NONE,
                timeout_sec=10.0,
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to directory (defaults to root).", "default": "."},
                },
            },
        )

    async def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        raw_path = params.get("path", ".")
        resolved_path = self.sandbox.validate_and_resolve(raw_path, must_exist=True)

        if not resolved_path.is_dir():
            raise ValueError(f"Path '{raw_path}' is not a directory.")

        target_dirs = [resolved_path]
        clean_raw = str(raw_path).lower().strip()
        if clean_raw == "desktop":
            for d in self.sandbox._get_desktop_dirs():
                if d not in target_dirs:
                    target_dirs.append(d)
        elif clean_raw == "documents":
            for d in self.sandbox._get_documents_dirs():
                if d not in target_dirs:
                    target_dirs.append(d)
        elif clean_raw == "downloads":
            for d in self.sandbox._get_downloads_dirs():
                if d not in target_dirs:
                    target_dirs.append(d)

        items = []
        seen_names = set()
        for t_dir in target_dirs:
            if not t_dir.is_dir():
                continue
            for item in t_dir.iterdir():
                if item.name not in seen_names:
                    seen_names.add(item.name)
                    items.append({
                        "name": item.name,
                        "is_directory": item.is_dir(),
                        "size_bytes": item.stat().st_size if item.is_file() else 0,
                    })

        return {
            "directory": _format_path(self.sandbox, resolved_path),
            "total_items": len(items),
            "items": items,
        }


class SearchFilesTool(BaseToolAdapter):
    """Tool for searching files by glob pattern inside workspace."""

    def __init__(self, workspace_root: Optional[Path] = None) -> None:
        self.sandbox = PathSandbox(workspace_root or Path.cwd())

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            manifest=ToolManifest(
                name="search_files",
                version="1.0.0",
                description="Search workspace files matching a glob pattern.",
                permission_level=PermissionLevel.READ_ONLY,
                idempotent=True,
                read_only=True,
                side_effect_level=SideEffectLevel.NONE,
                timeout_sec=15.0,
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern (e.g. *.py, **/*.md)."},
                    "path": {"type": "string", "description": "Subdirectory path to search in.", "default": "."},
                },
                "required": ["pattern"],
            },
        )

    async def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        pattern = params["pattern"]
        raw_path = params.get("path", ".")

        resolved_path = self.sandbox.validate_and_resolve(raw_path, must_exist=True)
        matched_files = []

        search_dirs = [resolved_path]
        clean_raw = str(raw_path).lower().strip()
        if clean_raw == "desktop":
            for d in self.sandbox._get_desktop_dirs():
                if d not in search_dirs:
                    search_dirs.append(d)
        elif clean_raw == "documents":
            for d in self.sandbox._get_documents_dirs():
                if d not in search_dirs:
                    search_dirs.append(d)
        elif clean_raw == "downloads":
            for d in self.sandbox._get_downloads_dirs():
                if d not in search_dirs:
                    search_dirs.append(d)

        for s_dir in search_dirs:
            if not s_dir.is_dir():
                continue
            for p in s_dir.glob(pattern):
                try:
                    clean_p = self.sandbox.validate_and_resolve(p)
                    if clean_p.is_file():
                        formatted = _format_path(self.sandbox, clean_p)
                        if formatted not in matched_files:
                            matched_files.append(formatted)
                except Exception:
                    continue

        return {
            "pattern": pattern,
            "matched_count": len(matched_files),
            "matches": matched_files[:100],  # Capped at 100 entries
        }
