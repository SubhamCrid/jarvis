"""
Hierarchical configuration schema for jarvis.internet platform.
Production-grade configuration management with versioning, health weights, and fail-fast startup validation.
"""

from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
from jarvis.internet.exceptions import PolicyViolationError


class HealthWeightsConfig(BaseModel):
    success_weight: float = 0.4
    latency_weight: float = 0.3
    reliability_weight: float = 0.2
    freshness_weight: float = 0.1


class SearchProvidersConfig(BaseModel):
    default: str = "duckduckgo"
    enabled: List[str] = Field(default_factory=lambda: ["duckduckgo", "wikipedia", "arxiv"])


class BrowserRecyclingConfig(BaseModel):
    max_tasks_per_context: int = 50
    max_uptime_sec: float = 1800.0
    max_idle_sec: float = 30.0
    max_memory_mb: int = 300


class BrowserConfig(BaseModel):
    default_engine: str = "camoufox"
    headless: bool = True
    idle_timeout_sec: float = 30.0
    recycling: BrowserRecyclingConfig = Field(default_factory=BrowserRecyclingConfig)


class ProvidersConfig(BaseModel):
    search: SearchProvidersConfig = Field(default_factory=SearchProvidersConfig)
    fetch_default: str = "httpx"
    extraction_default: str = "trafilatura"
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    ranking_default: str = "bm25"
    cache_enabled: bool = True
    cache_ttl_sec: int = 86400
    verification_enabled: bool = True


class LimitsConfig(BaseModel):
    max_concurrent_requests: int = 5
    max_page_size_bytes: int = 524288  # 512 KB cap
    max_redirects: int = 3
    max_domains_per_query: int = 4
    max_extraction_tokens: int = 2048
    per_provider_rate_limit_rps: float = 2.0
    memory_budget_mb: int = 50


class SecurityConfig(BaseModel):
    ssrf_protection: bool = True
    block_private_subnets: bool = True
    allowed_protocols: List[str] = Field(default_factory=lambda: ["http", "https"])
    blocked_domains: List[str] = Field(default_factory=list)
    allowed_domains: List[str] = Field(default_factory=list)


class InternetConfig(BaseModel):
    """Master configuration for jarvis.internet platform."""

    enabled: bool = True
    version: int = 1
    policy_mode: str = "BALANCED"  # STRICT, BALANCED, PERMISSIVE
    db_path: str = "data/sessions/jarvis.db"
    health_weights: HealthWeightsConfig = Field(default_factory=HealthWeightsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    def validate_startup(self) -> None:
        """Fail-fast validation for startup configuration integrity."""
        # 1. Check health weights sum to ~1.0
        hw = self.health_weights
        total_weight = hw.success_weight + hw.latency_weight + hw.reliability_weight + hw.freshness_weight
        if abs(total_weight - 1.0) > 0.01:
            raise PolicyViolationError(f"Health weights must sum to 1.0 (got {total_weight}).")

        # 2. Check resource limits
        if self.limits.max_concurrent_requests <= 0:
            raise PolicyViolationError("max_concurrent_requests must be > 0.")
        if self.limits.max_page_size_bytes <= 0:
            raise PolicyViolationError("max_page_size_bytes must be > 0.")

        # 3. Check SQLite directory write access if not in-memory
        if self.db_path != ":memory:":
            db_dir = Path(self.db_path).parent
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise PolicyViolationError(f"Cannot create or write to SQLite directory '{db_dir}': {e}") from e


def load_internet_config(raw_dict: Optional[dict] = None) -> InternetConfig:
    """Load and validate InternetConfig from dictionary or return defaults."""
    if not raw_dict:
        config = InternetConfig()
    else:
        config = InternetConfig.model_validate(raw_dict)
    config.validate_startup()
    return config
