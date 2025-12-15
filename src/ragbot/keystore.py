"""
Keystore and user configuration for Ragbot.

Loads API keys from ~/.config/ragbot/keys.yaml with support for
workspace-specific overrides.

Also loads user preferences from ~/.config/ragbot/config.yaml.

Keys format:
    default:
      anthropic: "sk-ant-..."
      openai: "sk-..."
      google: "..."

    workspaces:
      example-client:
        anthropic: "sk-ant-client-key..."

Config format:
    default_workspace: rajiv
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import yaml

# Standard XDG config location
CONFIG_DIR = Path.home() / ".config" / "ragbot"
KEYSTORE_PATH = CONFIG_DIR / "keys.yaml"
USER_CONFIG_PATH = CONFIG_DIR / "config.yaml"


class Keystore:
    """API key management with workspace-specific overrides."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or KEYSTORE_PATH
        self._data: Dict[str, Any] = {}
        self._loaded = False

    def _load(self) -> None:
        """Load keystore from disk."""
        if self._loaded:
            return

        if self.path.exists():
            with open(self.path) as f:
                self._data = yaml.safe_load(f) or {}
        else:
            self._data = {}

        self._loaded = True

    def get_key(self, provider: str, workspace: Optional[str] = None) -> Optional[str]:
        """
        Get API key for a provider, optionally scoped to a workspace.

        Resolution order:
        1. Workspace-specific key (if workspace provided)
        2. Default key

        Args:
            provider: Provider name (anthropic, openai, google, aws_bedrock)
            workspace: Optional workspace name for workspace-specific key

        Returns:
            API key string or None if not found
        """
        self._load()

        # Try workspace-specific key first
        if workspace:
            workspace_keys = self._data.get("workspaces", {}).get(workspace, {})
            if provider in workspace_keys:
                return workspace_keys[provider]

        # Fall back to default
        return self._data.get("default", {}).get(provider)

    def has_key(self, provider: str, workspace: Optional[str] = None) -> bool:
        """Check if a key exists for the provider."""
        return self.get_key(provider, workspace) is not None

    def get_configured_providers(self, workspace: Optional[str] = None) -> Dict[str, bool]:
        """
        Get dict of providers and whether they have keys configured.

        Args:
            workspace: Optional workspace to check workspace-specific keys

        Returns:
            Dict mapping provider names to availability boolean
        """
        providers = ["anthropic", "openai", "google", "aws_bedrock"]
        return {p: self.has_key(p, workspace) for p in providers}

    def list_workspaces_with_keys(self) -> list[str]:
        """List workspaces that have custom keys configured."""
        self._load()
        return list(self._data.get("workspaces", {}).keys())

    def reload(self) -> None:
        """Force reload from disk."""
        self._loaded = False
        self._load()


# Global singleton instance
_keystore: Optional[Keystore] = None


def get_keystore() -> Keystore:
    """Get the global keystore instance."""
    global _keystore
    if _keystore is None:
        _keystore = Keystore()
    return _keystore


def get_api_key(provider: str, workspace: Optional[str] = None) -> Optional[str]:
    """
    Get API key for a provider.

    Args:
        provider: Provider name (anthropic, openai, google, aws_bedrock)
        workspace: Optional workspace for workspace-specific key

    Returns:
        API key string or None
    """
    return get_keystore().get_key(provider, workspace)


def check_api_keys(workspace: Optional[str] = None) -> Dict[str, bool]:
    """
    Check which providers have API keys configured.

    Args:
        workspace: Optional workspace to check

    Returns:
        Dict mapping provider names to availability
    """
    return get_keystore().get_configured_providers(workspace)


def ensure_keystore_dir() -> Path:
    """Ensure ~/.config/ragbot/ directory exists."""
    config_dir = Path.home() / ".config" / "ragbot"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def create_example_keystore() -> Path:
    """Create an example keys.yaml file if none exists."""
    ensure_keystore_dir()

    if KEYSTORE_PATH.exists():
        return KEYSTORE_PATH

    example = """# Ragbot API Keys
# This file should NOT be committed to git.
# Location: ~/.config/ragbot/keys.yaml

# Default keys used when no workspace-specific key exists
default:
  anthropic: "sk-ant-your-key-here"
  openai: "sk-your-key-here"
  google: "your-gemini-key-here"
  # aws_bedrock uses AWS credentials, not API keys

# Workspace-specific key overrides
# Keys here take precedence over defaults for the specified workspace
workspaces:
  # Example: client workspace with their own Anthropic key
  # example-client:
  #   anthropic: "sk-ant-client-specific-key"

  # Example: company workspace with their own OpenAI key
  # example-company:
  #   openai: "sk-company-key"
"""

    with open(KEYSTORE_PATH, "w") as f:
        f.write(example)

    # Set restrictive permissions (owner read/write only)
    os.chmod(KEYSTORE_PATH, 0o600)

    return KEYSTORE_PATH


# User configuration management
_user_config: Optional[Dict[str, Any]] = None


def _load_user_config() -> Dict[str, Any]:
    """Load user configuration from config.yaml."""
    global _user_config
    if _user_config is not None:
        return _user_config

    if USER_CONFIG_PATH.exists():
        with open(USER_CONFIG_PATH) as f:
            _user_config = yaml.safe_load(f) or {}
    else:
        _user_config = {}

    return _user_config


def get_default_workspace() -> Optional[str]:
    """Get the user's default workspace from config."""
    config = _load_user_config()
    return config.get("default_workspace")


def get_user_config(key: str, default: Any = None) -> Any:
    """Get a user configuration value.

    Args:
        key: Configuration key
        default: Default value if key not found

    Returns:
        Configuration value or default
    """
    config = _load_user_config()
    return config.get(key, default)


def reload_user_config() -> None:
    """Force reload of user configuration from disk."""
    global _user_config
    _user_config = None
    _load_user_config()
