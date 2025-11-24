# RaGenie Resources

This folder contains utilities, guides, and templates that ship with RaGenie.

## Purpose

These resources are:
- ✅ Part of the open-source RaGenie distribution
- ✅ Available to all users out of the box
- ✅ Usable standalone in other projects
- ✅ Publicly accessible on GitHub

These are NOT:
- ❌ User's private data (that's mounted via `RAGBOT_DATA_PATH`)
- ❌ Auto-indexed for RAG (user data is indexed, product resources are reference material)
- ❌ Specific to any individual user

## Contents

- **`guides/`** - User guides and best practices
  - `writing/` - Writing-related guides
- **`workflows/`** - Pre-built LangGraph workflow definitions (coming soon)
- **`templates/`** - Configuration templates (coming soon)

## Usage in Containers

These resources are available at `/data/resources/` in all RaGenie service containers.

Example: A user can reference these resources in their custom instructions:
```
"When helping me identify AI-generated content, refer to the guide in
/data/resources/guides/writing/Guide_to_Identifying_AI-Generated_Content_v2.md"
```

## Usage Standalone

These resources can be copied and used in other projects without the rest of RaGenie:

```bash
# Copy a guide to your project
cp resources/guides/writing/*.md /your-project/docs/

# Use workflows in your own LangGraph project
cp resources/workflows/*.json /your-project/workflows/
```

## Architecture

### Product Resources vs User Data

**Product Resources** (this folder):
- Location: Part of ragenie repository (`./resources/`)
- Access: Available at `/data/resources/` in containers
- Indexing: NO - Static reference material
- Distribution: Ships with every RaGenie installation
- Git: Public repo

**User Data** (separate):
- Location: User's filesystem, mounted via `RAGBOT_DATA_PATH`
- Access: Available at `/data/user-data/` in containers
- Indexing: YES - File watcher monitors and embeds for RAG
- Distribution: NOT shipped, user provides their own
- Git: Private repo (if any)

## Contributing

To add new resources:

1. Place files in the appropriate subdirectory
2. Update this README with the new resource
3. If adding a guide, update `guides/README.md`
4. Submit a pull request

All contributions must be suitable for public distribution and not contain any private/confidential information.

---

**Note**: This folder structure is mirrored in the ragbot repository for backward compatibility with Ragbot v1.
