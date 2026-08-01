"""
Unit tests for Configuration loader, schema validation, versioning, and environment overrides.
"""

import os
import pytest
from jarvis.core.config.loader import load_config, deep_merge, migrate_config
from jarvis.core.config.schema import AppConfig


def test_deep_merge():
    base = {"a": 1, "b": {"x": 10, "y": 20}}
    override = {"b": {"y": 30, "z": 40}, "c": 3}
    merged = deep_merge(base, override)
    assert merged == {"a": 1, "b": {"x": 10, "y": 30, "z": 40}, "c": 3}


def test_migrate_config():
    data = {"version": "0.9", "llm": {"provider": "ollama"}}
    migrated = migrate_config(data)
    assert migrated["version"] == "1.0"


def test_load_config_defaults(config):
    assert isinstance(config, AppConfig)
    assert config.version == "1.0"
    assert config.stt.provider == "faster_whisper"
    assert config.tts.provider == "kokoro"
    assert config.wakeword.provider == "openwakeword"


def test_env_override():
    os.environ["JARVIS_LLM__MODEL"] = "qwen2.5:3b"
    try:
        cfg = load_config()
        assert cfg.llm.model == "qwen2.5:3b"
    finally:
        del os.environ["JARVIS_LLM__MODEL"]
