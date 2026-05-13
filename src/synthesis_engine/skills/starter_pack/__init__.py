"""Starter pack of universal skills bundled with Ragbot.

These six skills ship with every Ragbot installation. They are universal
in scope (visible from every workspace) and form the baseline capability
set the agent has out of the box, before the operator installs any of
their own skills or any third-party skill packs.

The pack is intentionally small. Each skill in the pack covers one
distinct agent operation:

* ``workspace-search-with-citations`` — retrieval with explicit citation.
* ``draft-and-revise`` — two-phase generation with a revision rubric.
* ``fact-check-claims`` — claim extraction and per-claim verdicts.
* ``summarize-document`` — three-section structured summary.
* ``agent-self-review`` — four-dimension rubric over the agent's turn.
* ``cross-workspace-synthesis`` — multi-workspace synthesis with explicit
  per-workspace citations, confidentiality enforcement, and an audit trail.

Discovery
---------

The starter pack lives under :mod:`synthesis_engine.skills.starter_pack`
inside the Ragbot source tree, so it is always present regardless of
filesystem layout. :func:`list_starter_skill_paths` returns absolute
paths to each skill directory in a stable order, suitable for feeding to
:func:`synthesis_engine.skills.discovery.discover_skills_in_root` or
:func:`synthesis_engine.skills.parser.parse_skill`.

The six returned paths are the source of truth for what ships in the
pack. Adding a seventh starter skill is a matter of dropping its directory
under this package and updating the ordered name list below.
"""

from __future__ import annotations

import os
from typing import List

# Canonical ordering of starter-pack skills. This is the order discovery
# returns them when the pack is enumerated directly; alphabetical when
# routed through ``discover_skills_in_root``. Both orderings are stable.
_STARTER_SKILL_NAMES: tuple = (
    "workspace-search-with-citations",
    "draft-and-revise",
    "fact-check-claims",
    "summarize-document",
    "agent-self-review",
    "cross-workspace-synthesis",
)


def starter_pack_root() -> str:
    """Return the absolute filesystem path of the starter-pack package.

    Equivalent to ``os.path.dirname(__file__)`` but goes through
    :func:`os.path.abspath` so a relative ``__file__`` (rare, but possible
    in some zipimport scenarios) is normalised.
    """
    return os.path.abspath(os.path.dirname(__file__))


def list_starter_skill_paths() -> List[str]:
    """Return absolute paths to each bundled starter-pack skill directory.

    The returned list is in the canonical order declared in
    ``_STARTER_SKILL_NAMES``. Each path is an existing directory that
    contains a ``SKILL.md`` file; the function does not return paths for
    skills that have been removed from the source tree without updating
    the name tuple, but it also does not silently invent skills that the
    tuple lists but the filesystem does not have.

    Discovery callers can feed this list directly to
    :func:`synthesis_engine.skills.parser.parse_skill` for each entry, or
    pass :func:`starter_pack_root` to
    :func:`synthesis_engine.skills.discovery.discover_skills_in_root` for
    bulk enumeration.

    Returns:
        A list of absolute directory paths.

    Raises:
        FileNotFoundError: If a name in the canonical tuple does not have
            a matching directory under the package root. This is a
            development-time signal that the tuple and the filesystem are
            out of sync; production builds should never raise it.
    """
    root = starter_pack_root()
    paths: List[str] = []
    missing: List[str] = []
    for name in _STARTER_SKILL_NAMES:
        candidate = os.path.join(root, name)
        if os.path.isdir(candidate) and os.path.isfile(
            os.path.join(candidate, "SKILL.md")
        ):
            paths.append(candidate)
        else:
            missing.append(name)
    if missing:
        raise FileNotFoundError(
            "Starter-pack skill directory or SKILL.md missing for: "
            + ", ".join(missing)
            + f". Searched under {root}."
        )
    return paths


__all__ = [
    "list_starter_skill_paths",
    "starter_pack_root",
]
