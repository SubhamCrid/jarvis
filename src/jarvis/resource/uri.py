"""
Universal Resource Identifier (ResourceURI) parser and builder utilities.
Supports file://, app://, search://, memory://, browser://, note://, docker://, git://, db://.
"""

from typing import Dict, Any, Optional
from urllib.parse import urlparse, unquote, quote


class ResourceURI:
    """
    Canonical parser and builder for Jarvis Universal URIs.
    """

    SUPPORTED_SCHEMES = {
        "file",
        "app",
        "search",
        "memory",
        "browser",
        "note",
        "docker",
        "git",
        "db",
        "custom",
    }

    def __init__(self, raw_uri: str) -> None:
        self.raw_uri = raw_uri.strip()
        parsed = urlparse(self.raw_uri)
        
        # Default scheme parsing
        self.scheme = parsed.scheme.lower() if parsed.scheme else "file"
        if self.scheme not in self.SUPPORTED_SCHEMES:
            self.scheme = "custom"

        # Path parsing
        self.path = unquote(parsed.path) if parsed.path else parsed.netloc
        self.netloc = parsed.netloc
        self.query = parsed.query
        self.fragment = parsed.fragment

    @classmethod
    def parse(cls, uri_str: str) -> "ResourceURI":
        return cls(uri_str)

    @classmethod
    def create_file_uri(cls, path: str) -> str:
        clean_path = path.replace("\\", "/")
        if not clean_path.startswith("/"):
            clean_path = "/" + clean_path
        return f"file://{quote(clean_path)}"

    @classmethod
    def create_app_uri(cls, app_name: str) -> str:
        return f"app://{quote(app_name)}"

    @classmethod
    def create_memory_uri(cls, memory_id: str, memory_type: str = "generic") -> str:
        return f"memory://{memory_type}/{quote(memory_id)}"

    @classmethod
    def create_search_uri(cls, query: str) -> str:
        return f"search://query?q={quote(query)}"

    @classmethod
    def create_browser_uri(cls, target: str) -> str:
        if target.startswith("http://") or target.startswith("https://"):
            return target
        return f"browser://{quote(target)}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_uri": self.raw_uri,
            "scheme": self.scheme,
            "netloc": self.netloc,
            "path": self.path,
            "query": self.query,
            "fragment": self.fragment,
        }

    def __str__(self) -> str:
        return self.raw_uri

    def __repr__(self) -> str:
        return f"ResourceURI({self.raw_uri!r})"
