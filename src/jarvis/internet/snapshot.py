"""
Immutable ExecutionSnapshot for post-mortem debugging and historical analysis.
"""

import time
from typing import Any, Dict, List
from pydantic import BaseModel, Field
from jarvis.internet.ids import ExecutionId
from jarvis.internet.schemas import InternetDocument


class ExecutionSnapshot(BaseModel):
    """Immutable snapshot of complete pipeline execution state."""

    version: int = 1
    execution_id: str = Field(default_factory=lambda: ExecutionId().value)
    query: str
    strategy_name: str
    plan_json: str
    providers_used: List[str] = Field(default_factory=list)
    configuration_dump: Dict[str, Any] = Field(default_factory=dict)
    results: List[InternetDocument] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)
