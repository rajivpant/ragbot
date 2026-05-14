"""Notification adapters for background-task lifecycle events.

The :class:`BackgroundTaskManager` calls :meth:`Notifier.notify` on
every terminal transition. Adapters ship for the three channels that
make sense on an operator's local machine:

* :class:`MacOSNotifier` — macOS Notification Centre via ``osascript``.
* :class:`EmailNotifier` — SMTP using ``~/.synthesis/email.yaml`` for
  host/port/from/to and ``~/.synthesis/keys.yaml`` for the password.
* :class:`SlackNotifier` — uses a wired :class:`MCPClient` to invoke
  the Slack MCP server's ``slack_send_message`` tool.

Each notifier is OPTIONAL. The composite notifier dispatches to every
configured adapter; one failing adapter does not suppress the others.
This mirrors the audit log's fail-soft-on-write contract.

Webhook delivery is NOT a Notifier. Webhooks are per-task callbacks
attached when the task is created; notifiers are global. Mixing the
two would put the responsibility for delivering "this specific
caller's callback" on a registry that has no caller-level context.
"""

from __future__ import annotations

import abc
import asyncio
import logging
import os
import platform
import shutil
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is a hard dep
    yaml = None  # type: ignore[assignment]

from .manager import TaskRecord

logger = logging.getLogger("synthesis_engine.tasks.notifications")


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class Notifier(abc.ABC):
    """Async notifier interface.

    Notifiers MUST NOT raise on configuration absence — silent skip is
    the contract so a fresh operator machine without an SMTP server or
    a Slack MCP integration does not lose audit traces from failed
    notifications. Hard errors during a configured delivery may
    propagate; the composite catches them.
    """

    @abc.abstractmethod
    async def notify(self, task_record: TaskRecord, event: str) -> None:
        """Send a notification for ``task_record`` carrying ``event``.

        ``event`` is one of: started, succeeded, failed, cancelled,
        timed_out, crashed.
        """


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------


class CompositeNotifier(Notifier):
    """Dispatches to every wrapped notifier; collects errors per-adapter."""

    def __init__(self, notifiers: Iterable[Notifier]) -> None:
        self._notifiers: List[Notifier] = list(notifiers)
        self.last_errors: List[Exception] = []

    def add(self, notifier: Notifier) -> None:
        self._notifiers.append(notifier)

    @property
    def notifiers(self) -> List[Notifier]:
        return list(self._notifiers)

    async def notify(self, task_record: TaskRecord, event: str) -> None:
        self.last_errors = []
        for notifier in self._notifiers:
            try:
                await notifier.notify(task_record, event=event)
            except Exception as exc:  # noqa: BLE001 — per-adapter isolation
                logger.warning(
                    "Notifier %s failed for task %s event %s: %s",
                    notifier.__class__.__name__,
                    task_record.id,
                    event,
                    exc,
                )
                self.last_errors.append(exc)


# ---------------------------------------------------------------------------
# macOS Notification Centre
# ---------------------------------------------------------------------------


class MacOSNotifier(Notifier):
    """macOS desktop notifications via ``osascript``.

    Silently skips on non-macOS platforms or when osascript is missing.
    The command shell-outs to AppleScript's ``display notification``
    primitive rather than the heavier ``terminal-notifier`` external
    binary so no extra dependency is needed.
    """

    DEFAULT_SOUND_NAME = "Glass"

    def __init__(
        self,
        *,
        runner: Optional[Any] = None,
        sound_name: str = DEFAULT_SOUND_NAME,
        platform_name: Optional[str] = None,
        osascript_path: Optional[str] = None,
    ) -> None:
        # Allow tests to inject a fake subprocess runner without
        # monkeypatching ``subprocess`` at module scope.
        if runner is None:
            import subprocess as _subprocess

            runner = _subprocess.run
        self._runner = runner
        self._sound_name = sound_name
        self._platform = platform_name or platform.system()
        self._osascript = osascript_path or shutil.which("osascript")

    async def notify(self, task_record: TaskRecord, event: str) -> None:
        if self._platform != "Darwin":
            logger.debug(
                "MacOSNotifier silent-skip on platform %s", self._platform,
            )
            return
        if not self._osascript:
            logger.debug("MacOSNotifier: osascript binary not found; skipping.")
            return

        title = f"Ragbot task {event}"
        message = _format_summary(task_record)
        script = _build_osascript(
            title=title, message=message, sound=self._sound_name,
        )
        cmd = [self._osascript, "-e", script]

        def _do() -> Any:
            return self._runner(
                cmd, capture_output=True, text=True, timeout=5,
            )

        await asyncio.to_thread(_do)


