"""
SearchSessionStore for maintaining conversational search state across voice interactions.
Supports pagination ('show next 10') and index selection ('open 3rd result').
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from jarvis.search.schemas import SearchMatch, SearchQuery


@dataclass
class SearchSession:
    session_id: str
    last_query: Optional[SearchQuery] = None
    last_matches: List[SearchMatch] = field(default_factory=list)
    cursor_page: int = 0
    page_size: int = 10


class SearchSessionStore:
    """Stores and retrieves SearchSession instances by session_id."""

    def __init__(self) -> None:
        self._sessions: Dict[str, SearchSession] = {}

    def get_or_create_session(self, session_id: str) -> SearchSession:
        """Get or instantiate SearchSession for a session_id."""
        if session_id not in self._sessions:
            self._sessions[session_id] = SearchSession(session_id=session_id)
        return self._sessions[session_id]

    def update_session(self, session_id: str, query: SearchQuery, matches: List[SearchMatch]) -> None:
        """Update last query and matches for session."""
        sess = self.get_or_create_session(session_id)
        sess.last_query = query
        sess.last_matches = matches
        sess.cursor_page = 0

    def get_next_page(self, session_id: str, page_size: int = 10) -> List[SearchMatch]:
        """Fetch next page of results for an ongoing voice search session."""
        sess = self.get_or_create_session(session_id)
        if not sess.last_matches:
            return []

        sess.cursor_page += 1
        start_idx = sess.cursor_page * page_size
        end_idx = start_idx + page_size
        return sess.last_matches[start_idx:end_idx]

    def get_result_by_index(self, session_id: str, match_index: int) -> Optional[SearchMatch]:
        """Fetch a specific result by its 1-indexed position from the last search."""
        sess = self.get_or_create_session(session_id)
        idx = match_index - 1
        if 0 <= idx < len(sess.last_matches):
            return sess.last_matches[idx]
        return None
