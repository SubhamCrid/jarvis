"""
Jarvis Provider package exporting central ProviderRegistry and registration decorator.
"""

from jarvis.providers.registry import ProviderRegistry, register_provider

__all__ = [
    "ProviderRegistry",
    "register_provider",
]
