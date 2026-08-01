"""
Jarvis Capabilities package.
High-level domain capabilities (VoiceAssistantCapability, ToolsCapability, BrowserCapability, DesktopCapability).
"""

from jarvis.capabilities.base import BaseCapability, PermissionEnum
from jarvis.capabilities.registry import CapabilityRegistry
from jarvis.capabilities.voice_assistant import VoiceAssistantCapability
from jarvis.capabilities.tools import ToolsCapability
from jarvis.capabilities.browser import BrowserCapability
from jarvis.capabilities.desktop import DesktopCapability

__all__ = [
    "BaseCapability",
    "PermissionEnum",
    "CapabilityRegistry",
    "VoiceAssistantCapability",
    "ToolsCapability",
    "BrowserCapability",
    "DesktopCapability",
]
