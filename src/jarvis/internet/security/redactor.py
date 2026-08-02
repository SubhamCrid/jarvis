"""
InternetRedactor for scrubbing API keys, cookies, auth headers, and tokens before logging or persistence.
"""

import re
from typing import Any, Dict


class InternetRedactor:
    """Scrubs sensitive authorization data, API tokens, and secret parameters."""

    PATTERNS = [
        (re.compile(r"(api[_-]?key|access[_-]?token|bearer|auth|password|secret)=([^&;\s]+)", re.IGNORECASE), r"\1=[REDACTED]"),
        (re.compile(r"Bearer\s+([A-Za-z0-9\-\._~\+\/]+=*)", re.IGNORECASE), r"Bearer [REDACTED]"),
        (re.compile(r"tvly-[A-Za-z0-9_-]{20,}", re.IGNORECASE), r"tvly-[REDACTED]"),
        (re.compile(r"BSB[A-Za-z0-9_-]{20,}", re.IGNORECASE), r"BSB[REDACTED]"),
    ]

    @classmethod
    def redact_text(cls, text: str) -> str:
        if not text or not isinstance(text, str):
            return text
        result = text
        for pattern, replacement in cls.PATTERNS:
            result = pattern.sub(replacement, result)
        return result

    @classmethod
    def redact_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        redacted = {}
        for key, value in data.items():
            key_lower = str(key).lower()
            if any(secret_kw in key_lower for secret_kw in ("key", "token", "auth", "secret", "password", "cookie")):
                redacted[key] = "[REDACTED]"
            elif isinstance(value, str):
                redacted[key] = cls.redact_text(value)
            elif isinstance(value, dict):
                redacted[key] = cls.redact_dict(value)
            else:
                redacted[key] = value
        return redacted
