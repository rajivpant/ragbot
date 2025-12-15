# 2025-12-14: Fix Instruction Runbook References

**Project:** AI Knowledge Compiler
**Focus:** Fix broken runbook filename references in instructions

## Problem Identified

The `default.md` instructions file referenced runbook filenames that didn't exist:

| Referenced | Actual File |
|------------|-------------|
| `voice-and-style/persona.md` | `voice-and-style/thought-leadership-writing-guidelines.md` |

This caused:
- Instructions pointed to non-existent files
- AI assistants couldn't find the referenced runbooks
- Writing style guidelines weren't being applied

## Solution

1. **Fixed filename references** in `ai-knowledge-rajiv/source/instructions/default.md`:
   - Changed `persona.md` to `thought-leadership-writing-guidelines.md`
   - Added missing runbooks: `message-condensation.md`, `article-publishing.md`, `content-promotion-voice.md`

2. **Added AI patterns reminder** for all writing tasks:
   - Reference to "Guide to Identifying and Improving AI-Assisted Content"
   - Located in `datasets/guides/` (in ai-knowledge-ragbot, inherited)

## Updated Runbook Table

```markdown
| Task | Runbook |
|------|---------|
| Writing voice and style | `voice-and-style/thought-leadership-writing-guidelines.md` |
| Message brevity | `voice-and-style/message-condensation.md` |
| Social media posts | `content-creation/social-media.md` |
| Blog/article writing | `content-creation/thought-leadership.md` |
| Author bios | `content-creation/author-bios.md` |
| Article publishing | `content-creation/article-publishing.md` |
| Content promotion | `content-creation/content-promotion-voice.md` |
| Blog revitalization | `content-enhancement/blog-revitalization.md` |
| LinkedIn engagement | `automation/linkedin-engagement.md` |
| Birthday messages | `automation/facebook-birthday.md` |
```

## Design Consideration

**Open question:** How should compiled instructions reference runbooks?

Current approach: Instructions reference source filenames. After compilation, these paths may not be valid if runbooks are concatenated.

Possible solutions:
1. **Keep source paths** - RAG retrieval finds content by semantic search anyway
2. **Replace with topic tags** - "For writing style, see the thought leadership guidelines"
3. **Inline critical rules** - Put must-apply rules directly in compiled instructions
4. **Compiler transformation** - Compiler rewrites paths to compiled locations

For now, kept source paths since RAG retrieval doesn't depend on exact filenames.

## Related

- [AI Knowledge Architecture](https://github.com/rajivpant/ai-knowledge-rajiv/tree/main/projects/active/ai-knowledge-architecture)
- Inheritance fix (same session) - created `my-projects.yaml`
