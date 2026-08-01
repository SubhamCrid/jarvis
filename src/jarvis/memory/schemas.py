"""
Typed contracts and schema definitions for the Jarvis Memory Platform.
"""

import time, uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MemoryType(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    USER_PROFILE = "user_profile"
    KNOWLEDGE_STORE = "knowledge_store"
    VECTOR = "vector"


class MemoryItem(BaseModel):
    """Universal memory record representation."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"mem-{uuid.uuid4().hex[:12]}")
    memory_type: MemoryType = MemoryType.WORKING
    key: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    tags: List[str] = Field(default_factory=list)
    session_id: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class MemoryQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    query_text: str
    memory_types: List[MemoryType] = Field(default_factory=lambda: [MemoryType.WORKING, MemoryType.SEMANTIC])
    session_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    min_confidence: float = 0.0
    limit: int = 20


class MemoryStoreRequest(BaseModel):
    key: str
    content: str
    memory_type: MemoryType = MemoryType.WORKING
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    session_id: Optional[str] = None


class MemorySearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    item: MemoryItem
    relevance_score: float = 1.0
    matched_by: str = "keyword"

