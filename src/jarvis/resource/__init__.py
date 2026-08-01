"""
Universal Resource Model platform package exports.
"""

from jarvis.resource.schemas import (
    Resource,
    ResourceType,
    ResourcePermission,
    ActionDescriptor,
)
from jarvis.resource.uri import ResourceURI
from jarvis.resource.actions import (
    generate_file_actions,
    generate_memory_actions,
)

__all__ = [
    "Resource",
    "ResourceType",
    "ResourcePermission",
    "ActionDescriptor",
    "ResourceURI",
    "generate_file_actions",
    "generate_memory_actions",
]
