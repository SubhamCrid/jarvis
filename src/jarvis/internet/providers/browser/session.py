"""
BrowserSessionType Enum for explicit context isolation semantics.
EPHEMERAL (default), PERSISTENT, AUTHENTICATED.
"""

from enum import Enum


class BrowserSessionType(str, Enum):
    EPHEMERAL = "ephemeral"        # Fresh isolated context, destroyed immediately post-execution
    PERSISTENT = "persistent"      # Retained profile context across multi-step research session
    AUTHENTICATED = "authenticated"  # Isolated context preserving domain authentication state
