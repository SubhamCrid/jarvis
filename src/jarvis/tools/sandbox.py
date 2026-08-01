"""
Path sandbox implementation for strictly confining file system operations
within the configured workspace root directory.
"""

from pathlib import Path
from typing import List, Union


class PathTraversalError(PermissionError):
    """Raised when a file path escapes the configured workspace root boundary."""

    pass


class PathSandbox:
    """
    Enforces strict path normalization, symlink resolution, and allowed root confinement.
    Confines file operations to workspace_root and user home/OneDrive directories (Desktop, Downloads, Documents).
    """

    def __init__(self, workspace_root: Union[str, Path]) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.home_root = Path.home().resolve()
        self.allowed_roots = [self.workspace_root]
        for d in self._get_desktop_dirs() + self._get_downloads_dirs() + self._get_documents_dirs():
            if d not in self.allowed_roots:
                self.allowed_roots.append(d)

    def _get_desktop_dirs(self) -> List[Path]:
        candidates = [
            self.home_root / "Desktop",
            self.home_root / "OneDrive" / "Desktop",
        ]
        try:
            for p in self.home_root.glob("OneDrive*/Desktop"):
                if p not in candidates:
                    candidates.append(p)
        except Exception:
            pass
        return [c.resolve() for c in candidates if c.exists()]

    def _get_downloads_dirs(self) -> List[Path]:
        candidates = [
            self.home_root / "Downloads",
            self.home_root / "OneDrive" / "Downloads",
        ]
        try:
            for p in self.home_root.glob("OneDrive*/Downloads"):
                if p not in candidates:
                    candidates.append(p)
        except Exception:
            pass
        return [c.resolve() for c in candidates if c.exists()]

    def _get_documents_dirs(self) -> List[Path]:
        candidates = [
            self.home_root / "Documents",
            self.home_root / "OneDrive" / "Documents",
        ]
        try:
            for p in self.home_root.glob("OneDrive*/Documents"):
                if p not in candidates:
                    candidates.append(p)
        except Exception:
            pass
        return [c.resolve() for c in candidates if c.exists()]

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

        candidate = None

        # Handle system location aliases (Desktop, Downloads, Documents) including OneDrive
        if lower_str == "desktop" or lower_str.startswith("desktop/"):
            sub_path = raw_str[7:].lstrip("/\\")
            dt_dirs = self._get_desktop_dirs()
            if sub_path:
                for dt in dt_dirs:
                    cand = (dt / sub_path).resolve()
                    if cand.exists() or not candidate:
                        candidate = cand
                        if cand.exists():
                            break
            if not candidate and dt_dirs:
                candidate = dt_dirs[0]
            if not candidate:
                candidate = (self.home_root / "Desktop" / sub_path).resolve()

        elif lower_str == "downloads" or lower_str.startswith("downloads/"):
            sub_path = raw_str[9:].lstrip("/\\")
            dl_dirs = self._get_downloads_dirs()
            if sub_path:
                for dl in dl_dirs:
                    cand = (dl / sub_path).resolve()
                    if cand.exists() or not candidate:
                        candidate = cand
                        if cand.exists():
                            break
            if not candidate and dl_dirs:
                candidate = dl_dirs[0]
            if not candidate:
                candidate = (self.home_root / "Downloads" / sub_path).resolve()

        elif lower_str == "documents" or lower_str.startswith("documents/"):
            sub_path = raw_str[9:].lstrip("/\\")
            doc_dirs = self._get_documents_dirs()
            if sub_path:
                for doc in doc_dirs:
                    cand = (doc / sub_path).resolve()
                    if cand.exists() or not candidate:
                        candidate = cand
                        if cand.exists():
                            break
            if not candidate and doc_dirs:
                candidate = doc_dirs[0]
            if not candidate:
                candidate = (self.home_root / "Documents" / sub_path).resolve()

        elif not path_obj.is_absolute():
            ws_candidate = (self.workspace_root / path_obj).resolve()
            if ws_candidate.exists() or not must_exist:
                candidate = ws_candidate
            else:
                # Fallback: check if target file exists across Desktop, Downloads, Documents
                found_candidate = None
                for loc_dir in self._get_desktop_dirs() + self._get_downloads_dirs() + self._get_documents_dirs():
                    cand = (loc_dir / path_obj).resolve()
                    if cand.exists():
                        found_candidate = cand
                        break
                candidate = found_candidate or ws_candidate
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
