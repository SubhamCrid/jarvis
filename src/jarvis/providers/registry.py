"""
Central ProviderRegistry and decorator for dynamic plug-and-play AI and hardware backends.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Type

from vidya.core.config.schema import AppConfig

logger = logging.getLogger("vidya.providers.registry")


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
                "vidya.providers.audio.mock_audio",
                "vidya.providers.audio.sounddevice_session",
                "vidya.providers.llm.mock_llm",
                "vidya.providers.llm.ollama_llm",
                "vidya.providers.storage.session_store",
                "vidya.providers.stt.faster_whisper_stt",
                "vidya.providers.stt.mock_stt",
                "vidya.providers.stt.whisper_cpp_stt",
                "vidya.providers.tts.edge_tts_provider",
                "vidya.providers.tts.mock_tts",
                "vidya.providers.tts.piper_tts",
                "vidya.providers.wakeword.mock_wakeword",
                "vidya.providers.wakeword.openwakeword_provider",
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
