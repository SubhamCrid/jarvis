"""
ReplayPlayer for replaying executions 100% offline from a ReplayArtifact.
Has ZERO dependencies on live external providers or network sockets.
"""

from typing import Optional
from jarvis.internet.replay.artifact import ReplayArtifact
from jarvis.internet.schemas import InternetResult


class ReplayPlayer:
    """Replays execution offline from a ReplayArtifact."""

    def replay(self, artifact: ReplayArtifact) -> InternetResult:
        """Reconstruct InternetResult directly from artifact without network calls."""
        return InternetResult(
            query=artifact.query,
            strategy_used=f"Replay:{artifact.strategy_name}",
            documents=artifact.final_documents,
            execution_time_ms=0.0,
            offline_fallback_used=True,
            metadata={"replay_id": artifact.replay_id, "replayed": True},
        )
