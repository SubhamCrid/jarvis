"""
ReplayDataset container for storing sets of ReplayArtifacts as CI regression datasets.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from jarvis.internet.replay.artifact import ReplayArtifact


class ReplayDataset(BaseModel):
    """Dataset bundling multiple ReplayArtifact instances for regression testing and benchmarking."""

    version: int = 1
    dataset_name: str = "default_regression_dataset"
    artifacts: List[ReplayArtifact] = Field(default_factory=list)

    def add_artifact(self, artifact: ReplayArtifact) -> None:
        self.artifacts.append(artifact)

    def get_artifact_by_query(self, query: str) -> Optional[ReplayArtifact]:
        for art in self.artifacts:
            if art.query.lower().strip() == query.lower().strip():
                return art
        return None
