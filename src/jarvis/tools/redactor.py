"""
Secret-aware output redactor preventing sensitive tokens, credentials, and keys
from leaking into logs, trace files, or LLM context prompts.
"""

import re
from typing import Any, Dict, List, Union


class OutputRedactor:
    """Regex-based secret scrubber for strings, dictionaries, and nested data structures."""

    PATTERNS = [
        # Bearer / JWT Tokens
        (re.compile(r"Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
        # OpenAI / Anthropic / Groq / Generic API Keys (e.g. sk-..., gsk_...)
        (re.compile(r"\b(?:sk|gsk|pk|api|key)-[A-Za-z0-9_-]{16,}\b", re.IGNORECASE), "[REDACTED_API_KEY]"),
        # AWS Access Keys & Secret Keys
        (re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY_ID]"),
        (re.compile(r"\b[A-Za-z0-9/+=]{40}\b(?=.*(?:aws|secret|key))", re.IGNORECASE), "[REDACTED_AWS_SECRET]"),
        # Private RSA / EC / SSH Keys
        (re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END\s+(?:RSA\s+)?PRIVATE\s+KEY-----"), "[REDACTED_PRIVATE_KEY]"),
        # Generic Passwords in key-value pairs (e.g., password=secret, secret_key: "abc")
        (re.compile(r"(?i)\b(password|passwd|secret|api_key|token|access_token)\b\s*[:=]\s*['\"]?([^\s'\";]+)['\"]?"), r"\1=[REDACTED]"),
    ]

    @classmethod
    def redact_text(cls, text: str) -> str:
        """Scrub secret patterns from input string."""
        if not text:
            return ""
        scrubbed = text
        for pattern, replacement in cls.PATTERNS:
            scrubbed = pattern.sub(replacement, scrubbed)
        return scrubbed

    @classmethod
    def redact_data(cls, data: Any) -> Any:
        """Recursively scrub secrets from dictionaries, lists, strings, or numbers."""
        if isinstance(data, str):
            return cls.redact_text(data)
        elif isinstance(data, dict):
            new_dict = {}
            for k, v in data.items():
                if isinstance(k, str) and any(kw in k.lower() for kw in ("password", "secret", "token", "api_key", "private_key")):
                    new_dict[k] = "[REDACTED]"
                else:
                    new_dict[k] = cls.redact_data(v)
            return new_dict
        elif isinstance(data, list):
            return [cls.redact_data(item) for item in data]
        return data
