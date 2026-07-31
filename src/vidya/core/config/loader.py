"""
Hierarchical Configuration Loader with Migration Support and Environment Overrides.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from vidya.core.config.schema import AppConfig


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
    """Migrate legacy configuration formats to latest version (1.0)."""
    version = str(data.get("version", "1.0"))
    if version == "1.0":
        return data
    # Future migrations can be chained here
    data["version"] = "1.0"
    return data


def apply_env_overrides(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Override configuration values with environment variables starting with VIDYA_.
    Example: VIDYA_LLM__MODEL=llama3.2:1b overrides data['llm']['model']
    """
    prefix = "VIDYA_"
    for env_key, env_val in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        key_path = env_key[len(prefix):].lower().split("__")
        current = data
        for part in key_path[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        
        # Convert string env_val to int/float/bool if appropriate
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
    user_overrides: Optional[Dict[str, Any]] = None
) -> AppConfig:
    """
    Load and merge configurations in order:
    1. default.yaml
    2. development.yaml / production.yaml (based on env)
    3. user.yaml (if present)
    4. Explicit user_overrides dict (if passed)
    5. Environment variable overrides (VIDYA_*)
    """
    if config_dir is None:
        # Default config dir relative to workspace root or package
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

    # 1. Default config
    default_path = config_dir / "default.yaml"
    if default_path.exists():
        with open(default_path, "r", encoding="utf-8") as f:
            merged_data = yaml.safe_load(f) or {}

    # Determine environment
    if env is None:
        env = os.getenv("VIDYA_ENV", merged_data.get("system", {}).get("environment", "development"))

    # 2. Environment override file (development.yaml or production.yaml)
    env_file = config_dir / f"{env}.yaml"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            env_data = yaml.safe_load(f) or {}
            merged_data = deep_merge(merged_data, env_data)

    # 3. User config file (user.yaml)
    user_file = config_dir / "user.yaml"
    if user_file.exists():
        with open(user_file, "r", encoding="utf-8") as f:
            user_data = yaml.safe_load(f) or {}
            merged_data = deep_merge(merged_data, user_data)

    # 4. Explicit user overrides passed to loader
    if user_overrides:
        merged_data = deep_merge(merged_data, user_overrides)

    # 5. Environment variables
    merged_data = apply_env_overrides(merged_data)

    # Migrate if necessary
    merged_data = migrate_config(merged_data)

    return AppConfig(**merged_data)
