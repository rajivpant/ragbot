---
name: summarize-document
description: "Produce a multi-style summary of a document: an executive summary for skim readers, a key-points list for reference, and an action-items list for owners. Three output sections in a fixed structured format. Use when asked to: summarize, tldr, give me the key points, what does this say, executive summary, action items from, condense, distill."
license: "CC0-1.0"
scope: universal
depends_on: []
metadata:
  author: "Synthesis Engineering"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/ragbot"
  source_type: "starter_pack"
output_sections:
  - id: executive_summary
    label: "Executive Summary"
    purpose: "A single paragraph (60-120 words) that a senior reader can absorb in 30 seconds and walk away with the document's thesis, the supporting argument's shape, and the most consequential conclusion."
    constraints:
      - "One paragraph; no bullet points."
      - "Lead with the thesis or the question the document answers; do not open with meta-commentary about what the document is."
      - "Name the most consequential conclusion or recommendation; do not bury it."
  - id: key_points
    label: "Key Points"
    purpose: "A bulleted list of 5-9 substantive claims, decisions, or findings. Each bullet is a sentence the reader can paraphrase back to a colleague without re-reading the document."
    constraints:
      - "5-9 bullets. Fewer than 5 means the summary is hiding detail; more than 9 means the bullets are duplicating each other."
      - "Each bullet is one sentence, complete, declarative."
      - "Order matters: most important first, scaffolding context after."
  - id: action_items
    label: "Action Items"
    purpose: "Owner-tagged tasks or decisions the document explicitly assigns or implies. Empty if the document has none — do not invent action items to fill the section."
    constraints:
      - "Each item has the form '[Owner] - [Action] - [Deadline or trigger if stated]'."
      - "Use 'Owner: unspecified' when the document implies a task without naming an owner."
      - "Use 'None' when the document is purely informational. Do not pad."
---

# Summarize Document

A summary is not a shorter version of a document; it is a different artifact with a different purpose. The original carries the full argument with its evidence; the summary carries enough of the conclusion that a reader can decide whether to read the original. This skill produces summaries that respect that distinction, in three formats that serve three audiences in one pass.

Readers do not all want the same shape. An executive wants a paragraph and moves on. A practitioner wants a list of points they can act on. A project manager wants a list of tasks with owners. A document that gets only one of these formats serves only one audience well. The skill produces all three.

## When to Apply

- The user asks for a summary, TL;DR, executive summary, or key points of a document.
- The user pastes a long document or transcript and asks "what does this say."
- A workspace document has been retrieved and the user wants a quick read before deciding whether to open it.
- A meeting transcript or status report needs to be reduced to action items.

## When NOT to Apply

- The document is shorter than the summary would be (under ~300 words). The model offers to read the original aloud or paraphrase it inline; a three-section summary is overkill.
- The user asks "explain this," which is a different operation (paraphrase and clarify, not condense).
- The user asks for a critical review or fact-check; those are `agent-self-review` and `fact-check-claims`, respectively.

## Protocol

The skill is single-pass over the document, with one explicit re-read before publishing. The re-read catches the failure modes summaries fall into.

### 1. Read the document end to end

Read the whole document before composing any section. Skimming and summarizing in parallel is the dominant failure mode here — the model writes a summary of the first half and silently truncates whatever the second half added.

For very long documents, the model uses a windowed pass: read in chunks of roughly 8-12 thousand tokens, note the thesis and key claims from each window, then assemble. The windowed pass should produce the same output as a single-pass read; it is the same work in a different shape.

### 2. Identify the thesis

Most documents have one. It is the sentence (or two) that answers "what is this document for." It usually sits in the first paragraph or the last paragraph, sometimes both. The thesis becomes the lead of the executive summary.

If the document does not have a single thesis (it is a survey, a transcript, a digest), the model says so in the executive summary: "This document is a status update covering three projects. The most consequential change is X." Naming the document type up front avoids forcing a false thesis.

### 3. Compose each section in the fixed order

