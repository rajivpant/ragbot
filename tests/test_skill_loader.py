"""Tests for the skill loader, runtime, and parser tool-frontmatter (Phase 2 Agent B)."""

from __future__ import annotations

import asyncio
import os
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest

# Make ``src/`` importable just like the other test modules do.
_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src",
)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


from synthesis_engine.agent import (  # noqa: E402
    ActionType,
    AgentLoop,
    AgentState,
    GraphState,
    PermissionRegistry,
    PermissionResult,
    PlanStep,
    StepStatus,
)
from synthesis_engine.skills import (  # noqa: E402
    ActivatedSkill,
    ScriptNotFoundError,
    ScriptPathError,
    Skill,
    SkillLoader,
    SkillNotFoundError,
    SkillRuntime,
    SkillScope,
    SkillTool,
    make_skill_tool_target,
    parse_skill,
    parse_skill_tool_target,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_skill(
    root: Path,
    name: str,
    *,
    description: str = "test fixture",
    extra_frontmatter: str = "",
    body: str = "",
    scripts: Optional[Dict[str, str]] = None,
) -> Path:
    """Create a synthetic skill directory and return its absolute path."""
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    fm_parts = [
        "---",
        f"name: {name}",
        f"description: {description}",
    ]
    if extra_frontmatter:
        fm_parts.append(extra_frontmatter.rstrip())
    fm_parts.append("---")
    md = "\n".join(fm_parts) + "\n\n"
    md += body or f"# {name}\n\nDefault body.\n"
    (skill_dir / "SKILL.md").write_text(md)
    if scripts:
        for rel, content in scripts.items():
            target = skill_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
    return skill_dir


def _make_skill(root: Path, name: str, **kwargs) -> Skill:
    _write_skill(root, name, **kwargs)
    skill = parse_skill(str(root / name))
    assert skill is not None, f"parse_skill failed for {name}"
    return skill


# ---------------------------------------------------------------------------
# Tier 1: system-prompt fragment
# ---------------------------------------------------------------------------


class TestTier1Prompt:
    def test_lists_every_active_skill_with_name_and_description(
        self, tmp_path: Path
    ) -> None:
        s1 = _make_skill(tmp_path, "alpha", description="does alpha things")
        s2 = _make_skill(tmp_path, "beta", description="does beta things")
        loader = SkillLoader([s1, s2])

        prompt = loader.tier_1_system_prompt()

        assert "alpha" in prompt
        assert "beta" in prompt
        assert "does alpha things" in prompt
        assert "does beta things" in prompt
        # Sorted by name so the prompt is deterministic.
        assert prompt.index("alpha") < prompt.index("beta")

    def test_omits_skills_the_workspace_filter_excluded(
        self, tmp_path: Path
    ) -> None:
        # Caller pre-filters the skill list; only the surviving skills
        # land in the Tier-1 prompt. We model this by constructing the
        # loader with the filtered subset rather than calling discovery.
        all_skills = [
            _make_skill(tmp_path, "universal-skill"),
            _make_skill(tmp_path, "acme-news-only"),
        ]
        # Workspace filter passes only universal-skill through.
        filtered = [s for s in all_skills if s.name == "universal-skill"]
        loader = SkillLoader(filtered)

        prompt = loader.tier_1_system_prompt()

        assert "universal-skill" in prompt
        assert "acme-news-only" not in prompt

    def test_empty_active_set_returns_empty_string(self) -> None:
        loader = SkillLoader([])
        assert loader.tier_1_system_prompt() == ""

    def test_missing_description_falls_back_to_placeholder(
        self, tmp_path: Path
    ) -> None:
        # An empty description still produces a renderable line.
        s = _make_skill(tmp_path, "nameless", description="")
        loader = SkillLoader([s])
        prompt = loader.tier_1_system_prompt()
        assert "nameless" in prompt
        assert "(no description)" in prompt


# ---------------------------------------------------------------------------
# Tier 2: activate
# ---------------------------------------------------------------------------


class TestActivate:
    def test_returns_full_body_markdown(self, tmp_path: Path) -> None:
        body = "# alpha\n\nFull body content here.\n"
        s = _make_skill(tmp_path, "alpha", body=body)
        loader = SkillLoader([s])

        activated = loader.activate("alpha")

        assert isinstance(activated, ActivatedSkill)
        assert "Full body content here." in activated.body_markdown
        assert activated.skill is s

    def test_parses_bundled_tools_from_frontmatter(self, tmp_path: Path) -> None:
        extra = textwrap.dedent("""\
            tools:
              - name: write_note
                description: Write a note to the user's notebook
                parameters:
                  type: object
                  properties:
                    text:
                      type: string
                  required:
                    - text
              - name: read_note
                description: Read a note back
        """)
        s = _make_skill(tmp_path, "noter", extra_frontmatter=extra)
        loader = SkillLoader([s])

        activated = loader.activate("noter")

        assert len(activated.tools) == 2
        names = [t.name for t in activated.tools]
        assert names == ["write_note", "read_note"]
        write_tool = activated.tools[0]
        assert write_tool.description == "Write a note to the user's notebook"
        assert write_tool.parameters["type"] == "object"
        assert "text" in write_tool.parameters["properties"]

    def test_activate_is_cached_on_second_call(self, tmp_path: Path) -> None:
        s = _make_skill(tmp_path, "alpha")
        loader = SkillLoader([s])

        a = loader.activate("alpha")
        b = loader.activate("alpha")

        # LRU hit returns the same dataclass instance.
        assert a is b
        info = loader.cache_info()
        assert info.hits == 1
        assert info.misses == 1

    def test_invalidate_cache_busts_lru(self, tmp_path: Path) -> None:
        s = _make_skill(tmp_path, "alpha")
        loader = SkillLoader([s])

        a = loader.activate("alpha")
        loader.invalidate_cache()
        b = loader.activate("alpha")
        assert a is not b

    def test_raises_clearly_for_unknown_skill_name(self, tmp_path: Path) -> None:
        loader = SkillLoader([_make_skill(tmp_path, "alpha")])
        with pytest.raises(SkillNotFoundError, match="unknown skill 'ghost'"):
            loader.activate("ghost")

    def test_pre_loaded_context_strings_normalised(self, tmp_path: Path) -> None:
        extra = textwrap.dedent("""\
            pre_loaded_context:
              - Always greet the user.
              - text: Use polite phrasing.
                source: style-guide
        """)
        s = _make_skill(tmp_path, "etiquette", extra_frontmatter=extra)
        loader = SkillLoader([s])

        activated = loader.activate("etiquette")

        assert len(activated.pre_loaded_context) == 2
        assert activated.pre_loaded_context[0]["text"] == "Always greet the user."
        assert activated.pre_loaded_context[0]["source"] == "skill"
        assert activated.pre_loaded_context[1]["source"] == "style-guide"


# ---------------------------------------------------------------------------
# Tier 3: load_script
# ---------------------------------------------------------------------------


class TestLoadScript:
    def test_returns_bytes_for_existing_script(self, tmp_path: Path) -> None:
        s = _make_skill(
            tmp_path,
            "scripty",
            scripts={"scripts/hello.py": "print('hi')\n"},
        )
        loader = SkillLoader([s])

        data = loader.load_script("scripty", "scripts/hello.py")

        assert isinstance(data, bytes)
        assert data == b"print('hi')\n"

    def test_raises_clearly_for_missing_script(self, tmp_path: Path) -> None:
        s = _make_skill(tmp_path, "scripty")
        loader = SkillLoader([s])

        with pytest.raises(ScriptNotFoundError, match="missing.py"):
            loader.load_script("scripty", "scripts/missing.py")

    def test_rejects_path_traversal(self, tmp_path: Path) -> None:
        # Create a sibling file outside the skill root we should never read.
        secret = tmp_path / "outside-secret.txt"
        secret.write_text("classified")
        s = _make_skill(tmp_path, "scripty")
        loader = SkillLoader([s])

        with pytest.raises(ScriptPathError, match="escapes the skill root"):
            loader.load_script("scripty", "../outside-secret.txt")

    def test_rejects_absolute_path(self, tmp_path: Path) -> None:
        s = _make_skill(tmp_path, "scripty")
        loader = SkillLoader([s])

        with pytest.raises(ScriptPathError, match="must be relative"):
            loader.load_script("scripty", "/etc/passwd")

    def test_load_script_raises_for_unknown_skill(self, tmp_path: Path) -> None:
        s = _make_skill(tmp_path, "scripty")
        loader = SkillLoader([s])

        with pytest.raises(SkillNotFoundError):
            loader.load_script("ghost", "scripts/x.py")


# ---------------------------------------------------------------------------
# Runtime: permission-gate registration
# ---------------------------------------------------------------------------


def _skill_with_tools(
    tmp_path: Path,
    name: str,
    tools_yaml: str,
    permissions_yaml: str = "",
) -> Skill:
    """Build a Skill with a tools: block and optional tool_permissions: block."""
    extra = "tools:\n" + textwrap.indent(tools_yaml.rstrip(), "  ")
    if permissions_yaml:
        extra += "\ntool_permissions:\n" + textwrap.indent(
            permissions_yaml.rstrip(), "  "
        )
    return _make_skill(tmp_path, name, extra_frontmatter=extra)


class TestRegisterSkillTools:
    def test_registers_gates_for_each_declared_tool(self, tmp_path: Path) -> None:
        tools = textwrap.dedent("""\
            - name: tool_a
              description: tool a
            - name: tool_b
              description: tool b
        """)
        permissions = textwrap.dedent("""\
            tool_a: allow
            tool_b: allow
        """)
        skill = _skill_with_tools(tmp_path, "multi", tools, permissions)
        registry = PermissionRegistry()
        loader = SkillLoader([skill])
        runtime = SkillRuntime(loader, registry)

        registered = runtime.register_skill_tools("multi")

        assert {t.name for t in registered} == {"tool_a", "tool_b"}
        # Each tool target has at least one gate now.
        for tool_name in ("tool_a", "tool_b"):
            target = make_skill_tool_target("multi", tool_name)
            verdict = registry.check(target, arguments={})
            assert verdict.allowed is True

    def test_default_for_tools_without_explicit_verdict_is_fail_closed(
        self, tmp_path: Path
    ) -> None:
        # tool_a declared but no tool_permissions entry → fail-closed.
        tools = textwrap.dedent("""\
            - name: tool_a
              description: tool a
        """)
        skill = _skill_with_tools(tmp_path, "stealth", tools, permissions_yaml="")
        registry = PermissionRegistry()
        runtime = SkillRuntime(SkillLoader([skill]), registry)

        runtime.register_skill_tools("stealth")

        target = make_skill_tool_target("stealth", "tool_a")
        verdict = registry.check(target, arguments={})
        assert verdict.allowed is False
        assert "fail-closed" in verdict.reason.lower() or "no explicit" in (
            verdict.reason.lower()
        )

    def test_honors_allow_verdict(self, tmp_path: Path) -> None:
        tools = textwrap.dedent("""\
            - name: tool_a
              description: tool a
        """)
        permissions = "tool_a: allow\n"
        skill = _skill_with_tools(tmp_path, "permitter", tools, permissions)
        registry = PermissionRegistry()
        runtime = SkillRuntime(SkillLoader([skill]), registry)
        runtime.register_skill_tools("permitter")

        target = make_skill_tool_target("permitter", "tool_a")
        verdict = registry.check(target, arguments={})

        assert verdict.allowed is True
        assert "allow" in verdict.reason.lower()

    def test_honors_deny_with_reason(self, tmp_path: Path) -> None:
        tools = textwrap.dedent("""\
            - name: tool_a
              description: tool a
        """)
        permissions = "tool_a: 'deny:tool is not yet audited'\n"
        skill = _skill_with_tools(tmp_path, "denier", tools, permissions)
        registry = PermissionRegistry()
        runtime = SkillRuntime(SkillLoader([skill]), registry)
        runtime.register_skill_tools("denier")

        target = make_skill_tool_target("denier", "tool_a")
        verdict = registry.check(target, arguments={})

        assert verdict.allowed is False
        assert "tool is not yet audited" in verdict.reason
        assert verdict.requires_user_confirmation is False

    def test_honors_prompt_verdict(self, tmp_path: Path) -> None:
        tools = textwrap.dedent("""\
            - name: tool_a
              description: tool a
        """)
        permissions = "tool_a: prompt\n"
        skill = _skill_with_tools(tmp_path, "asker", tools, permissions)
        registry = PermissionRegistry()
        runtime = SkillRuntime(SkillLoader([skill]), registry)
        runtime.register_skill_tools("asker")

        target = make_skill_tool_target("asker", "tool_a")
        verdict = registry.check(target, arguments={})

        assert verdict.allowed is False
        assert verdict.requires_user_confirmation is True

    def test_unknown_verdict_falls_back_to_deny(self, tmp_path: Path) -> None:
        tools = textwrap.dedent("""\
            - name: tool_a
              description: tool a
        """)
        permissions = "tool_a: maybe-later\n"
        skill = _skill_with_tools(tmp_path, "weird", tools, permissions)
        registry = PermissionRegistry()
        runtime = SkillRuntime(SkillLoader([skill]), registry)
        runtime.register_skill_tools("weird")

        target = make_skill_tool_target("weird", "tool_a")
        verdict = registry.check(target, arguments={})

        assert verdict.allowed is False
        assert "unrecognised" in verdict.reason.lower()

    def test_register_is_idempotent(self, tmp_path: Path) -> None:
        tools = "- name: tool_a\n  description: tool a\n"
        permissions = "tool_a: allow\n"
        skill = _skill_with_tools(tmp_path, "again", tools, permissions)
        registry = PermissionRegistry()
        runtime = SkillRuntime(SkillLoader([skill]), registry)

        runtime.register_skill_tools("again")
        runtime.register_skill_tools("again")  # second call replaces

        target = make_skill_tool_target("again", "tool_a")
        verdict = registry.check(target, arguments={})
        assert verdict.allowed is True


# ---------------------------------------------------------------------------
# Runtime: agent-loop integration
# ---------------------------------------------------------------------------


class _DummyLLM:
    """Tiny LLM stub — the wrap_agent_loop test never invokes it."""
    calls: List[Any] = []

    def complete(self, request):  # pragma: no cover - never called in this test
        raise AssertionError("LLM should not be called in skill-dispatch test")


class _DummyMCP:
    """MCP client that should never be consulted for skill-tool dispatch."""
    async def list_tools(self, server_id):
        return []

    async def call_tool(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError(
            "MCP client should not be invoked for skill-tool targets"
        )


class TestWrapAgentLoopIntegration:
    @pytest.mark.asyncio
    async def test_skill_tool_dispatches_through_runtime_and_gate_runs(
        self, tmp_path: Path
    ) -> None:
        tools = textwrap.dedent("""\
            - name: capture
              description: capture structured output
        """)
        permissions = "capture: allow\n"
        skill = _skill_with_tools(tmp_path, "writer", tools, permissions)

        registry = PermissionRegistry()
        gate_invocations: List[str] = []

        def recording_gate(ctx):
            gate_invocations.append(ctx.tool_name)
            return PermissionResult.allow("test allow")

        loader = SkillLoader([skill])
        runtime = SkillRuntime(loader, registry)
        # Register the runtime's ``allow`` gate first via the frontmatter
        # declaration, then layer a recording gate on top. The runtime
        # honours both — every registered gate runs in order and the
        # first non-ALLOW wins; here both ALLOW so the call passes and
        # the recorder captures the dispatch.
        runtime.register_skill_tools("writer")
        registry.register(
            make_skill_tool_target("writer", "capture"), recording_gate
        )

        loop = AgentLoop(
            llm_backend=_DummyLLM(),
            mcp_client=_DummyMCP(),
            permission_registry=registry,
            default_mcp_server="local",
        )
        runtime.wrap_agent_loop(loop)

        state = GraphState.new("dispatch a skill tool")
        target = make_skill_tool_target("writer", "capture")
        step = PlanStep(
            step_id="s1",
            action_type=ActionType.TOOL_CALL,
            target=target,
            inputs={"text": "hello"},
        )
        state.plan = [step]

        # Drive one EXECUTE transition manually.
        state.current_state = AgentState.EXECUTE
        new_state = await loop.step(state)

        assert step.status == StepStatus.SUCCEEDED, step.error
        # Gate ran with the right tool name.
        assert target in gate_invocations
        # Output captured the structured arguments.
        output = step.output
        assert isinstance(output, dict)
        assert output["skill"] == "writer"
        assert output["tool"] == "capture"
        assert output["arguments"] == {"text": "hello"}
        # Loop progressed past EXECUTE.
        assert new_state.current_state == AgentState.EVALUATE

    @pytest.mark.asyncio
    async def test_skill_tool_dispatch_blocked_by_deny_gate(
        self, tmp_path: Path
    ) -> None:
        tools = "- name: blocked\n  description: nope\n"
        permissions = "blocked: 'deny:policy says no'\n"
        skill = _skill_with_tools(tmp_path, "shut", tools, permissions)

        registry = PermissionRegistry()
        loader = SkillLoader([skill])
        runtime = SkillRuntime(loader, registry)
        runtime.register_skill_tools("shut")

        loop = AgentLoop(
            llm_backend=_DummyLLM(),
            mcp_client=_DummyMCP(),
            permission_registry=registry,
            default_mcp_server="local",
        )
        runtime.wrap_agent_loop(loop)

        state = GraphState.new("attempt blocked tool")
        target = make_skill_tool_target("shut", "blocked")
        step = PlanStep(
            step_id="s1",
            action_type=ActionType.TOOL_CALL,
            target=target,
            inputs={},
        )
        state.plan = [step]
        state.current_state = AgentState.EXECUTE

        await loop.step(state)

        assert step.status == StepStatus.FAILED
        assert step.error is not None
        assert "Permission denied" in step.error
        assert "policy says no" in step.error


# ---------------------------------------------------------------------------
# Runtime: available_tools_for workspace filtering
# ---------------------------------------------------------------------------


class TestAvailableToolsFor:
    def test_filters_by_workspace_inheritance(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        # Build three skills in synthetic workspace locations and verify
        # available_tools_for(workspace) only returns tools visible from
        # that workspace's inheritance chain.
        home = tmp_path / "fakehome"
        (home / ".synthesis" / "skills").mkdir(parents=True)
        (home / ".claude" / "skills").mkdir(parents=True)
        (home / "workspaces" / "acme-user" / "synthesis-skills").mkdir(
            parents=True
        )
        identity = home / ".synthesis" / "identity.yaml"
        identity.write_text("personal_workspaces:\n  - acme-user\n")
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        monkeypatch.setenv("SYNTHESIS_IDENTITY_CONFIG", str(identity))

        # Universal skill with a tool — visible from everywhere.
        universal_tools = textwrap.dedent("""\
            - name: shared_tool
              description: visible everywhere
        """)
        universal = _skill_with_tools(
            home / ".synthesis" / "skills",
            "universal-skill",
            universal_tools,
            permissions_yaml="shared_tool: allow\n",
        )

        # Workspace-scoped skill under ~/workspaces/acme-news/synthesis-skills-acme-news/
        (home / "workspaces" / "acme-news" / "synthesis-skills-acme-news").mkdir(
            parents=True
        )
        news_tools = textwrap.dedent("""\
            - name: news_only_tool
              description: only news workspace
        """)
        news_skill = _skill_with_tools(
            home / "workspaces" / "acme-news" / "synthesis-skills-acme-news",
            "news-skill",
            news_tools,
            permissions_yaml="news_only_tool: allow\n",
        )

        # Loader holds every skill the runtime knows about; runtime
        # then filters down to what each workspace can see.
        loader = SkillLoader([universal, news_skill])
        registry = PermissionRegistry()
        runtime = SkillRuntime(loader, registry)

        from_news = runtime.available_tools_for("acme-news")
        from_other = runtime.available_tools_for("acme-other")

        news_names = {t.name for t in from_news}
        other_names = {t.name for t in from_other}

        assert "shared_tool" in news_names
        assert "news_only_tool" in news_names
        # acme-other does not inherit acme-news; only the universal tool
        # surfaces there.
        assert "shared_tool" in other_names
        assert "news_only_tool" not in other_names


# ---------------------------------------------------------------------------
# Parser: tool / tool_permissions frontmatter parsing
# ---------------------------------------------------------------------------


class TestParserToolFrontmatter:
    def test_skill_without_tools_has_empty_defaults(self, tmp_path: Path) -> None:
        s = _make_skill(tmp_path, "plain")
        assert s.tools == []
        assert s.tool_permissions == {}

    def test_malformed_tool_entry_is_dropped(self, tmp_path: Path) -> None:
        extra = textwrap.dedent("""\
            tools:
              - description: missing-name
              - name: real_tool
                description: real
        """)
        s = _make_skill(tmp_path, "halfgood", extra_frontmatter=extra)
        names = [t.name for t in s.tools]
        assert names == ["real_tool"]

    def test_tool_permissions_parsed_as_strings(self, tmp_path: Path) -> None:
        extra = textwrap.dedent("""\
            tool_permissions:
              alpha: allow
              beta: 'deny:not yet'
              gamma: prompt
        """)
        s = _make_skill(tmp_path, "policy", extra_frontmatter=extra)
        assert s.tool_permissions == {
            "alpha": "allow",
            "beta": "deny:not yet",
            "gamma": "prompt",
        }