def _build_osascript(*, title: str, message: str, sound: str) -> str:
    safe_title = title.replace('"', '\\"')
    safe_message = message.replace('"', '\\"')
    return (
        f'display notification "{safe_message}" '
        f'with title "{safe_title}" sound name "{sound}"'
    )


def _format_summary(record: TaskRecord) -> str:
    parts = [f"{record.name} → {record.state}"]
    if record.result_summary and record.state == "succeeded":
        # The summary can be long; the desktop banner clips at ~256 chars.
        parts.append(record.result_summary[:80])
    elif record.error_summary:
        parts.append(record.error_summary[:80])
    return " · ".join(parts)


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


@dataclass
class EmailConfig:
    host: str
    port: int
    sender: str
    recipient: str
    password: Optional[str] = None
    use_ssl: bool = True

    @classmethod
    def from_yaml(cls, path: Path) -> Optional["EmailConfig"]:
        if yaml is None or not path.is_file():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as exc:
            logger.warning("Failed to read email config at %s: %s", path, exc)
            return None
        if not isinstance(data, dict):
            return None
        try:
            return cls(
                host=str(data["host"]),
                port=int(data["port"]),
                sender=str(data["from"]),
                recipient=str(data["to"]),
                password=data.get("password"),
                use_ssl=bool(data.get("use_ssl", True)),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("Email config at %s is malformed: %s", path, exc)
            return None


class EmailNotifier(Notifier):
    """SMTP-backed notifier.

    Configuration sources (resolved in this order):

    1. Constructor argument ``config=`` (explicit injection).
    2. ``~/.synthesis/email.yaml`` (operator-local config).

    The password is taken from ``EmailConfig.password`` directly. If
    the YAML config sets ``password: !env SMTP_PASS`` the operator is
    responsible for env-substituting before write — the substrate does
    NOT shell-out a custom YAML loader to keep the failure modes
    simple.
    """

    DEFAULT_CONFIG_PATH = Path.home() / ".synthesis" / "email.yaml"

    def __init__(
        self,
        config: Optional[EmailConfig] = None,
        *,
        config_path: Optional[Path] = None,
        smtp_factory: Optional[Any] = None,
    ) -> None:
        self._explicit_config = config
        self._config_path = config_path or self.DEFAULT_CONFIG_PATH
        # ``smtp_factory(host, port) -> SMTP-like`` allows tests to inject
        # a fake SMTP client without monkeypatching smtplib.
        self._smtp_factory = smtp_factory

    def _resolve_config(self) -> Optional[EmailConfig]:
        if self._explicit_config is not None:
            return self._explicit_config
        return EmailConfig.from_yaml(self._config_path)

    async def notify(self, task_record: TaskRecord, event: str) -> None:
        config = self._resolve_config()
        if config is None:
            logger.debug(
                "EmailNotifier: no config available; skipping for task %s.",
                task_record.id,
            )
            return

        message = EmailMessage()
        message["Subject"] = f"Ragbot task {task_record.name} → {event}"
        message["From"] = config.sender
        message["To"] = config.recipient
        message.set_content(_format_email_body(task_record, event))

        await asyncio.to_thread(self._send, config, message)

    def _send(self, config: EmailConfig, message: EmailMessage) -> None:
        factory = self._smtp_factory
        if factory is None:
            ctx = ssl.create_default_context() if config.use_ssl else None
            if config.use_ssl:
                client = smtplib.SMTP_SSL(
                    config.host, config.port, context=ctx, timeout=10,
                )
            else:
                client = smtplib.SMTP(config.host, config.port, timeout=10)
        else:
            client = factory(config.host, config.port)
        try:
            if config.password:
                client.login(config.sender, config.password)
            client.send_message(message)
        finally:
            try:
                client.quit()
            except Exception:  # noqa: BLE001 — quit() best-effort
                pass


def _format_email_body(record: TaskRecord, event: str) -> str:
    lines = [
        f"Task: {record.name}",
        f"ID: {record.id}",
        f"State: {event}",
        f"Created: {record.created_at_iso}",
        f"Finished: {record.finished_at_iso or '-'}",
    ]
    if record.result_summary:
        lines.append("")
        lines.append("Result summary:")
        lines.append(record.result_summary)
    if record.error_summary:
        lines.append("")
        lines.append("Error summary:")
        lines.append(record.error_summary)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Slack via MCP
# ---------------------------------------------------------------------------


SLACK_DEFAULT_TOOL_CANDIDATES = (
    "slack_send_message",
    "slack-send-message",
    "send_message",
    "chat_postMessage",
)


class SlackNotifier(Notifier):
    """Slack notifier that routes through an MCP client.

    The notifier does NOT call the Slack Web API directly. The
    integration point is the wired :class:`MCPClient`: the operator
    has already chosen which Slack MCP server they trust (the official
    server, a self-hosted shim, etc.), and the notifier rides that
    choice. If no MCP client is wired or no connected server exposes
    a recognised Slack send-message tool, the notifier logs a warning
    and silent-skips.

    Constructor parameters
    ----------------------
    ``mcp_client``
        Any object exposing ``async list_tools(server_id)`` and
        ``async call_tool(server_id, name, arguments)`` — mirrors the
        substrate's :class:`MCPClient` shape so the same fakes used
        elsewhere in the test suite plug in directly.

    ``channel``
        Slack channel id / name to post into.

    ``server_id``
        MCP server id to use; if omitted, the notifier discovers the
        first connected server exposing a recognised tool.

    ``tool_name``
        Explicit tool name override. If omitted, the notifier picks
        the first match from :data:`SLACK_DEFAULT_TOOL_CANDIDATES`.
    """

    def __init__(
        self,
        mcp_client: Any,
        channel: str,
        *,
        server_id: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> None:
        self._client = mcp_client
        self._channel = channel
        self._server_id = server_id
        self._tool_name = tool_name

    async def notify(self, task_record: TaskRecord, event: str) -> None:
        if self._client is None:
            logger.debug("SlackNotifier: no MCP client wired; skipping.")
            return

        server_id, tool_name = await self._resolve_target()
        if server_id is None or tool_name is None:
            logger.warning(
                "SlackNotifier: no MCP server with a Slack send-message "
                "tool is connected; skipping notification for task %s.",
                task_record.id,
            )
            return

        arguments = {
            "channel": self._channel,
            "text": _format_slack_text(task_record, event),
        }
        await self._client.call_tool(server_id, tool_name, arguments)

    async def _resolve_target(self) -> tuple:
        if self._server_id and self._tool_name:
            return self._server_id, self._tool_name
        # Discover the first connected server whose tool list has a
        # recognised slack tool.
        active = []
        if hasattr(self._client, "get_active_servers"):
            try:
                active = self._client.get_active_servers()
            except Exception:  # noqa: BLE001 — discovery best-effort
                active = []
        # Fall back to scanning every server if get_active_servers is
        # unavailable (e.g., a fake test client).
        server_ids: List[str] = []
        for entry in active or []:
            sid = getattr(entry, "id", None) or getattr(entry, "server_id", None)
            if sid:
                server_ids.append(sid)
        if not server_ids and hasattr(self._client, "list_servers"):
            try:
                for entry in self._client.list_servers():
                    sid = getattr(entry, "id", None) or getattr(entry, "server_id", None)
                    if sid:
                        server_ids.append(sid)
            except Exception:  # noqa: BLE001 — discovery best-effort
                pass
        if not server_ids and self._server_id:
            server_ids = [self._server_id]
        for sid in server_ids:
            try:
                tools = await self._client.list_tools(sid)
            except Exception as exc:  # noqa: BLE001 — discovery best-effort
                logger.debug(
                    "SlackNotifier: list_tools(%s) failed: %s", sid, exc,
                )
                continue
            for tool in tools or []:
                name = _tool_name(tool)
                if not name:
                    continue
                if self._tool_name and name == self._tool_name:
                    return sid, name
                if not self._tool_name and name in SLACK_DEFAULT_TOOL_CANDIDATES:
                    return sid, name
        return None, None


def _tool_name(tool: Any) -> Optional[str]:
    if isinstance(tool, dict):
        return tool.get("name")
    return getattr(tool, "name", None)


def _format_slack_text(record: TaskRecord, event: str) -> str:
    prefix = {
        "succeeded": "Task succeeded",
        "failed": "Task failed",
        "cancelled": "Task cancelled",
        "timed_out": "Task timed out",
        "crashed": "Task crashed during run",
        "started": "Task started",
    }.get(event, f"Task {event}")
    body = _format_summary(record)
    return f"{prefix}: {body}"


__all__ = [
    "CompositeNotifier",
    "EmailConfig",
    "EmailNotifier",
    "MacOSNotifier",
    "Notifier",
    "SlackNotifier",
    "SLACK_DEFAULT_TOOL_CANDIDATES",
]