**Executive summary.** One paragraph, 60-120 words. Lead with the thesis. Develop the argument's shape in two or three sentences. Close with the most consequential conclusion or recommendation. No meta-commentary ("This document discusses..."); start with the substance.

**Key points.** 5-9 bullets. Each is a complete declarative sentence. Order them by importance, not by position in the document. Avoid bullets that are paraphrases of other bullets; if two bullets converge, merge them.

**Action items.** Pull explicit assignments and clear implications. Format: `[Owner] - [Action] - [Deadline or trigger]`. When the owner is unstated but the action is clear, use `Owner: unspecified`. When the document is purely informational, write `None`. Do not invent action items to fill space.

### 4. Re-read and tighten

Read the three sections back. Check:

- Does the executive summary's lead match the thesis? If the lead is meta-commentary, rewrite it.
- Does each key-points bullet contain new information? If a bullet repeats the executive summary verbatim, replace it with the next-most-important claim.
- Are the action items genuine? Strip anything the document does not actually assign or imply.
- Is anything missing? If a major argument in the document is not represented in either section, add a bullet for it.

The re-read is fast (seconds) and catches the failures that bare composition does not.

## Output Format

Fixed structure. Always these three sections, in this order, with these headings:

```
## Executive Summary
[paragraph]

## Key Points
- [bullet 1]
- [bullet 2]
- ...

## Action Items
- [Owner] - [Action] - [Deadline or trigger]
- ...
```

When the document has no action items, the section reads:

```
## Action Items
None.
```

Do not skip the section. Its presence with "None" is informative; its absence is not.

## Substyle Customization

Users can override the default styles by asking. The model accepts these patterns:

- "Just the TL;DR" → output only the executive summary.
- "Just the action items" → output only the action items section.
- "Bullet summary" → output only the key-points section.
- "Detailed summary" → expand the key-points section to 9-12 bullets and the executive summary to 150-200 words.
- "One-sentence summary" → output a single sentence; ignore the structured format.

The default — all three sections — is what runs when the user does not specify.

## Anti-patterns the Skill Catches

**Lead with meta-commentary.** "This document discusses three topics" is throat-clearing. Replace with the substance: "The team is migrating from Qdrant to pgvector for vector storage, on a four-week timeline starting May 1."

**Duplicate the original.** A summary that contains the same examples and the same caveats as the document is the document, not its summary. Cut examples unless they are the load-bearing part of the argument.

**Inflate the action items.** A status update that has no assigned actions does not get fake action items "to be useful." Empty is empty. The user knows what to do with that.

**Hide the conclusion.** The executive summary that ends "...with several open questions remaining" is hiding the conclusion. If the document concludes, the summary states the conclusion. If the document genuinely leaves open questions, name them.

**Lose the numbers.** A summary that drops the specific figures (dates, counts, percentages, names) is harder to act on. The first re-read pass restores any figure the document treated as load-bearing.

## Edge Cases

**Multi-document inputs.** When the user pastes two or more documents and asks for one summary, the model produces a single set of three sections that covers all of them. The executive summary names how many documents and what their relationship is.

**Conversation transcripts.** Each speaker's contributions roll up into the key points. Action items come from explicit assignments in the transcript; the speaker becomes the owner unless otherwise stated.

**Code-heavy documents.** Code snippets are not summarized line by line. The summary captures what the code does, the API or interface it exposes, and any non-obvious behavior. Lines of code go into the key points only when the line itself is the thing the reader needs to remember.

**Highly structured documents** (specs, runbooks, decision records). The thesis is usually the document's title or first heading. The key points map to the document's existing sections, one bullet per section, expressing the section's load-bearing claim.

## Relationship to Other Starter Pack Skills

- `workspace-search-with-citations` provides the document content when the user asks for a summary of a document already in the workspace.
- `fact-check-claims` audits this skill's summary against the source document when the user wants verification that the summary tracks the original.
- `agent-self-review` checks that the summary meets its format contract (three sections, in order, action items present or `None`).
