"""MCP primitive wrappers.

Each module in this package wraps one MCP primitive against an active
:class:`mcp.ClientSession`. The wrappers exist so the runtime sees one
substrate-shaped surface ("list_tools(server_id)") and never has to
reach into the SDK's session directly.

Six primitives are covered, matching the 2025-11-25 spec:

* :mod:`tools` — ``tools/list``, ``tools/call``
* :mod:`resources` — ``resources/list``, ``resources/read``,
  ``resources/subscribe``, ``resources/unsubscribe``
* :mod:`prompts` — ``prompts/list``, ``prompts/get``
* :mod:`roots` — client-offered roots and the ``roots/list`` server-to-client
  inquiry, with a notify channel for ``notifications/roots/list_changed``
* :mod:`sampling` — server-initiated ``sampling/createMessage`` requests
* :mod:`elicitation` — server-initiated ``elicitation/create`` requests
  (form and URL modes)

The Tasks support is intentionally not a "primitive" in the spec sense;
it lives at :mod:`synthesis_engine.mcp.tasks` because it composes with
any other primitive's request.
"""

from .elicitation import ElicitationCallback, default_elicitation_handler
from .prompts import get_prompt, list_prompts
from .resources import (
    list_resource_templates,
    list_resources,
    read_resource,
    subscribe_resource,
    unsubscribe_resource,
)
from .roots import RootsProvider, StaticRootsProvider
from .sampling import SamplingCallback, default_sampling_handler
from .tools import call_tool, list_tools

__all__ = [
    # tools
    "list_tools",
    "call_tool",
    # resources
    "list_resources",
    "list_resource_templates",
    "read_resource",
    "subscribe_resource",
    "unsubscribe_resource",
    # prompts
    "list_prompts",
    "get_prompt",
    # roots
    "RootsProvider",
    "StaticRootsProvider",
    # sampling
    "SamplingCallback",
    "default_sampling_handler",
    # elicitation
    "ElicitationCallback",
    "default_elicitation_handler",
]
