"""SKILL.md parser and skill directory loader."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

from .model import Skill, SkillFile, SkillFileKind

logger = logging.getLogger(__name__)


# File extensions classified as scripts (indexed as text but flagged for the
# compiler to render by name only).
_SCRIPT_EXTENSIONS = {
    ".py", ".sh", ".bash", ".zsh", ".fish",
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".rb", ".go", ".rs", ".lua", ".pl",
    ".sql",
}

# File extensions classified as text (indexable). Anything else with content
# we can decode as UTF-8 is treated as ``OTHER`` and still indexed.
_TEXT_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".rst",
    ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg",
    ".html", ".htm", ".xml",
    ".csv", ".tsv",
}

# Files we never index — locks, binaries, version-controlled internals.
_IGNORED_NAMES = {
    ".DS_Store", "Thumbs.db",
    "__pycache__", ".git", ".github",
}
_IGNORED_PREFIXES = (".",)
_IGNORED_SUFFIXES = (".pyc", ".pyo", ".so", ".dylib", ".dll", ".class", ".o")


def _split_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """Extract YAML frontmatter from a SKILL.md body.

    Frontmatter convention: ``---`` … ``---`` at the very top of the file.
    Returns ``({}, body)`` when no frontmatter is present so the function
    is total.
    """

    if not text.startswith("---"):
        return {}, text

    # Find the closing fence on its own line.
    rest = text[3:]
    end_idx = rest.find("\n---")
    if end_idx == -1:
        return {}, text

    fm_text = rest[:end_idx]
    body = rest[end_idx + len("\n---"):]
    # Trim a single leading newline after the closing fence for cleanliness.
    if body.startswith("\n"):
        body = body[1:]

    try:
        fm = yaml.safe_load(fm_text) or {}
        if not isinstance(fm, dict):
            logger.warning("SKILL.md frontmatter is not a mapping; ignoring.")
            return {}, text
    except yaml.YAMLError as exc:
        logger.warning("SKILL.md frontmatter parse failed: %s", exc)
        return {}, text

    return fm, body


def parse_skill_md(path: str) -> Tuple[Dict[str, Any], str]:
    """Parse a SKILL.md file and return ``(frontmatter, body)``."""

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return _split_frontmatter(text)


def _classify(relative_path: str) -> SkillFileKind:
    name = os.path.basename(relative_path).lower()
    parent_lower = os.path.dirname(relative_path).lower().replace("\\", "/")
    ext = os.path.splitext(name)[1].lower()

    if name == "skill.md":
        return SkillFileKind.SKILL_MD

    # references/ directory or nested markdown reference docs.
    if (
        parent_lower.startswith("references")
        or parent_lower.endswith("/references")
        or parent_lower == "references"
    ):
        return SkillFileKind.REFERENCE

    if ext in _SCRIPT_EXTENSIONS:
        return SkillFileKind.SCRIPT

    if ext in (".md", ".markdown") or ext in _TEXT_EXTENSIONS:
        # Markdown outside references/ is still treated as a reference (it
        # documents the skill); other text artifacts are ``OTHER``.
        if ext in (".md", ".markdown"):
            return SkillFileKind.REFERENCE
        return SkillFileKind.OTHER

    return SkillFileKind.OTHER


def _is_ignored(name: str) -> bool:
    if name in _IGNORED_NAMES:
        return True
    if any(name.startswith(p) for p in _IGNORED_PREFIXES) and name not in (".env.example",):
        return True
    if any(name.endswith(s) for s in _IGNORED_SUFFIXES):
        return True
    return False


def _read_text(path: str) -> Tuple[str, bool]:
    """Read a file as UTF-8 text. Returns ``(content, is_text)``.

    Binary files return ``("", False)`` so the caller can include them in
    the file list without their content (e.g., images).
    """

    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read(), True
    except UnicodeDecodeError:
        return "", False
    except OSError as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return "", False


def _walk_skill_files(skill_root: str) -> list:
    """Walk a skill directory and yield SkillFile objects (skill.md first)."""

    skill_root = os.path.abspath(skill_root)
    files: list = []
    skill_md_file: Optional[SkillFile] = None

    for current, dirs, names in os.walk(skill_root):
        # Prune ignored directories in-place.
        dirs[:] = [d for d in dirs if not _is_ignored(d)]

        for name in names:
            if _is_ignored(name):
                continue
            absolute = os.path.join(current, name)
            relative = os.path.relpath(absolute, skill_root).replace("\\", "/")
            kind = _classify(relative)
            content, is_text = _read_text(absolute)

            sf = SkillFile(
                relative_path=relative,
                absolute_path=absolute,
                kind=kind,
                content=content,
                is_text=is_text,
            )
            if kind is SkillFileKind.SKILL_MD:
                skill_md_file = sf
            else:
                files.append(sf)

    if skill_md_file is not None:
        files.insert(0, skill_md_file)
    return files


def parse_skill(directory: str) -> Optional[Skill]:
    """Parse a skill directory. Returns None if SKILL.md is absent.

    The directory's basename is the default skill name; if frontmatter
    declares ``name``, that wins (so a renamed directory keeps the canonical
    identifier).
    """

    directory = os.path.abspath(directory)
    skill_md_path = os.path.join(directory, "SKILL.md")
    if not os.path.isfile(skill_md_path):
        return None

    try:
        frontmatter, body = parse_skill_md(skill_md_path)
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Could not parse %s: %s", skill_md_path, exc)
        return None

    name = str(frontmatter.get("name") or os.path.basename(directory))
    description = str(frontmatter.get("description") or "").strip()

    files = _walk_skill_files(directory)

    return Skill(
        name=name,
        path=directory,
        skill_md_path=skill_md_path,
        description=description,
        body=body.strip(),
        frontmatter=frontmatter,
        files=files,
    )
