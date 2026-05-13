"""Agent-loop substrate for synthesis_engine.

This package implements a hand-rolled, framework-free agent loop on top of
the existing synthesis substrates:

  - ``synthesis_engine.mcp.MCPClient`` for tool calls
  - ``synthesis_engine.llm.get_llm_backend()`` for LLM calls
  - ``synthesis_engine.observability.*`` for tracing and metrics
  - ``synthesis_engine.memory.three_tier_retrieve`` for context

The design is explicit-FSM, not framework-driven. Each state in the loop
(INIT, PLAN, EXECUTE, EVALUATE, REPLAN, DONE, ERROR) has a dedicated async
transition function; the graph state itself is a serialisable dataclass
that round-trips through JSON for durable checkpoints.

Public surface:

    GraphState, PlanStep, AgentState, ActionType, StepStatus
        — the serialisable state model.

    AgentLoop
        — the FSM driver. Constructed with the substrates it consumes;
          methods ``run``, ``step``, and ``replay``.

    PermissionResult, PermissionGate, register_permission, check_permission
        — the tool-permission registry.

    make_plan, replan
        — the planning helpers (LLM-driven; structured JSON output).

    FilesystemCheckpointStore
        — durable per-transition state persistence.

Everything in this package is async at the boundary so it composes
cleanly with the async MCP client.
"""

from __future__ import annotations

from .checkpoints import FilesystemCheckpointStore
from .dispatch import SubAgentDispatcher, SubAgentFailure
from .grading import DEFAULT_PASS_THRESHOLD, GradingResult, SelfGrader
from .loop import (
    AgentLoop,
    SANDBOX_EXEC_TOOL_NAME,
    SUBAGENT_DISPATCH_TOOL_NAME,
)
from .permissions import (
    PermissionGate,
    PermissionRegistry,
    PermissionResult,
    ToolCallContext,
    check_permission,
    get_default_registry,
    register_permission,
)
from .planner import PlanValidationError, make_plan, replan
from .sandbox import (
    DaytonaSandbox,
    DisabledSandbox,
    E2BSandbox,
    ExecutionResult,
    Sandbox,
)
from .state import (
    ActionType,
    AgentState,
    ContextBlock,
    GraphState,
    PlanStep,
    StepStatus,
    TurnRecord,
)

__all__ = [
    # State
    "ActionType",
    "AgentState",
    "ContextBlock",
    "GraphState",
    "PlanStep",
    "StepStatus",
    "TurnRecord",
    # Loop
    "AgentLoop",
    "SANDBOX_EXEC_TOOL_NAME",
    "SUBAGENT_DISPATCH_TOOL_NAME",
    # Permissions
    "PermissionGate",
    "PermissionRegistry",
    "PermissionResult",
    "ToolCallContext",
    "check_permission",
    "get_default_registry",
    "register_permission",
    # Planning
    "PlanValidationError",
    "make_plan",
    "replan",
    # Checkpoints
    "FilesystemCheckpointStore",
    # Sandbox
    "DaytonaSandbox",
    "DisabledSandbox",
    "E2BSandbox",
    "ExecutionResult",
    "Sandbox",
    # Dispatch
    "SubAgentDispatcher",
    "SubAgentFailure",
    # Grading
    "DEFAULT_PASS_THRESHOLD",
    "GradingResult",
    "SelfGrader",
]
