"""Bearer-token authentication for the HTTP/SSE transport.

Stdio mode skips auth (the transport is process-local; trust is the
parent process's responsibility). HTTP/SSE mode requires a bearer token
on every request, resolved against a per-server YAML config at
``~/.synthesis/mcp-server.yaml`` (env-overridable via
``RAGBOT_MCP_SERVER_CONFIG``).

YAML shape::

    bearer_tokens:
      - name: claude-code-local
        token: <random>
        allowed_tools: ["workspace_search", "skill_run"]
      - name: cursor-laptop
        token: <random>
        allowed_tools: ["*"]

Behaviour
---------

* :func:`load_auth_config` reads the YAML and returns
  :class:`MCPServerAuthConfig`. A missing or unparseable file in HTTP
  mode is a fatal configuration error — the server refuses to start
  with a clear remediation message. The same path is allowed to be
  absent in stdio mode (the loader returns ``None``).

* :meth:`MCPServerAuthConfig.authenticate_bearer` resolves a presented
  token to a :class:`BearerToken` entry, returning ``None`` when the
  token is unknown.

* :meth:`BearerToken.allows_tool` matches a tool name against the
  per-token ``allowed_tools`` glob list. The literal ``"*"`` is a
  wildcard for "every tool exposed by this server."

The module is deliberately storage-agnostic: every consumer takes the
config as an argument. The HTTP/SSE transport wires the loader at
startup; tests construct an :class:`MCPServerAuthConfig` directly.
"""

from __future__ import annotations

import fnmatch
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is a hard dep
    yaml = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


DEFAULT_AUTH_CONFIG_PATH = Path.home() / ".synthesis" / "mcp-server.yaml"
AUTH_CONFIG_ENV = "RAGBOT_MCP_SERVER_CONFIG"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MCPServerAuthError(Exception):
    """Raised when the HTTP/SSE transport cannot start due to bad auth config.

    The error message is suitable for logging directly — callers do not
    need to wrap it. Stdio mode never raises this because stdio bypasses
    auth entirely.
    """


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BearerToken:
    """One token entry from the auth YAML.

    Attributes:
        name:          Human-readable label (e.g., ``"claude-code-local"``).
                       Used in audit and log lines so an operator can
                       see which client made which call.
        token:         The opaque secret presented in
                       ``Authorization: Bearer <token>``.
        allowed_tools: Tuple of glob patterns. ``("*",)`` allows every
                       tool; an empty tuple denies everything (the
                       server refuses to dispatch any tool). Glob match
                       uses :mod:`fnmatch`.
    """

    name: str
    token: str
    allowed_tools: Tuple[str, ...] = ()

    def allows_tool(self, tool_name: str) -> bool:
        """Return True when ``tool_name`` matches any allowed glob.

        The literal ``"*"`` always matches. Otherwise we use
        :func:`fnmatch.fnmatchcase` on each pattern so callers can write
        ``workspace_*`` to grant the search family without granting
        ``skill_run`` or ``agent_run_start``.
        """
        if not self.allowed_tools:
            return False
        for pattern in self.allowed_tools:
            if pattern == "*":
                return True
            if fnmatch.fnmatchcase(tool_name, pattern):
                return True
        return False


@dataclass(frozen=True)
class MCPServerAuthConfig:
    """Resolved auth config for the HTTP/SSE transport.

    The config holds the list of accepted bearer tokens. The
    :meth:`authenticate_bearer` method is the single point of truth for
    "is this Authorization header valid"; downstream code never matches
    tokens by hand.

    Construction
    ------------

    * Production: :func:`load_auth_config` reads the YAML.
    * Tests: instantiate directly with a list of :class:`BearerToken`.
    """

    tokens: Tuple[BearerToken, ...] = field(default_factory=tuple)

    def authenticate_bearer(self, presented: Optional[str]) -> Optional[BearerToken]:
        """Resolve a presented bearer string to a :class:`BearerToken`.

        Accepts either the raw token or the full
        ``"Bearer <token>"`` header value — operators sometimes get the
        slicing wrong, and this layer should not bounce them for a
        cosmetic difference. Returns ``None`` when no entry matches.
        """
        if not presented or not isinstance(presented, str):
            return None
        candidate = presented.strip()
        if candidate.lower().startswith("bearer "):
            candidate = candidate[7:].strip()
        if not candidate:
            return None
        for entry in self.tokens:
            if entry.token == candidate:
                return entry
        return None


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def _resolve_config_path(explicit: Optional[Path]) -> Path:
    """Resolve the auth-config path, honouring env override + explicit arg."""
    if explicit is not None:
        return Path(os.path.expanduser(str(explicit)))
    env_override = os.environ.get(AUTH_CONFIG_ENV)
    if env_override:
        return Path(os.path.expanduser(env_override))
    return DEFAULT_AUTH_CONFIG_PATH


