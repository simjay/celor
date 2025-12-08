"""Centralized configuration loading for CeLoR.

This module provides utilities for loading and accessing configuration from config.json
with support for environment variable fallbacks and default values.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    """Load configuration from JSON file.

    Returns empty dict if file doesn't exist or is invalid.

    Args:
        config_path: Path to config.json file (default: "config.json")

    Returns:
        Configuration dictionary, or empty dict if file not found/invalid
    """
    path = Path(config_path)

    if not path.exists():
        return {}

    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        # Return empty dict on error, allowing code to use defaults
        return {}


def get_config_value(
    keys: List[str], default: Any = None, config: Optional[Dict[str, Any]] = None
) -> Any:
    """Get nested configuration value with fallback to environment variable.

    Supports dot-notation keys like ["openai", "api_key"] or ["cegis", "max_iters"].
    Also checks environment variables as fallback (e.g., OPENAI_API_KEY for openai.api_key).

    Args:
        keys: List of keys to traverse (e.g., ["openai", "api_key"])
        default: Default value if key not found
        config: Optional config dict (uses load_config() if not provided)

    Returns:
        Configuration value, or default if not found
    """
    if config is None:
        config = load_config()

    value = config
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
            if value is None:
                break
        else:
            return default

    if value is not None:
        return value

    env_key = "_".join(k.upper() for k in keys)
    env_value = os.environ.get(env_key)
    if env_value is not None:
        return env_value

    return default

