"""
Hierarchical configuration loader supporting defaults, environment overlays, and environment variable overrides.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

from jarvis.core.config.schema import AppConfig


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge override dictionary into base dictionary."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def migrate_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate legacy configuration schemas to the target version."""
    version = str(data.get("version", "1.0"))
    if version == "1.0":
        return data

    data["version"] = "1.0"
    return data


def apply_env_overrides(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Override configuration properties via environment variables starting with JARVIS_.
    Example: JARVIS_LLM__MODEL=qwen2.5 overrides data['llm']['model'].
    """
    prefix = "JARVIS_"
    for env_key, env_val in os.environ.items():
        if not env_key.startswith(prefix):
            continue

        key_path = env_key[len(prefix):].lower().split("__")
        current = data
        for part in key_path[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]

        final_val: Any = env_val
        if env_val.lower() == "true":
            final_val = True
        elif env_val.lower() == "false":
            final_val = False
        elif env_val.isdigit():
            final_val = int(env_val)
        else:
            try:
                final_val = float(env_val)
            except ValueError:
                pass

        current[key_path[-1]] = final_val

    return data


def load_config(
    config_dir: Optional[Path] = None,
    env: Optional[str] = None,
    user_overrides: Optional[Dict[str, Any]] = None,
) -> AppConfig:
    """
    Load and aggregate configuration layers in priority order:
    1. default.yaml
    2. {env}.yaml (development / production / test)
    3. user.yaml
    4. Explicit programmatic user_overrides dictionary
    5. Environment variable overrides (JARVIS_*)
    """
    if config_dir is None:
        possible_dirs = [
            Path("config"),
            Path(__file__).parents[3] / "config",
            Path.cwd() / "config",
        ]
        for d in possible_dirs:
            if d.exists() and (d / "default.yaml").exists():
                config_dir = d
                break
        if config_dir is None:
            config_dir = Path("config")

    merged_data: Dict[str, Any] = {}

    default_path = config_dir / "default.yaml"
    if default_path.exists():
        with open(default_path, "r", encoding="utf-8") as f:
            merged_data = yaml.safe_load(f) or {}

    if env is None:
        env = os.getenv("JARVIS_ENV", merged_data.get("system", {}).get("environment", "development"))

    env_file = config_dir / f"{env}.yaml"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            env_data = yaml.safe_load(f) or {}
            merged_data = deep_merge(merged_data, env_data)

    user_file = config_dir / "user.yaml"
    if user_file.exists():
        with open(user_file, "r", encoding="utf-8") as f:
            user_data = yaml.safe_load(f) or {}
            merged_data = deep_merge(merged_data, user_data)

    if user_overrides:
        merged_data = deep_merge(merged_data, user_overrides)

    merged_data = apply_env_overrides(merged_data)
    merged_data = migrate_config(merged_data)

    return AppConfig(**merged_data)

