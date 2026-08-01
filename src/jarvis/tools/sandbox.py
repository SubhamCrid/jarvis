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
    Enforces strict path normalization, symlink resolution, and root confinement.
    Prevents path traversal attacks (e.g. '../../../etc/passwd') and symlink escapes.
    """

    def __init__(self, workspace_root: Union[str, Path]) -> None:
        self.workspace_root = Path(workspace_root).resolve()

    def validate_and_resolve(self, raw_path: Union[str, Path], must_exist: bool = False) -> Path:
        """
        Validate, normalize, and resolve a file or directory path.

        :param raw_path: Input path string or Path object.
        :param must_exist: If True, raise FileNotFoundError if target does not exist.
        :return: Absolute resolved Path object within workspace_root.
        :raises PathTraversalError: If the target path escapes the workspace_root.
        :raises FileNotFoundError: If must_exist is True and path does not exist.
        """
        if not raw_path:
            raise ValueError("Path string cannot be empty.")

        path_obj = Path(raw_path)

        # Handle relative paths relative to workspace root
        if not path_obj.is_absolute():
            candidate = (self.workspace_root / path_obj).resolve()
        else:
            candidate = path_obj.resolve()

        # Enforce root confinement using is_relative_to
        try:
            candidate.relative_to(self.workspace_root)
        except ValueError:
            raise PathTraversalError(
                f"Path traversal blocked: target '{raw_path}' resolves to '{candidate}', "
                f"which is outside workspace boundary '{self.workspace_root}'."
            )

        if must_exist and not candidate.exists():
            raise FileNotFoundError(f"File or directory does not exist: '{candidate}'")

        return candidate
