"""
Unit tests for ProviderRegistry, decorator registration, factory instantiation, and error handling.
"""

import pytest
from jarvis.core.config.schema import AppConfig
from jarvis.providers import ProviderRegistry, register_provider
from jarvis.providers.base import LLMProtocol
from jarvis.core.base import ServiceStatus, HealthStatus
from typing import AsyncGenerator, Optional, List, Dict


@register_provider("llm", "test_custom")
class CustomTestLLM(LLMProtocol):
    """Custom plug-and-play LLM backend for unit testing."""

    @classmethod
    def from_config(cls, config: AppConfig) -> "CustomTestLLM":
        return cls(custom_model=config.llm.model)

    def __init__(self, custom_model: str = "test-model") -> None:
        self.custom_model = custom_model
        self._status = ServiceStatus.UNINITIALIZED

    async def initialize(self) -> bool:
        self._status = ServiceStatus.RUNNING
        return True

    async def generate_stream(self, prompt: str, history: Optional[List[Dict[str, str]]] = None) -> AsyncGenerator[str, None]:
        yield "custom token"

    async def health(self) -> HealthStatus:
        return HealthStatus(status=self._status, message="Custom LLM healthy")

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        pass


def test_provider_registration_and_list():
    providers = ProviderRegistry.list_providers()
    assert "llm" in providers
    assert "test_custom" in providers["llm"]
    assert "ollama" in providers["llm"]
    assert "mock" in providers["llm"]

    assert "stt" in providers
    assert "whisper_cpp" in providers["stt"]
    assert "faster_whisper" in providers["stt"]

    assert "tts" in providers
    assert "edge_tts" in providers["tts"]
    assert "piper" in providers["tts"]


def test_provider_creation_from_config():
    config = AppConfig()
    llm_instance = ProviderRegistry.create("llm", "test_custom", config)
    assert isinstance(llm_instance, CustomTestLLM)
    assert llm_instance.custom_model == config.llm.model


def test_unknown_provider_raises_error():
    config = AppConfig()
    with pytest.raises(ValueError, match="Unknown llm provider 'non_existent_llm'"):
        ProviderRegistry.create("llm", "non_existent_llm", config)
