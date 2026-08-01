"""
Transient TTL-based ContextStore for managing ephemeral variables and active state.
"""

import time
from typing import Any, Dict, List, Optional
from jarvis.context.schemas import ContextItem, ContextScope


class ContextStore:
    """Thread-safe in-memory store for ephemeral, TTL-managed context variables."""

    def __init__(self) -> None:
        # Scope -> Key -> ContextItem
        self._store: Dict[ContextScope, Dict[str, ContextItem]] = {
            scope: {} for scope in ContextScope
        }

    def set(
        self,
        key: str,
        value: Any,
        scope: ContextScope = ContextScope.EPHEMERAL,
        ttl_seconds: Optional[float] = None,
        tags: Optional[List[str]] = None,
    ) -> ContextItem:
        now = time.time()
        expires_at = (now + ttl_seconds) if ttl_seconds is not None else None

        item = ContextItem(
            key=key,
            value=value,
            scope=scope,
            ttl_seconds=ttl_seconds,
            created_at=now,
            expires_at=expires_at,
            tags=tags or [],
        )
        self._store[scope][key] = item
        return item

    def get(self, key: str, scope: ContextScope = ContextScope.EPHEMERAL) -> Optional[Any]:
        self.cleanup_expired()
        item = self._store.get(scope, {}).get(key)
        if item and not item.is_expired():
            return item.value
        return None

    def remove(self, key: str, scope: ContextScope = ContextScope.EPHEMERAL) -> bool:
        if key in self._store.get(scope, {}):
            del self._store[scope][key]
            return True
        return False

    def clear_scope(self, scope: ContextScope) -> int:
        count = len(self._store.get(scope, {}))
        self._store[scope].clear()
        return count

    def cleanup_expired(self) -> int:
        now = time.time()
        expired_count = 0
        for scope, items in self._store.items():
            to_remove = [k for k, item in items.items() if item.is_expired(now)]
            for k in to_remove:
                del items[k]
                expired_count += 1
        return expired_count

    def get_all(self, scope: ContextScope) -> Dict[str, Any]:
        self.cleanup_expired()
        return {k: item.value for k, item in self._store.get(scope, {}).items()}
