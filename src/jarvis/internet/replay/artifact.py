"""
ReplayArtifact and StepRecord schemas for Internet Replay Framework.
"""

import time
from typing import Any, Dict, List
from pydantic import BaseModel, Field
from jarvis.internet.ids import ReplayId
from jarvis.internet.schemas import InternetDocument


class StepRecord(BaseModel):
    step_id: str
    action: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0


class ReplayArtifact(BaseModel):
    """Serializable replay artifact supporting 100% offline pipeline replay."""

    version: int = 1
    replay_id: str = Field(default_factory=lambda: ReplayId().value)
    query: str
    strategy_name: str
    step_records: List[StepRecord] = Field(default_factory=list)
    final_documents: List[InternetDocument] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)
