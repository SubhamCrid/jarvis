"""
Central ProviderRegistry and decorator for dynamic plug-and-play AI and hardware backends.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Type

from jarvis.core.config.schema import AppConfig

logger = logging.getLogger("jarvis.providers.registry")


class ProviderRegistry:
    """
    Central registry maintaining mappings of provider categories (stt, tts, llm, wakeword, audio, storage)
    to concrete backend implementation classes.
    """

    _registry: Dict[str, Dict[str, Type[Any]]] = {}
    _loaded_builtins: bool = False

    @classmethod
    def _ensure_builtins(cls) -> None:
        if not cls._loaded_builtins:
            cls._loaded_builtins = True
            builtin_modules = [
                "jarvis.providers.audio.mock_audio",
                "jarvis.providers.audio.sounddevice_session",
                "jarvis.providers.llm.mock_llm",
                "jarvis.providers.llm.ollama_llm",
                "jarvis.providers.storage.session_store",
                "jarvis.providers.stt.faster_whisper_stt",
                "jarvis.providers.stt.mock_stt",
                "jarvis.providers.stt.whisper_cpp_stt",
                "jarvis.providers.tts.chatterbox_tts",
                "jarvis.providers.tts.edge_tts_provider",
                "jarvis.providers.tts.kokoro_tts",
                "jarvis.providers.tts.mock_tts",
                "jarvis.providers.tts.piper_tts",
                "jarvis.providers.wakeword.mock_wakeword",
                "jarvis.providers.wakeword.openwakeword_provider",
            ]
            import importlib
            for mod_name in builtin_modules:
                try:
                    importlib.import_module(mod_name)
                except Exception as err:
                    logger.debug(f"Optional provider module '{mod_name}' not loaded: {err}")

    @classmethod
    def register(cls, category: str, name: str) -> Callable[[Type[Any]], Type[Any]]:
        """Decorator to register a provider class under a category and name key."""

        def decorator(provider_cls: Type[Any]) -> Type[Any]:
            category_key = category.lower().strip()
            name_key = name.lower().strip()
            if category_key not in cls._registry:
                cls._registry[category_key] = {}
            cls._registry[category_key][name_key] = provider_cls
            logger.debug(f"Registered provider: category='{category_key}', name='{name_key}' -> {provider_cls.__name__}")
            return provider_cls

        return decorator

    @classmethod
    def get_class(cls, category: str, name: str) -> Optional[Type[Any]]:
        """Retrieve a registered provider class by category and name."""
        cls._ensure_builtins()
        return cls._registry.get(category.lower().strip(), {}).get(name.lower().strip())

    @classmethod
    def create(cls, category: str, name: str, config: AppConfig, **kwargs: Any) -> Any:
        """
        Dynamically instantiate a registered provider backend using its factory classmethod
        `from_config` if available, or direct constructor arguments.
        """
        cls._ensure_builtins()
        category_key = category.lower().strip()
        name_key = name.lower().strip()

        provider_cls = cls.get_class(category_key, name_key)
        if not provider_cls:
            available = list(cls._registry.get(category_key, {}).keys())
            raise ValueError(
                f"Unknown {category_key} provider '{name_key}'. Registered providers for '{category_key}': {available}"
            )

        logger.info(f"Instantiating {category_key} provider '{name_key}' ({provider_cls.__name__})...")

        if hasattr(provider_cls, "from_config") and callable(getattr(provider_cls, "from_config")):
            return provider_cls.from_config(config, **kwargs)

        return provider_cls(**kwargs)

    @classmethod
    def list_providers(cls, category: Optional[str] = None) -> Dict[str, List[str]]:
        """Return a mapping of registered categories to provider names."""
        cls._ensure_builtins()
        if category:
            cat_key = category.lower().strip()
            return {cat_key: list(cls._registry.get(cat_key, {}).keys())}
        return {cat: list(providers.keys()) for cat, providers in cls._registry.items()}


def register_provider(category: str, name: str) -> Callable[[Type[Any]], Type[Any]]:
    """Helper decorator for provider registration."""
    return ProviderRegistry.register(category, name)
