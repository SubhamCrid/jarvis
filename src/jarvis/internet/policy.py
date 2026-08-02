"""
InternetPolicy for domain trust, privacy rules, rate limits, and policy evaluation.
"""

from typing import List, Optional
from jarvis.internet.config import InternetConfig
from jarvis.internet.exceptions import PolicyViolationError
from jarvis.internet.security.sandbox import URLSandbox


class InternetPolicy:
    """Evaluates privacy, domain trust, policy mode, and security boundaries."""

    def __init__(self, config: Optional[InternetConfig] = None) -> None:
        self.config = config or InternetConfig()
        self.sandbox = URLSandbox(
            allowed_protocols=self.config.security.allowed_protocols,
            blocked_domains=self.config.security.blocked_domains,
            allowed_domains=self.config.security.allowed_domains,
            enable_ssrf_protection=self.config.security.ssrf_protection,
        )

    def evaluate_url(self, url: str) -> str:
        """
        Evaluate if a target URL is permissible under current policy mode and security rules.
        """
        if not self.config.enabled:
            raise PolicyViolationError("Internet platform is currently disabled in system configuration.")

        return self.sandbox.validate_url(url)
