"""Append-only audit log for cross-workspace operations.

Every confidentiality-sensitive event lands as a JSONL line at
``~/.synthesis/cross-workspace-audit.jsonl`` (or the path declared in
``$SYNTHESIS_AUDIT_LOG_PATH``).

Design choices:

* **Append-only on disk**: writes use ``open(path, "a")`` with
  newline-terminated JSON lines. The file is never rewritten; rotation
  is the operator's responsibility (we provide a rotation-safe reader
  that copes with truncation mid-read).

* **Thread-safe**: a module-level lock guards the write critical
  section so concurrent agent threads don't interleave bytes. The lock
  is intentionally not a per-path lock because cross-thread visibility
  matters more than cross-process visibility, and a single Ragbot
  process is the canonical writer.

* **Redaction first**: ``redact_args`` runs over every JSON-serializable
  arg dict before the entry is appended. Values that match the API-key
  regex set or that exceed 200 characters become ``<redacted>``. The
  regex set is loaded from ``~/.synthesis/git-hook-config.yaml``
  (``tier_0_always.api_keys``) at import time; if the file is
  unreadable we fall back to a hard-coded minimal set so the audit
  trail stays clean even on a freshly-provisioned operator machine.

* **Fail-soft on read, fail-loud on write**: a corrupt JSONL line is
  skipped on read (with a warning) so a rotation glitch doesn't crash
  the agent loop. Write failures bubble up because losing audit data
  silently is the worst-case outcome.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is a hard dep
    yaml = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


DEFAULT_AUDIT_LOG_PATH = Path.home() / ".synthesis" / "cross-workspace-audit.jsonl"
AUDIT_LOG_ENV = "SYNTHESIS_AUDIT_LOG_PATH"

GIT_HOOK_CONFIG_PATH = Path.home() / ".synthesis" / "git-hook-config.yaml"

# Fallback regex set used when ~/.synthesis/git-hook-config.yaml is unreadable.
# Mirrors the tier_0_always.api_keys subset that has appeared in every
# audit-relevant version of the hook config.
_FALLBACK_API_KEY_REGEXES: Tuple[str, ...] = (
    r"AKIA[0-9A-Z]{16}",                  # AWS access key ID
    r"sk-[a-zA-Z0-9]{20}T3BlbkFJ",        # OpenAI
    r"sk-ant-api[a-zA-Z0-9-]+",           # Anthropic
    r"AIza[0-9A-Za-z_-]{35}",             # Google
    r"ghp_[a-zA-Z0-9]{36}",               # GitHub PAT
    r"glpat-[a-zA-Z0-9_-]{20}",           # GitLab PAT
    r"xoxb-[0-9]+-[a-zA-Z0-9]+",          # Slack bot token
    r"xoxp-[0-9]+-[a-zA-Z0-9]+",          # Slack user token
)


# Length threshold above which a value is redacted on its own (independent
# of regex match). Matches the brief.
_REDACTION_LENGTH_THRESHOLD = 200


# ---------------------------------------------------------------------------
# Regex loading
# ---------------------------------------------------------------------------


_compiled_regexes: Optional[List[re.Pattern]] = None
_regex_lock = threading.Lock()


def _load_api_key_regexes() -> List[re.Pattern]:
    """Load and compile the API-key regex set.

    Reads ``tier_0_always.api_keys`` from
    ``~/.synthesis/git-hook-config.yaml``. Falls back to
    :data:`_FALLBACK_API_KEY_REGEXES` when the file is missing,
    malformed, or yaml is unavailable.
    """
    patterns: Tuple[str, ...] = _FALLBACK_API_KEY_REGEXES
    if yaml is not None and GIT_HOOK_CONFIG_PATH.is_file():
        try:
            with open(GIT_HOOK_CONFIG_PATH, "r") as f:
                data = yaml.safe_load(f) or {}
            tier_0 = (data.get("tier_0_always") or {})
            raw = tier_0.get("api_keys") or []
            if isinstance(raw, list) and raw:
                cleaned = tuple(p for p in raw if isinstance(p, str) and p)
                if cleaned:
                    patterns = cleaned
        except (yaml.YAMLError, OSError) as exc:
            logger.warning(
                "Failed to read git-hook-config.yaml for redaction patterns "
                "(%s); falling back to built-in set.",
                exc,
            )

    compiled: List[re.Pattern] = []
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern))
        except re.error as exc:
            logger.warning(
                "Skipping invalid redaction regex %r: %s", pattern, exc,
            )
    return compiled


def _get_api_key_regexes() -> List[re.Pattern]:
    """Cached accessor for the compiled regex set."""
    global _compiled_regexes
    with _regex_lock:
        if _compiled_regexes is None:
            _compiled_regexes = _load_api_key_regexes()
        return _compiled_regexes


def _reset_regex_cache() -> None:
    """Drop the cached regex set (test hook)."""
    global _compiled_regexes
    with _regex_lock:
        _compiled_regexes = None


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------


REDACTED_PLACEHOLDER = "<redacted>"


def _redact_value(value: Any) -> Any:
    """Recursively redact a value.

    * Strings: redacted if they match any API-key regex OR exceed the
      length threshold.
    * Dicts: each value redacted; keys preserved.
    * Lists/tuples: each element redacted.
    * Other scalars (bool, int, float, None): passed through unchanged.
    """

    if isinstance(value, str):
        if len(value) > _REDACTION_LENGTH_THRESHOLD:
            return REDACTED_PLACEHOLDER
        for pattern in _get_api_key_regexes():
            if pattern.search(value):
                return REDACTED_PLACEHOLDER
        return value
    if isinstance(value, Mapping):
        return {k: _redact_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        rendered = [_redact_value(v) for v in value]
        return rendered if isinstance(value, list) else tuple(rendered)
    return value


def redact_args(args: Optional[Mapping[str, Any]]) -> str:
    """Render an args mapping as a JSON string with secrets redacted.

    Returns ``"{}"`` when ``args`` is None or empty. The output is
    sorted-keys + non-ASCII-safe (``ensure_ascii=False``) so a
    grep-friendly trail survives across operator locales.
    """
    if not args:
        return "{}"
    cleaned = _redact_value(dict(args))
    return json.dumps(cleaned, sort_keys=True, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# AuditEntry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditEntry:
    """One audit-log line.

    Frozen because entries are written-once. ``record()`` accepts a
    construction at the call site and serializes it as one JSON line.
    """

    timestamp_iso: str
    op_type: str
    workspaces: Tuple[str, ...]
    tools: Tuple[str, ...]
    model_id: str
    outcome: str
    args_summary: str = "{}"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        *,
        op_type: str,
        workspaces: List[str],
        tools: Optional[List[str]] = None,
        model_id: str = "",
        outcome: str = "allowed",
        args_summary: str = "{}",
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> "AuditEntry":
        """Convenience constructor with sensible defaults."""
        ts = (timestamp or datetime.now(timezone.utc)).isoformat()
        return cls(
            timestamp_iso=ts,
            op_type=op_type,
            workspaces=tuple(workspaces),
            tools=tuple(tools or ()),
            model_id=model_id,
            outcome=outcome,
            args_summary=args_summary,
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return the JSON-safe dict shape used for serialization."""
        return {
            "timestamp_iso": self.timestamp_iso,
            "op_type": self.op_type,
            "workspaces": list(self.workspaces),
            "tools": list(self.tools),
            "model_id": self.model_id,
            "outcome": self.outcome,
            "args_summary": self.args_summary,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "AuditEntry":
        """Inverse of :meth:`to_dict`; coerces lists back to tuples."""
        return cls(
            timestamp_iso=str(raw.get("timestamp_iso", "")),
            op_type=str(raw.get("op_type", "")),
            workspaces=tuple(raw.get("workspaces", ()) or ()),
            tools=tuple(raw.get("tools", ()) or ()),
            model_id=str(raw.get("model_id", "")),
            outcome=str(raw.get("outcome", "")),
            args_summary=str(raw.get("args_summary", "{}")),
            metadata=dict(raw.get("metadata", {}) or {}),
        )


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _resolve_path(explicit: Optional[Path]) -> Path:
    """Resolve the audit log path, honoring env override + explicit arg."""
    if explicit is not None:
        return Path(os.path.expanduser(str(explicit)))
    env_override = os.environ.get(AUDIT_LOG_ENV)
    if env_override:
        return Path(os.path.expanduser(env_override))
    return DEFAULT_AUDIT_LOG_PATH


# ---------------------------------------------------------------------------
# Append (thread-safe)
# ---------------------------------------------------------------------------


_write_lock = threading.Lock()


def record(entry: AuditEntry, log_path: Optional[Path] = None) -> None:
    """Append ``entry`` to the audit log as one JSON line.

    Atomic-per-line via ``os.open(O_APPEND | O_CREAT)`` + a single
    write of pre-rendered bytes. Thread-safe via a module-level lock.

    Parents are created as needed; the file is created with 0o600
    permissions so the audit trail is not world-readable on a shared
    machine.
    """
    path = _resolve_path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        entry.to_dict(),
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    line = (payload + "\n").encode("utf-8")

    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    with _write_lock:
        fd = os.open(str(path), flags, 0o600)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def read_recent(
    limit: int = 100,
    log_path: Optional[Path] = None,
) -> List[AuditEntry]:
    """Return the last ``limit`` entries from the audit log.

    Robust to rotation: if the file is empty, missing, or truncated
    mid-read we return whatever clean lines we managed to parse. Corrupt
    lines are logged at WARN and skipped — losing a few entries to a
    rotation event is preferable to crashing the caller.

    Lines are read in order; the result is the chronologically-newest
    ``limit`` entries with the newest entry last (i.e., the natural
    file order, truncated at the head).
    """
    if limit <= 0:
        return []
    path = _resolve_path(log_path)
    if not path.is_file():
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
    except OSError as exc:
        logger.warning("Failed to read audit log at %s: %s", path, exc)
        return []

    # Truncate to last ``limit`` raw lines first to keep parsing cheap on
    # very long files.
    tail = raw_lines[-limit:]
    entries: List[AuditEntry] = []
    for ln, raw in enumerate(tail, start=max(0, len(raw_lines) - limit) + 1):
        text = raw.strip()
        if not text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning(
                "Skipping malformed audit log line %d (rotation?)", ln,
            )
            continue
        if not isinstance(data, dict):
            continue
        entries.append(AuditEntry.from_dict(data))
    return entries


__all__ = [
    "AUDIT_LOG_ENV",
    "AuditEntry",
    "DEFAULT_AUDIT_LOG_PATH",
    "REDACTED_PLACEHOLDER",
    "read_recent",
    "record",
    "redact_args",
]
