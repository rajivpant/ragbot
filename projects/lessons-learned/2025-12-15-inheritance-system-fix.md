# Lessons Learned: RAG Inheritance System Fix

**Date:** 2025-12-15
**Project:** RAG Relevance Improvements
**Context:** Phase 3 testing revealed inheritance was broken

## Summary

During Phase 3 testing, discovered workspace inheritance wasn't working - mcclatchy couldn't find ragbot content. Root cause: I had created a duplicate inheritance mechanism instead of using the existing sophisticated one in `compiler/inheritance.py`.

## The Mistakes Made

### 1. Created Duplicate Inheritance Configuration

**What I Did:**
Added `inherits_from: [ragbot]` to each client's `compile-config.yaml`:
```yaml
# WRONG - ai-knowledge-mcclatchy/compile-config.yaml
project:
  name: mcclatchy
  inherits_from: [ragbot]  # <-- This was wrong
```

**Why It Was Wrong:**
- ADR-006 specifies inheritance ONLY lives in personal repo's `my-projects.yaml`
- Putting inheritance in shared repos would reveal private repo existence
- Flattened the inheritance tree (lost rajiv → flatiron → client chain)
- scalepost incorrectly would get flatiron content

**The Existing System:**
```yaml
# CORRECT - ai-knowledge-rajiv/my-projects.yaml (centralized)
projects:
  ragbot:
    inherits_from: []  # Public root
  rajiv:
    inherits_from: [ragbot]
  flatiron:
    inherits_from: [rajiv]
  mcclatchy:
    inherits_from: [flatiron]  # Multi-level chain preserved
  scalepost:
    inherits_from: [rajiv]  # NOT flatiron - intentional
```

### 2. Hardcoded Personal Repo Name

**What I Did:**
When fixing the first mistake, I hardcoded the user's workspace name:
```python
# WRONG
user_workspace = get_user_config('user_workspace', 'rajiv')  # Hardcoded!
```

**Why It Was Wrong:**
- Makes the tool unusable for anyone not named "rajiv"
- Every new user would need to edit source code
- Violates basic software engineering principles

**The Existing System:**
The user config at `~/.config/ragbot/config.yaml` already defines:
```yaml
default_workspace: rajiv  # User-configured, not hardcoded
```

### 3. Created Hack Instead of Using Existing Function

**What I Did:**
Created `discover_personal_repo()` to search for `my-projects.yaml`:
```python
# WRONG - unnecessary hack
def discover_personal_repo(base_path):
    for item in os.listdir(base_path):
        if item.startswith('ai-knowledge-'):
            # Search every repo for my-projects.yaml
```

**Why It Was Wrong:**
- `keystore.py` already has `get_default_workspace()` which reads user config
- The proper mechanism was documented and tested
- My "fix" ignored the existing solution

**The Existing System:**
```python
# CORRECT - in keystore.py
def get_default_workspace() -> Optional[str]:
    """Get the user's default workspace from config."""
    config = _load_user_config()  # Reads ~/.config/ragbot/config.yaml
    return config.get("default_workspace")
```

## Key Lessons

### 1. Read Documentation Before Implementing

I should have read:
- `projects/completed/ai-knowledge-architecture/decisions.md` (ADR-006)
- `src/ragbot/keystore.py` (user configuration system)
- `src/compiler/inheritance.py` (existing inheritance resolver)

**Lesson:** When working on a complex system, spend time understanding existing architecture before making changes.

### 2. Don't Create Duplicate Mechanisms

The inheritance system already existed and was sophisticated:
- Multi-level inheritance chains
- Privacy-preserving (centralized in personal repo)
- Well-tested

**Lesson:** Before implementing something "new," search for existing solutions. If they exist, use them.

### 3. Never Hardcode User-Specific Values

Any value that varies between users (names, paths, preferences) should come from configuration, not source code.

**Lesson:** If you find yourself typing someone's name as a default, stop and use configuration.

### 4. ADRs Exist for Good Reasons

ADR-006 specified centralized inheritance to prevent data leaks:
- Shared repos shouldn't reveal private repo names
- Only the personal repo knows the full inheritance tree

**Lesson:** Architectural Decision Records capture important constraints. Violating them often introduces bugs or security issues.

## Correct Implementation

The fix uses existing systems properly:

1. **Inheritance** from `my-projects.yaml` via `compiler/inheritance.py`:
```python
from compiler.inheritance import load_inheritance_config, find_inheritance_config

inheritance_config_path = find_inheritance_config(personal_repo_path)
inheritance_config = load_inheritance_config(inheritance_config_path)
```

2. **Personal repo** from user config via `keystore.py`:
```python
from ragbot.keystore import get_default_workspace

default_workspace = get_default_workspace()  # e.g., "rajiv"
personal_repo_path = os.path.join(base_path, f'ai-knowledge-{default_workspace}')
```

## Verification

After fix:
- All 8 workspaces show correct inheritance chains
- Vector indices rebuilt with inherited content (mcclatchy: 705 chunks vs ~70)
- Queries about "ragbot" in mcclatchy return correct results

## Related Documents

- [RAG Relevance Improvements README](../active/rag-relevance-improvements/README.md)
- [AI Knowledge Architecture Decisions](../../../ai-knowledge-rajiv/projects/completed/ai-knowledge-architecture/decisions.md)
- [keystore.py](../../../ragbot/src/ragbot/keystore.py)
- [workspaces.py](../../../ragbot/src/ragbot/workspaces.py)
