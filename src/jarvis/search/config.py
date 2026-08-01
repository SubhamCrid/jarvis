"""
Central runtime configuration for Jarvis Search Platform.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class SearchConfig:
    """Central configuration for search indexing, root boundaries, and provider priority."""

    search_root: Path = field(default_factory=lambda: Path(os.getcwd()).resolve())
    max_results: int = 50
    default_timeout_sec: float = 10.0
    cache_ttl_sec: float = 60.0
    cache_max_entries: int = 200
    fuzzy_threshold: float = 0.6
    enable_index_manager: bool = True
    index_db_path: Path = field(default_factory=lambda: Path("data/search/index.db").resolve())
    provider_priority: List[str] = field(
        default_factory=lambda: ["everything", "windows_index", "ripgrep", "filesystem"]
    )
    max_streaming_buffer: int = 100

    @classmethod
    def from_env(cls, search_root: Optional[Path] = None) -> "SearchConfig":
        """Instantiate config reading overrides from environment variables (JARVIS_SEARCH_*)."""
        root = search_root or Path(os.getenv("JARVIS_SEARCH_ROOT", os.getcwd())).resolve()
        max_res = int(os.getenv("JARVIS_SEARCH_MAX_RESULTS", "50"))
        timeout = float(os.getenv("JARVIS_SEARCH_TIMEOUT_SEC", "10.0"))
        cache_ttl = float(os.getenv("JARVIS_SEARCH_CACHE_TTL_SEC", "60.0"))
        fuzzy_th = float(os.getenv("JARVIS_SEARCH_FUZZY_THRESHOLD", "0.6"))

        return cls(
            search_root=root,
            max_results=max_res,
            default_timeout_sec=timeout,
            cache_ttl_sec=cache_ttl,
            fuzzy_threshold=fuzzy_th,
        )