def _coerce_allowed_tools(raw: object, ctx: str) -> Tuple[str, ...]:
    """Validate the ``allowed_tools`` list shape for one entry."""
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    if not isinstance(raw, (list, tuple)):
        raise MCPServerAuthError(
            f"mcp-server.yaml: entry {ctx} has allowed_tools of type "
            f"{type(raw).__name__}; expected a list of strings."
        )
    out: List[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise MCPServerAuthError(
                f"mcp-server.yaml: entry {ctx} has a non-string or empty "
                f"allowed_tools value {item!r}; expected a list of glob strings."
            )
        out.append(item.strip())
    return tuple(out)


def load_auth_config(
    *,
    require: bool = True,
    config_path: Optional[Path] = None,
) -> Optional[MCPServerAuthConfig]:
    """Load the per-server auth config.

    Args:
        require: When True (HTTP/SSE mode), a missing or malformed file
            raises :class:`MCPServerAuthError`. When False (stdio mode),
            a missing file returns ``None`` and the caller treats it as
            "auth disabled — process-local trust applies."
        config_path: Optional explicit path. Falls back to the env
            override (:data:`AUTH_CONFIG_ENV`) and finally to
            :data:`DEFAULT_AUTH_CONFIG_PATH`.

    Returns:
        A :class:`MCPServerAuthConfig` with the parsed tokens, or
        ``None`` when ``require=False`` and the file is absent.

    Raises:
        MCPServerAuthError: when ``require=True`` and the config is
            missing, malformed, or contains zero tokens. Fail-closed:
            the server cannot accept HTTP requests without at least one
            configured bearer token.
    """
    path = _resolve_config_path(config_path)

    if not path.is_file():
        if not require:
            logger.debug(
                "mcp-server auth config not found at %s; running without auth "
                "(stdio mode).",
                path,
            )
            return None
        raise MCPServerAuthError(
            f"HTTP/SSE transport requires {path} but the file is missing. "
            f"Create the file with at least one bearer_tokens entry or "
            f"set {AUTH_CONFIG_ENV} to point at an existing config."
        )

    if yaml is None:  # pragma: no cover - PyYAML is a hard dep
        raise MCPServerAuthError(
            "PyYAML is required to read mcp-server.yaml but is unavailable."
        )

    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    except (yaml.YAMLError, OSError) as exc:
        raise MCPServerAuthError(
            f"Failed to read mcp-server auth config at {path}: {exc}"
        ) from exc

    if raw is None:
        if not require:
            return None
        raise MCPServerAuthError(
            f"mcp-server.yaml at {path} is empty; HTTP/SSE transport "
            f"requires at least one bearer_tokens entry."
        )

    if not isinstance(raw, dict):
        raise MCPServerAuthError(
            f"mcp-server.yaml at {path} must be a mapping at the top "
            f"level, got {type(raw).__name__}."
        )

    raw_tokens = raw.get("bearer_tokens", [])
    if not isinstance(raw_tokens, list):
        raise MCPServerAuthError(
            f"mcp-server.yaml at {path}: bearer_tokens must be a list, "
            f"got {type(raw_tokens).__name__}."
        )

    tokens: List[BearerToken] = []
    seen_names: set = set()
    seen_tokens: set = set()
    for idx, entry in enumerate(raw_tokens):
        ctx = f"[{idx}]"
        if not isinstance(entry, dict):
            raise MCPServerAuthError(
                f"mcp-server.yaml entry {ctx} must be a mapping, got "
                f"{type(entry).__name__}."
            )
        name = str(entry.get("name", "")).strip()
        token = entry.get("token")
        if not name:
            raise MCPServerAuthError(
                f"mcp-server.yaml entry {ctx}: 'name' is required."
            )
        if not isinstance(token, str) or not token.strip():
            raise MCPServerAuthError(
                f"mcp-server.yaml entry {ctx!r} ({name!r}): 'token' must "
                f"be a non-empty string."
            )
        token = token.strip()
        if name in seen_names:
            raise MCPServerAuthError(
                f"mcp-server.yaml: duplicate token name {name!r}."
            )
        if token in seen_tokens:
            raise MCPServerAuthError(
                f"mcp-server.yaml: duplicate token value (entry {name!r})."
            )
        seen_names.add(name)
        seen_tokens.add(token)
        allowed = _coerce_allowed_tools(entry.get("allowed_tools"), ctx)
        tokens.append(
            BearerToken(name=name, token=token, allowed_tools=allowed)
        )

    if not tokens and require:
        raise MCPServerAuthError(
            f"mcp-server.yaml at {path}: bearer_tokens is empty. "
            f"HTTP/SSE transport requires at least one token."
        )

    return MCPServerAuthConfig(tokens=tuple(tokens))


__all__ = [
    "AUTH_CONFIG_ENV",
    "BearerToken",
    "DEFAULT_AUTH_CONFIG_PATH",
    "MCPServerAuthConfig",
    "MCPServerAuthError",
    "load_auth_config",
]
