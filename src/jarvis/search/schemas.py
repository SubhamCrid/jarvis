"""
Typed contracts and schemas for Jarvis Search Platform.
Fully model-agnostic and provider-agnostic.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SearchTargetType(str, Enum):
    FILE = "file"
    FOLDER = "folder"
    CONTENT = "content"
    APP = "app"
    RECENT = "recent"
    ANY = "any"


@dataclass
class SearchProviderManifest:
    """Capability manifest declared by search providers."""

    name: str
    supports_filename: bool = True
    supports_content: bool = False
    supports_regex: bool = False
    supports_metadata: bool = True
    supports_apps: bool = False
    supports_recent: bool = True
    confidence_score: float = 1.0


class SearchQuery(BaseModel):
    """Normalized search query request representation."""

    raw_query: str
    clean_query: str = ""
    target_type: SearchTargetType = SearchTargetType.ANY
    search_root: Optional[str] = None
    extensions: List[str] = Field(default_factory=list)
    min_size_bytes: Optional[int] = None
    max_size_bytes: Optional[int] = None
    modified_after: Optional[float] = None
    modified_before: Optional[float] = None
    fuzzy: bool = False
    max_results: int = 50
    session_id: Optional[str] = None


class SearchMatch(BaseModel):
    """Result match item returned by search providers."""

    path: str
    filename: str
    target_type: SearchTargetType = SearchTargetType.FILE
    score: float = 0.0
    size_bytes: int = 0
    modified_at: float = Field(default_factory=time.time)
    highlights: List[str] = Field(default_factory=list)
    provider_name: str = "unknown"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchExecutionPlan(BaseModel):
    """Execution plan constructed by SearchQueryPlanner."""

    plan_id: str = Field(default_factory=lambda: f"plan-{uuid.uuid4().hex[:8]}")
    query: SearchQuery
    primary_providers: List[str] = Field(default_factory=list)
    fallback_providers: List[str] = Field(default_factory=list)
    strategy: str = "filename_search"  # filename_search, content_search, recent_search, app_search
    parallel_execution: bool = True


class SearchResponse(BaseModel):
    """Aggregated final response container."""

    query: str
    matches: List[SearchMatch] = Field(default_factory=list)
    total_found: int = 0
    providers_used: List[str] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    cached: bool = False


class SearchError(BaseModel):
    """Normalized search error contract."""

    code: str
    message: str
    retryable: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)
