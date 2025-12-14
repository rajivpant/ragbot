"""Configuration loading for Ragbot.

This module handles loading and managing configuration from various sources.
"""

import os
from typing import Optional, Dict, Any, List
import yaml

from .exceptions import ConfigurationError


# Version of the ragbot library
VERSION = "2.0.0"

# Default settings
DEFAULT_MODEL = "anthropic/claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.75
DEFAULT_MAX_INPUT_TOKENS = 128000

# Model configurations
MODELS = {
    "anthropic": [
        {
            "id": "anthropic/claude-sonnet-4-20250514",
            "name": "Claude Sonnet 4",
            "context_window": 200000,
            "supports_streaming": True,
            "supports_system_role": True,
        },
        {
            "id": "anthropic/claude-opus-4-20250514",
            "name": "Claude Opus 4",
            "context_window": 200000,
            "supports_streaming": True,
            "supports_system_role": True,
        },
        {
            "id": "anthropic/claude-3-5-haiku-20241022",
            "name": "Claude 3.5 Haiku",
            "context_window": 200000,
            "supports_streaming": True,
            "supports_system_role": True,
        },
    ],
    "openai": [
        {
            "id": "gpt-4o",
            "name": "GPT-4o",
            "context_window": 128000,
            "supports_streaming": True,
            "supports_system_role": True,
        },
        {
            "id": "gpt-4o-mini",
            "name": "GPT-4o Mini",
            "context_window": 128000,
            "supports_streaming": True,
            "supports_system_role": True,
        },
        {
            "id": "o1",
            "name": "o1",
            "context_window": 200000,
            "supports_streaming": True,
            "supports_system_role": True,
        },
    ],
    "google": [
        {
            "id": "gemini/gemini-2.0-flash",
            "name": "Gemini 2.0 Flash",
            "context_window": 1000000,
            "supports_streaming": True,
            "supports_system_role": True,
        },
        {
            "id": "gemini/gemini-1.5-pro",
            "name": "Gemini 1.5 Pro",
            "context_window": 2000000,
            "supports_streaming": True,
            "supports_system_role": True,
        },
    ],
}


def load_yaml_config(path: str) -> Dict[str, Any]:
    """Load a YAML configuration file.

    Args:
        path: Path to YAML file

    Returns:
        Dictionary with config values

    Raises:
        ConfigurationError: If file cannot be loaded
    """
    try:
        with open(path, 'r') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in {path}: {e}")


def load_data_config(data_root: str) -> Dict[str, Any]:
    """Load global configuration from workspaces/config.yaml.

    Args:
        data_root: Root directory containing the workspaces folder

    Returns:
        Dictionary with config values
    """
    config_path = os.path.join(data_root, 'workspaces', 'config.yaml')
    return load_yaml_config(config_path)


def get_all_models() -> Dict[str, List[Dict[str, Any]]]:
    """Get all available models grouped by provider.

    Returns:
        Dictionary mapping provider to list of model configs
    """
    return MODELS


def get_model_info(model_id: str) -> Optional[Dict[str, Any]]:
    """Get information about a specific model.

    Args:
        model_id: Model identifier

    Returns:
        Model configuration dict, or None if not found
    """
    for provider, models in MODELS.items():
        for model in models:
            if model["id"] == model_id:
                return {**model, "provider": provider}
    return None


def get_default_model() -> str:
    """Get the default model ID.

    Returns:
        Default model identifier
    """
    return DEFAULT_MODEL


def check_api_keys() -> Dict[str, bool]:
    """Check which API keys are configured.

    Returns:
        Dictionary mapping provider to boolean availability
    """
    return {
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
        "google": bool(
            os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        ),
    }


def get_available_models() -> Dict[str, List[Dict[str, Any]]]:
    """Get models filtered by available API keys.

    Returns:
        Dictionary mapping provider to list of available model configs
    """
    api_keys = check_api_keys()
    available = {}

    for provider, models in MODELS.items():
        if api_keys.get(provider, False):
            available[provider] = models

    return available
