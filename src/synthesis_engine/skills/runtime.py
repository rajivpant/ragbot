"""Skill runtime: wires a :class:`SkillLoader` into an :class:`AgentLoop`.

The loader handles the static side of skills (parsing, caching, script
bytes). The runtime is the dynamic side: it registers permission gates,
dispatches skill-tool calls through the agent loop's tool router, and
exposes the active tool set per workspace.

Architecture
============

The agent loop already knows how to dispatch ``TOOL_CALL`` action types
through an MCP client. We let it keep doing that for MCP tools, and we
add a separate dispatch path for skill-declared tools:

* ``wrap_agent_loop`` patches the loop's ``_dispatch_tool_call`` method
  with a wrapper that checks "is this tool name one of mine?" first.
  Skill-tool dispatch routes through the runtime; everything else falls
  through to the original MCP-backed dispatch.

* The wrapper preserves the loop's existing instrumentation: every
  skill-tool call still fires a ``tool_span`` and still runs through the
  permission registry.

* Skill-tools without bundled scripts are structured-output channels:
  the LLM produced the arguments, the runtime captures them, and the
  step output is the arguments themselves (with the tool name and skill
  name attached). The SKILL.md body is what tells the LLM what to do
  with that captured shape.

* Skill-tools with bundled scripts hand the script bytes to whatever
  executor the loop has configured. For Python code, the loop's
  :class:`Sandbox` is the right target (Round 4b). For shell, a
  subprocess-backed adapter is the right target — but that adapter is
  not part of this round. The runtime exposes the script bytes via the
  loader; the loop's sandbox-dispatch path picks them up.

Permission semantics
====================

Every skill-tool call passes through
:class:`synthesis_engine.agent.permissions.PermissionRegistry` before it
runs. The gate is decided at ``register_skill_tools`` time:

* ``allow``        → :meth:`PermissionResult.allow`
* ``deny:<reason>`` → :meth:`PermissionResult.deny` with the reason text
* ``prompt``       → :meth:`PermissionResult.prompt` (soft deny pending
                     user confirmation)
* missing / unknown → fail-closed default (DENY_WITH_REASON consistent
                     with Round 4a)

The runtime never relaxes the permission model. A skill author who
wants their tool to be callable by the agent has to declare ``allow``
explicitly in their ``tool_permissions:`` block.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ..agent.permissions import (
    PermissionRegistry,
    PermissionResult,
    ToolCallContext,
)
from .discovery import get_skills_for_workspace
from .loader import ActivatedSkill, SkillLoader
from .model import Skill, SkillTool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool-namespacing convention
# ---------------------------------------------------------------------------


# Skill tools are surfaced to the planner as ``skill::<skill_name>::<tool>``
# so the agent's plan can disambiguate them from MCP tools without a
# parsing collision (MCP tools use ``server::tool``; the extra
# ``skill::`` prefix keeps the two namespaces apart).
SKILL_TOOL_PREFIX: str = "skill"
SKILL_TOOL_SEPARATOR: str = "::"


def make_skill_tool_target(skill_name: str, tool_name: str) -> str:
    """Build the planner-facing target string for a skill tool."""
    return f"{SKILL_TOOL_PREFIX}{SKILL_TOOL_SEPARATOR}{skill_name}{SKILL_TOOL_SEPARATOR}{tool_name}"


def parse_skill_tool_target(target: str) -> Optional[tuple]:
    """Return ``(skill_name, tool_name)`` if ``target`` is a skill-tool ref.

    Returns ``None`` for any other shape so the caller can fall through
    to the regular MCP dispatch.
    """
    if not target:
        return None
    parts = target.split(SKILL_TOOL_SEPARATOR)
    if len(parts) != 3:
        return None
    if parts[0] != SKILL_TOOL_PREFIX:
        return None
    skill_name = parts[1].strip()
    tool_name = parts[2].strip()
    if not skill_name or not tool_name:
        return None
    return skill_name, tool_name


# ---------------------------------------------------------------------------
# Permission-verdict parsing
# ---------------------------------------------------------------------------


def _verdict_for_gate(
    verdict_string: Optional[str],
) -> Callable[[ToolCallContext], PermissionResult]:
    """Compile a frontmatter verdict string into a permission gate function.

    Accepts:

    * ``None`` / missing → fail-closed default (DENY_WITH_REASON). The
      registry's own default-gate logic would handle this if we let it,
      but registering an explicit gate keeps the policy auditable: a
      ``ragbot skills permissions list`` command shows the policy
      directly without falling back to pattern-based inference.

    * ``"allow"``        → PermissionResult.allow
    * ``"deny[:reason]"`` → PermissionResult.deny with the reason
    * ``"prompt"``       → PermissionResult.prompt
    """

    if verdict_string is None or not verdict_string.strip():
        reason = (
            "Skill tool has no explicit permission verdict; fail-closed "
            "default applies. Declare tool_permissions in SKILL.md to "
            "enable it."
        )
        return lambda _ctx: PermissionResult.deny(reason)

    token = verdict_string.strip()
    lowered = token.lower()

    if lowered == "allow":
        return lambda _ctx: PermissionResult.allow(
            "Skill declared 'allow' for this tool."
        )

    if lowered == "prompt":
        return lambda _ctx: PermissionResult.prompt(
            "Skill declared 'prompt' — operator confirmation required."
        )

    if lowered.startswith("deny"):
        # Accept "deny", "deny:reason", "deny: reason".
        reason = ""
        if ":" in token:
            reason = token.split(":", 1)[1].strip()
        if not reason:
            reason = "Skill declared 'deny' for this tool."
        return lambda _ctx, _reason=reason: PermissionResult.deny(_reason)

    # Unknown verdict: fail-closed, but surface the typo so it's debuggable.
    reason = (
        f"Skill declared an unrecognised permission verdict "
        f"{verdict_string!r}; expected one of 'allow', 'deny[:reason]', "
        f"'prompt'. Fail-closed default applies."
    )
    return lambda _ctx, _reason=reason: PermissionResult.deny(_reason)


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------


# A tool executor is an async callable the loop hands raw scripts to.
# The runtime calls ``executor(skill_name, tool, script_bytes, arguments)``
# and returns the executor's result as the tool's step output. The
# default executor returns ``None`` and logs a warning — callers wire a
# real executor (e.g., a sandbox adapter) by passing it to the runtime
# constructor.
ToolScriptExecutor = Callable[
    [str, SkillTool, bytes, Dict[str, Any]],
    Awaitable[Any],
]


class SkillRuntime:
    """Runtime that registers and dispatches skill-declared tools."""

    def __init__(
        self,
        loader: SkillLoader,
        permission_registry: PermissionRegistry,
        *,
        script_executor: Optional[ToolScriptExecutor] = None,
    ) -> None:
        self._loader = loader
        self._permissions = permission_registry
        self._script_executor: ToolScriptExecutor = (
            script_executor or _default_script_executor
        )
        # Tracks which tool names this runtime has registered gates for,
        # so wrap_agent_loop knows which targets to claim.
        self._registered_tools: Dict[str, tuple] = {}
        # The previous _dispatch_tool_call bound method, kept so
        # unwrap_agent_loop can restore the loop's original behaviour.
        self._original_dispatch: Optional[Callable] = None
        self._wrapped_loop: Optional[Any] = None

    # ----- registration -----------------------------------------------------

    def register_skill_tools(self, skill_name: str) -> List[SkillTool]:
        """Register permission gates for every tool the named skill declares.

        Returns the list of tools that were registered. Idempotent: a
        second call replaces prior gates for the same tool name.
        """

        activated: ActivatedSkill = self._loader.activate(skill_name)
        skill: Skill = activated.skill
        tools = list(activated.tools)
        permissions = skill.tool_permissions or {}

        for tool in tools:
            verdict_string = permissions.get(tool.name)
            gate = _verdict_for_gate(verdict_string)
            target = make_skill_tool_target(skill_name, tool.name)
            # Replace any prior gate for the same target (idempotent).
            self._permissions.unregister(target)
            self._permissions.register(target, gate)
            self._registered_tools[target] = (skill_name, tool)

        return tools

    def registered_targets(self) -> List[str]:
        """Return every target string the runtime claims for dispatch."""
        return sorted(self._registered_tools)

    # ----- workspace view ---------------------------------------------------

    def available_tools_for(self, workspace_name: str) -> List[SkillTool]:
        """Return every skill-tool visible from ``workspace_name``.

        Walks the workspace's inheritance chain via
        :func:`get_skills_for_workspace`. The result is the union of
        every visible skill's declared tools, in skill-name then
        tool-name order. The loader itself may have been built against a
        broader set (the operator might preload every skill at session
        start); this method filters to what the workspace can actually
        see.
        """

        visible_skills = {
            s.name: s for s in get_skills_for_workspace(workspace_name)
        }
        # Intersect with what the loader knows so we don't surface tools
        # the loader has no way to activate.
        candidates: List[SkillTool] = []
        for skill in self._loader.active_skills:
            if skill.name not in visible_skills:
                continue
            for tool in skill.tools:
                candidates.append(tool)
        # Tools sort first by skill name (the discovery-layer key) then
        # by tool name within a skill.
        candidates.sort(key=lambda t: t.name)
        return candidates

    # ----- agent-loop wiring ------------------------------------------------

    def wrap_agent_loop(self, loop: Any) -> None:
        """Install the runtime as the agent loop's skill-aware tool source.

        The loop's existing ``_dispatch_tool_call`` keeps handling MCP
        tools. We patch in a wrapper that intercepts targets matching
        ``skill::<skill>::<tool>`` and routes them through the runtime;
        anything else falls through. Permission checks happen in the
        runtime path before the executor or capture, mirroring the MCP
        path's "gate first" contract.
        """

        if self._wrapped_loop is not None:
            raise RuntimeError(
                "SkillRuntime is already attached to an agent loop; "
                "detach it first via unwrap_agent_loop()."
            )

        original = loop._dispatch_tool_call  # type: ignore[attr-defined]
        self._original_dispatch = original
        self._wrapped_loop = loop

        runtime = self

        async def patched_dispatch(state, step, inputs):
            parsed = parse_skill_tool_target(step.target)
            if parsed is None:
                return await original(state, step, inputs)
            skill_name, tool_name = parsed
            return await runtime._dispatch_skill_tool(
                loop, state, step, inputs, skill_name, tool_name
            )

        # Bind the wrapper as a method on the loop instance so it sees
        # the same ``self`` original would have seen.
        loop._dispatch_tool_call = patched_dispatch  # type: ignore[attr-defined]

    def unwrap_agent_loop(self) -> None:
        """Restore the agent loop's original tool-dispatch behaviour."""
        if self._wrapped_loop is None or self._original_dispatch is None:
            return
        self._wrapped_loop._dispatch_tool_call = self._original_dispatch
        self._wrapped_loop = None
        self._original_dispatch = None

    # ----- dispatch ---------------------------------------------------------

    async def _dispatch_skill_tool(
        self,
        loop: Any,
        state: Any,
        step: Any,
        inputs: Dict[str, Any],
        skill_name: str,
        tool_name: str,
    ) -> Any:
        target = make_skill_tool_target(skill_name, tool_name)

        # Permission gate first, mirroring the MCP dispatch contract.
        verdict: PermissionResult = self._permissions.check(
            target,
            arguments=inputs,
            context=ToolCallContext(
                tool_name=target,
                arguments=inputs,
                server_id="skill",
                task_id=getattr(state, "task_id", None),
                metadata={
                    "step_id": getattr(step, "step_id", None),
                    "skill_name": skill_name,
                    "tool_name": tool_name,
                },
            ),
        )
        if not verdict.allowed:
            raise PermissionError(verdict.reason)

        # Look up the SkillTool; the registration map is the source of
        # truth so a tool the runtime never registered cannot be invoked
        # even if it appears on the loader.
        registered = self._registered_tools.get(target)
        if registered is None:
            raise RuntimeError(
                f"Skill tool {target!r} is not registered; call "
                f"register_skill_tools({skill_name!r}) before dispatch."
            )
        _skill_name, tool = registered

        # Reach for the loop's tool_span so the dispatch lands in OTEL
        # alongside MCP calls. Fall back to a noop CM if unavailable.
        tool_span = getattr(
            loop,
            "_tool_span",
            None,
        ) or _noop_cm

        with tool_span(
            tool_name=target,
            tool_type="skill",
            extra={
                "synthesis.skill.name": skill_name,
                "synthesis.skill.tool_name": tool_name,
            },
        ) as span:
            if tool.script:
                script_bytes = self._loader.load_script(
                    skill_name, tool.script
                )
                output = await self._script_executor(
                    skill_name, tool, script_bytes, inputs
                )
            else:
                # Structured-output channel: capture the args verbatim.
                output = {
                    "skill": skill_name,
                    "tool": tool_name,
                    "arguments": dict(inputs or {}),
                    "description": tool.description,
                }
            try:
                if span is not None:
                    span.set_attribute(
                        "synthesis.skill.has_script", bool(tool.script)
                    )
            except Exception:  # pragma: no cover - defensive
                pass
            return output


# ---------------------------------------------------------------------------
# Default executor + span fallback
# ---------------------------------------------------------------------------


async def _default_script_executor(
    skill_name: str,
    tool: SkillTool,
    script_bytes: bytes,
    arguments: Dict[str, Any],
) -> Any:
    """No-op default executor.

    Returns a manifest describing the script the runtime would have
    handed to a real executor. Real deployments pass a sandbox-backed
    callable to ``SkillRuntime(script_executor=...)``.
    """
    logger.warning(
        "SkillRuntime invoked the default script executor for "
        "skill=%s tool=%s — wire a real executor via "
        "SkillRuntime(script_executor=...). Returning a manifest.",
        skill_name,
        tool.name,
    )
    return {
        "skill": skill_name,
        "tool": tool.name,
        "script_path": tool.script,
        "script_size_bytes": len(script_bytes),
        "arguments": dict(arguments or {}),
        "executor": "default-noop",
    }


@contextlib.contextmanager
def _noop_cm(*_args, **_kwargs):
    yield None


__all__ = [
    "SKILL_TOOL_PREFIX",
    "SKILL_TOOL_SEPARATOR",
    "SkillRuntime",
    "ToolScriptExecutor",
    "make_skill_tool_target",
    "parse_skill_tool_target",
]
