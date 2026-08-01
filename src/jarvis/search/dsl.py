"""
Search DSL Parser module for structured query syntax interpretation.
Parses query expressions such as:
'kind:file ext:pdf,py size>10MB modified:last7days path:Downloads report'
"""

import re
import time
from typing import List, Optional, Tuple
from jarvis.search.schemas import SearchQuery, SearchTargetType


class SearchDSLParser:
    """Parses domain-specific search expressions into structured SearchQuery models."""

    KIND_MAP = {
        "file": SearchTargetType.FILE,
        "files": SearchTargetType.FILE,
        "folder": SearchTargetType.FOLDER,
        "folders": SearchTargetType.FOLDER,
        "dir": SearchTargetType.FOLDER,
        "directory": SearchTargetType.FOLDER,
        "content": SearchTargetType.CONTENT,
        "text": SearchTargetType.CONTENT,
        "app": SearchTargetType.APP,
        "apps": SearchTargetType.APP,
        "recent": SearchTargetType.RECENT,
    }

    SIZE_PATTERN = re.compile(r"size([><=]+)(\d+)(kb|mb|gb)?", re.IGNORECASE)
    MODIFIED_PATTERN = re.compile(r"modified:(last\d+[dhwmy]|today|yesterday)", re.IGNORECASE)

    @classmethod
    def parse(cls, query_str: str) -> SearchQuery:
        """Parse raw search query string into structured SearchQuery."""
        if not query_str:
            return SearchQuery(raw_query="")

        tokens = query_str.strip().split()
        clean_tokens: List[str] = []
        target_type = SearchTargetType.ANY
        extensions: List[str] = []
        search_root: Optional[str] = None
        min_size: Optional[int] = None
        max_size: Optional[int] = None
        modified_after: Optional[float] = None
        fuzzy = False

        for token in tokens:
            lower = token.lower()

            if lower.startswith("kind:") or lower.startswith("type:"):
                val = lower.split(":", 1)[1]
                target_type = cls.KIND_MAP.get(val, SearchTargetType.ANY)

            elif lower.startswith("ext:") or lower.startswith("extension:"):
                ext_str = lower.split(":", 1)[1]
                for ext in ext_str.split(","):
                    clean_ext = ext.lstrip(".")
                    if clean_ext:
                        extensions.append(clean_ext)

            elif lower.startswith("path:") or lower.startswith("dir:"):
                search_root = token.split(":", 1)[1]

            elif lower.startswith("fuzzy:"):
                val = lower.split(":", 1)[1]
                fuzzy = val in ("true", "1", "yes")

            elif cls.SIZE_PATTERN.match(lower):
                m = cls.SIZE_PATTERN.match(lower)
                if m:
                    op, num, unit = m.groups()
                    bytes_val = int(num)
                    if unit == "kb":
                        bytes_val *= 1024
                    elif unit == "mb":
                        bytes_val *= 1024 * 1024
                    elif unit == "gb":
                        bytes_val *= 1024 * 1024 * 1024

                    if ">" in op:
                        min_size = bytes_val
                    elif "<" in op:
                        max_size = bytes_val

            elif lower.startswith("modified:"):
                m = cls.MODIFIED_PATTERN.match(lower)
                if m:
                    val = m.group(1)
                    now = time.time()
                    if val == "today":
                        modified_after = now - 86400
                    elif val == "yesterday":
                        modified_after = now - (86400 * 2)
                    elif val.startswith("last"):
                        digit_match = re.search(r"\d+", val)
                        num_days = int(digit_match.group()) if digit_match else 7
                        if "d" in val:
                            modified_after = now - (num_days * 86400)
                        elif "h" in val:
                            modified_after = now - (num_days * 3600)
                        elif "w" in val:
                            modified_after = now - (num_days * 7 * 86400)

            else:
                clean_tokens.append(token)

        clean_text = " ".join(clean_tokens)

        return SearchQuery(
            raw_query=query_str,
            clean_query=clean_text,
            target_type=target_type,
            search_root=search_root,
            extensions=extensions,
            min_size_bytes=min_size,
            max_size_bytes=max_size,
            modified_after=modified_after,
            fuzzy=fuzzy,
        )
