"""
Path sandbox implementation for strictly confining file system operations
within the configured workspace root directory.
"""

from pathlib import Path
from typing import Union


class PathTraversalError(PermissionError):
    """Raised when a file path escapes the configured workspace root boundary."""

    pass


class PathSandbox:
    """
    Enforces strict path normalization, symlink resolution, and allowed root confinement.
    Confines file operations to workspace_root and user home directory (Desktop, Downloads, Documents).
    """

    def __init__(self, workspace_root: Union[str, Path]) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.home_root = Path.home().resolve()
        self.allowed_roots = [
            self.workspace_root,
            (self.home_root / "Desktop").resolve(),
            (self.home_root / "Downloads").resolve(),
            (self.home_root / "Documents").resolve(),
        ]

    def validate_and_resolve(self, raw_path: Union[str, Path], must_exist: bool = False) -> Path:
        """
        Validate, normalize, and resolve a file or directory path.

        :param raw_path: Input path string or Path object.
        :param must_exist: If True, raise FileNotFoundError if target does not exist.
        :return: Absolute resolved Path object within allowed workspace/home boundaries.
        :raises PathTraversalError: If target path escapes allowed roots.
        :raises FileNotFoundError: If must_exist is True and path does not exist.
        """
        if not raw_path:
            raise ValueError("Path string cannot be empty.")

        raw_str = str(raw_path).strip()
        path_obj = Path(raw_str)
        lower_str = raw_str.lower().replace("\\", "/")

        # Handle system location aliases (Desktop, Downloads, Documents)
        if lower_str == "desktop" or lower_str.startswith("desktop/"):
            sub_path = raw_str[7:].lstrip("/\\")
            candidate = (self.home_root / "Desktop" / sub_path).resolve()
        elif lower_str == "downloads" or lower_str.startswith("downloads/"):
            sub_path = raw_str[9:].lstrip("/\\")
            candidate = (self.home_root / "Downloads" / sub_path).resolve()
        elif lower_str == "documents" or lower_str.startswith("documents/"):
            sub_path = raw_str[9:].lstrip("/\\")
            candidate = (self.home_root / "Documents" / sub_path).resolve()
        elif not path_obj.is_absolute():
            ws_candidate = (self.workspace_root / path_obj).resolve()
            if ws_candidate.exists() or not must_exist:
                candidate = ws_candidate
            else:
                # Fallback: check if target file exists on Desktop or Downloads
                desktop_candidate = (self.home_root / "Desktop" / path_obj).resolve()
                downloads_candidate = (self.home_root / "Downloads" / path_obj).resolve()
                if desktop_candidate.exists():
                    candidate = desktop_candidate
                elif downloads_candidate.exists():
                    candidate = downloads_candidate
                else:
                    candidate = ws_candidate
        else:
            candidate = path_obj.resolve()

        # Enforce root confinement using allowed_roots
        allowed = False
        for root in self.allowed_roots:
            try:
                candidate.relative_to(root)
                allowed = True
                break
            except ValueError:
                pass

        if not allowed:
            raise PathTraversalError(
                f"Path traversal blocked: target '{raw_path}' resolves to '{candidate}', "
                f"which is outside allowed boundaries '{self.workspace_root}'."
            )

        if must_exist and not candidate.exists():
            raise FileNotFoundError(f"File or directory does not exist: '{candidate}'")

        return candidate
