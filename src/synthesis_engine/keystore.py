"""
Keystore and user configuration for Ragbot.

Configuration lives under ~/.synthesis/ — the shared config home for
synthesis-engineering products (ragbot, ragenie, synthesis-console, ...).

Files:
    ~/.synthesis/keys.yaml    — API keys (shared across synthesis products)
    ~/.synthesis/ragbot.yaml  — ragbot user preferences

Legacy ~/.config/ragbot/{keys,config}.yaml is read as a fallback if the
new location is missing, so existing setups keep working.

Keys format:
    default:
      anthropic: "sk-ant-..."
      openai: "sk-..."
      google: "..."

    workspaces:
      example-client:
        anthropic: "sk-ant-client-key..."

User config format:
    default_workspace: personal
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import yaml

# Primary config location: ~/.synthesis/ (synthesis-engineering shared home)
SYNTHESIS_DIR = Path.home() / ".synthesis"
KEYSTORE_PATH = SYNTHESIS_DIR / "keys.yaml"
USER_CONFIG_PATH = SYNTHESIS_DIR / "ragbot.yaml"

# Back-compat alias: CONFIG_DIR was the old name for the active config dir.
# Now points to ~/.synthesis/ (the new home).
CONFIG_DIR = SYNTHESIS_DIR

# Legacy fallback: ~/.config/ragbot/ (read-only fallback for back-compat)
LEGACY_CONFIG_DIR = Path.home() / ".config" / "ragbot"
LEGACY_KEYSTORE_PATH = LEGACY_CONFIG_DIR / "keys.yaml"
LEGACY_USER_CONFIG_PATH = LEGACY_CONFIG_DIR / "config.yaml"


def _resolve_with_fallback(primary: Path, legacy: Path) -> Path:
    """Return primary if it exists, otherwise legacy. Used for back-compat."""
    if primary.exists():
        return primary
    return legacy


class Keystore:
    """API key management with workspace-specific overrides."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or _resolve_with_fallback(KEYSTORE_PATH, LEGACY_KEYSTORE_PATH)
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
        result = {p: self.has_key(p, workspace) for p in providers}
        # Local providers (no API key needed) are always available when
        # configured in engines.yaml. The actual reachability is verified at
        # request time by LiteLLM/Ollama.
        result["ollama"] = True
        return result

    def get_key_status(self, workspace: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed key status per provider for a workspace.

        For each provider, returns:
        - has_key: whether any key is available
        - source: 'workspace', 'default', or None
        - has_workspace_key: whether workspace has its own key
        - has_default_key: whether a default key exists

        Args:
            workspace: Workspace name to check

        Returns:
            Dict mapping provider names to status dicts
        """
        self._load()
        providers = ["anthropic", "openai", "google"]
        result = {}

        for provider in providers:
            has_workspace_key = False
            has_default_key = self._data.get("default", {}).get(provider) is not None

            if workspace:
                workspace_keys = self._data.get("workspaces", {}).get(workspace, {})
                has_workspace_key = provider in workspace_keys and workspace_keys[provider] is not None

            # Determine effective source
            if has_workspace_key:
                source = "workspace"
                has_key = True
            elif has_default_key:
                source = "default"
                has_key = True
            else:
                source = None
                has_key = False

            result[provider] = {
                "has_key": has_key,
                "source": source,
                "has_workspace_key": has_workspace_key,
                "has_default_key": has_default_key,
            }

        # Local providers (no API key needed) are always available when
        # configured in engines.yaml. Mirror the get_configured_providers
        # logic so the frontend's keys-status view and the available-models
        # view agree.
        result["ollama"] = {
            "has_key": True,
            "source": None,
            "has_workspace_key": False,
            "has_default_key": False,
        }

        return result

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
    """Ensure ~/.synthesis/ directory exists."""
    SYNTHESIS_DIR.mkdir(parents=True, exist_ok=True)
    return SYNTHESIS_DIR


def create_example_keystore() -> Path:
    """Create an example keys.yaml file if none exists."""
    ensure_keystore_dir()

    if KEYSTORE_PATH.exists() or LEGACY_KEYSTORE_PATH.exists():
        return _resolve_with_fallback(KEYSTORE_PATH, LEGACY_KEYSTORE_PATH)

    example = """# Synthesis API Keys (shared across synthesis-engineering products: ragbot, ragenie, etc.)
# This file should NOT be committed to git.
# Location: ~/.synthesis/keys.yaml

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
    """Load user configuration from ~/.synthesis/ragbot.yaml (or legacy fallback)."""
    global _user_config
    if _user_config is not None:
        return _user_config

    path = _resolve_with_fallback(USER_CONFIG_PATH, LEGACY_USER_CONFIG_PATH)
    if path.exists():
        with open(path) as f:
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


# Cap for the recent-models list — kept short so the picker stays readable.
RECENT_MODELS_CAP = 10


def _save_user_config(config: Dict[str, Any]) -> None:
    """Persist user configuration to ~/.synthesis/ragbot.yaml.

    Writes are atomic (temp file + rename), preserve 0600 permissions, and
    always target the canonical synthesis-engineering home regardless of
    whether the read came from the legacy fallback. Invalidates the
    in-memory cache so subsequent reads see the new state.
    """
    global _user_config

    SYNTHESIS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = USER_CONFIG_PATH.with_suffix(USER_CONFIG_PATH.suffix + ".tmp")

    # Create the temp file with restrictive permissions before writing the
    # YAML content; os.replace is atomic on POSIX so partial writes never
    # leave a malformed config in place.
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise

    os.replace(str(tmp), str(USER_CONFIG_PATH))
    _user_config = config


def set_user_config(key: str, value: Any) -> None:
    """Set a single user-configuration key and persist."""
    config = dict(_load_user_config())  # copy so we don't mutate the cache mid-write
    config[key] = value
    _save_user_config(config)


def get_pinned_models() -> list:
    """Return the user's pinned model IDs (canonical / normalized form)."""
    raw = _load_user_config().get("pinned_models", [])
    return [str(m) for m in raw if isinstance(m, str)]


def set_pinned_models(model_ids: list) -> None:
    """Replace the pinned-models list. Order is preserved; duplicates dropped."""
    seen = set()
    cleaned = []
    for mid in model_ids:
        if not isinstance(mid, str) or mid in seen:
            continue
        seen.add(mid)
        cleaned.append(mid)
    set_user_config("pinned_models", cleaned)


def get_recent_models() -> list:
    """Return the user's recently-used model IDs, newest first."""
    raw = _load_user_config().get("recent_models", [])
    return [str(m) for m in raw if isinstance(m, str)]


def record_recent_model(model_id: str, *, cap: int = RECENT_MODELS_CAP) -> None:
    """Record a model use. Moves the entry to the front and caps the list."""
    if not isinstance(model_id, str) or not model_id:
        return
    current = get_recent_models()
    # Move-to-front: drop any prior occurrence, prepend, then cap.
    deduped = [mid for mid in current if mid != model_id]
    new_list = [model_id] + deduped
    if len(new_list) > cap:
        new_list = new_list[:cap]
    set_user_config("recent_models", new_list)
