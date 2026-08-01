"""
SearchMergeEngine combining and deduplicating parallel provider search results.
"""

from pathlib import Path
from typing import Dict, List
from jarvis.search.schemas import SearchMatch


class SearchMergeEngine:
    """Merges candidate matches from multiple providers, deduplicating by resolved path."""

    @classmethod
    def merge(cls, provider_results: List[List[SearchMatch]]) -> List[SearchMatch]:
        """Deduplicate and combine multi-provider match lists."""
        merged: Dict[str, SearchMatch] = {}

        for match_list in provider_results:
            for match in match_list:
                try:
                    canon_key = str(Path(match.path).resolve())
                except Exception:
                    canon_key = match.path.lower()

                if canon_key not in merged:
                    merged[canon_key] = match
                else:
                    # Update score if another provider gave a higher confidence score
                    existing = merged[canon_key]
                    if match.score > existing.score:
                        existing.score = match.score
                    # Merge highlights
                    if match.highlights:
                        for h in match.highlights:
                            if h not in existing.highlights:
                                existing.highlights.append(h)

        return list(merged.values())
