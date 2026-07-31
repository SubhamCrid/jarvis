"""
Vidya Provider package exporting central ProviderRegistry and registration decorator.
"""

from vidya.providers.registry import ProviderRegistry, register_provider

__all__ = [
    "ProviderRegistry",
    "register_provider",
]
