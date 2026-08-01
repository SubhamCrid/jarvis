"""
SearchRootSandbox enforcing path confinement for search operations.
"""

from pathlib import Path
from typing import Union


class SearchSandboxError(PermissionError):
    """Raised when a search path escapes allowed search boundaries."""

    pass


class SearchRootSandbox:
    """Canonicalizes paths and enforces root boundary confinement for search results."""

    def __init__(self, search_root: Union[str, Path]) -> None:
        self.search_root = Path(search_root).resolve()

    def validate_path(self, raw_path: Union[str, Path]) -> Path:
        """
        Validate and resolve candidate search path against search root.
        Raises SearchSandboxError if target escapes root boundary.
        """
        if not raw_path:
            raise ValueError("Path cannot be empty.")

        path_obj = Path(raw_path)
        if not path_obj.is_absolute():
            candidate = (self.search_root / path_obj).resolve()
        else:
            candidate = path_obj.resolve()

        try:
            candidate.relative_to(self.search_root)
        except ValueError:
            raise SearchSandboxError(
                f"Search root traversal blocked: '{raw_path}' resolves to '{candidate}', "
                f"outside allowed root '{self.search_root}'."
            )

        return candidate

    def is_within_root(self, raw_path: Union[str, Path]) -> bool:
        """Check if path is inside search root without raising an exception."""
        try:
            self.validate_path(raw_path)
            return True
        except Exception:
            return False
