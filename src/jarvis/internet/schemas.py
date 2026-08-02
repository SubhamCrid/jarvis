"""
Typed domain models for jarvis.internet platform.
Strictly typed Pydantic models preventing raw dictionary leakage across boundaries.
"""

import time
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BrowserCapabilities(BaseModel):
    """Capabilities advertised by a BrowserProvider implementation."""

    supports_extensions: bool = False
    supports_persistent_profiles: bool = True
    supports_downloads: bool = True
    supports_headful: bool = False
    supports_streaming_dom: bool = True
    stealth_level: str = "high"


class SearchHit(BaseModel):
    """Standardized search hit returned by SearchProvider implementations."""

    title: str
    url: str
    snippet: str
    engine: str
    score: float = 0.0
    published_date: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FetchedPage(BaseModel):
    """Raw HTTP page fetched by FetchProvider implementation."""

    url: str
    status_code: int
    content_type: str = "text/html"
    raw_content: str = ""
    headers: Dict[str, str] = Field(default_factory=dict)
    execution_time_ms: float = 0.0


class ExtractedDocument(BaseModel):
    """Clean text document extracted by ExtractionProvider implementation."""

    url: str
    title: str
    clean_markdown: str
    author: Optional[str] = None
    published_date: Optional[str] = None
    token_count: int = 0
    extractor_used: str = "default"


class Citation(BaseModel):
    """Source attribution for extracted facts."""

    source_url: str
    title: str
    snippet: str
    veracity_score: float = 1.0


class Evidence(BaseModel):
    """Verification evidence for factual claims."""

    claim: str
    supporting_sources: List[str] = Field(default_factory=list)
    contradicting_sources: List[str] = Field(default_factory=list)
    confidence: float = 1.0


class VerificationResult(BaseModel):
    """Multi-source verification outcome."""

    verified: bool = True
    confidence_score: float = 1.0
    conflicting_claims: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    evidences: List[Evidence] = Field(default_factory=list)


class InternetDocument(BaseModel):
    """Unified document representation ready for consumption by LLM or Assistant."""

    doc_id: str = Field(default_factory=lambda: f"doc-{uuid.uuid4().hex[:8]}")
    url: str
    title: str
    content: str
    summary: str = ""
    citations: List[Citation] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InternetResult(BaseModel):
    """Final typed result output produced by InternetPlatform pipeline execution."""

    query: str
    strategy_used: str
    documents: List[InternetDocument] = Field(default_factory=list)
    verification: Optional[VerificationResult] = None
    execution_time_ms: float = 0.0
    offline_fallback_used: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
