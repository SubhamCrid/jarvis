"""
Standard ActionDescriptor factory functions for Resources.
"""

from typing import Any, Dict, List
from jarvis.resource.schemas import ActionDescriptor, ResourcePermission


def generate_file_actions(
    file_path: str, permissions: List[ResourcePermission]
) -> List[ActionDescriptor]:
    actions = []
    if ResourcePermission.READ in permissions:
        actions.append(
            ActionDescriptor(
                name="open",
                label="Open File",
                capability_name="tools",
                required_permissions=[ResourcePermission.READ, ResourcePermission.EXECUTE],
                params={"tool": "file_opener", "path": file_path},
                description="Opens the file with default system application.",
            )
        )
        actions.append(
            ActionDescriptor(
                name="reveal",
                label="Reveal in Explorer",
                capability_name="tools",
                required_permissions=[ResourcePermission.READ],
                params={"tool": "explorer_reveal", "path": file_path},
                description="Reveals file location in file explorer.",
            )
        )
        actions.append(
            ActionDescriptor(
                name="copy_path",
                label="Copy Path",
                capability_name="tools",
                required_permissions=[ResourcePermission.READ],
                params={"tool": "clipboard", "text": file_path},
                description="Copies file path to clipboard.",
            )
        )
    if ResourcePermission.DELETE in permissions:
        actions.append(
            ActionDescriptor(
                name="delete",
                label="Delete File",
                capability_name="tools",
                required_permissions=[ResourcePermission.DELETE],
                params={"tool": "file_delete", "path": file_path},
                description="Deletes the file permanently or to recycle bin.",
            )
        )
    return actions


def generate_memory_actions(
    memory_id: str, memory_type: str = "generic"
) -> List[ActionDescriptor]:
    return [
        ActionDescriptor(
            name="retrieve",
            label="Retrieve Fact",
            capability_name="memory",
            required_permissions=[ResourcePermission.READ],
            params={"action": "retrieve", "memory_id": memory_id, "memory_type": memory_type},
            description="Retrieves full memory detail.",
        ),
        ActionDescriptor(
            name="forget",
            label="Delete Memory",
            capability_name="memory",
            required_permissions=[ResourcePermission.DELETE],
            params={"action": "delete", "memory_id": memory_id, "memory_type": memory_type},
            description="Removes memory item from storage.",
        ),
    ]
