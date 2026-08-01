"""
Deferred Plugin Package extension schemas and interfaces for Jarvis.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PluginCapabilityExtension(BaseModel):
    name: str
    extension_type: str  # search_provider, tool, action, memory_provider, event
    module_path: str
    enabled: bool = True


class PluginManifest(BaseModel):
    name: str
    version: str = "1.0.0"
    author: str = ""
    description: str = ""
    extensions: List[PluginCapabilityExtension] = Field(default_factory=list)
