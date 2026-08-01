"""
Central ContextManager for orchestrating ephemeral runtime context and snapshots across Jarvis platforms.
"""

from typing import Any, Dict, Optional
from jarvis.context.schemas import ContextScope, ContextSnapshot
from jarvis.context.store import ContextStore


class ContextManager:
    """Central manager providing scoped ephemeral context access and context snapshots."""

    def __init__(self, store: Optional[ContextStore] = None) -> None:
        self.store = store or ContextStore()

    def set_context(
        self,
        key: str,
        value: Any,
        scope: ContextScope = ContextScope.EPHEMERAL,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        self.store.set(key, value, scope=scope, ttl_seconds=ttl_seconds)

    def get_context(self, key: str, scope: ContextScope = ContextScope.EPHEMERAL) -> Optional[Any]:
        return self.store.get(key, scope=scope)

    def clear_context_scope(self, scope: ContextScope) -> int:
        return self.store.clear_scope(scope)

    def take_snapshot(self, session_id: str = "default_session") -> ContextSnapshot:
        desktop_ctx = self.store.get_all(ContextScope.DESKTOP)
        task_ctx = self.store.get_all(ContextScope.TASK)
        env_ctx = self.store.get_all(ContextScope.ENVIRONMENT)

        scoped_vars = {
            scope.value: self.store.get_all(scope) for scope in ContextScope
        }

        return ContextSnapshot(
            session_id=session_id,
            active_task_id=task_ctx.get("active_task_id"),
            focused_app=desktop_ctx.get("focused_app", ""),
            active_window=desktop_ctx.get("active_window", ""),
            current_file=desktop_ctx.get("current_file", ""),
            current_url=desktop_ctx.get("current_url", ""),
            clipboard_preview=desktop_ctx.get("clipboard_preview", ""),
            environment_vars={str(k): str(v) for k, v in env_ctx.items()},
            scoped_variables=scoped_vars,
        )
