---
name: draft-and-revise
description: "Produce a first draft, then revise it against a rubric until each rubric item is satisfied. Two-stage prompt that separates generation from criticism so each gets full attention. Use when asked to: draft, write, compose, revise, improve a draft, iterate on writing, refine, polish, edit my draft, rewrite, second pass."
license: "CC0-1.0"
scope: universal
depends_on: []
metadata:
  author: "Synthesis Engineering"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/ragbot"
  source_type: "starter_pack"
rubric:
  description: "Default revision rubric. The user can override any item by stating an explicit criterion in the request; the model checks the override list first."
  items:
    - id: clarity
      label: "Clarity"
      check: "A reader who is new to the topic can follow the argument on first read. Each paragraph has one main idea. No ambiguous pronouns; no jargon left undefined."
    - id: structure
      label: "Structure"
      check: "The piece opens with the thesis or the question, develops the argument in a logical sequence, and ends with the conclusion or the call to action. Section breaks land at natural seams, not arbitrary points."
    - id: evidence
      label: "Evidence and specificity"
      check: "Claims are supported by specific examples, numbers, quotes, or named cases. Abstract claims that lack a concrete example are flagged. Where applicable, citations point to sources."
    - id: voice
      label: "Voice and register"
      check: "The tone matches the audience and the channel. No throat-clearing, no hedging by default, no filler phrases (\"it is worth noting,\" \"in many ways,\" \"various aspects\"). First person when the channel allows; third person otherwise."
    - id: length
      label: "Length discipline"
      check: "The draft is no longer than the topic requires. Repetition, scaffolding sentences, and meta-commentary about what the draft is about to do are removed."
    - id: closing
      label: "Closing strength"
      check: "The final paragraph or line carries weight. It does not summarize what was already said; it concludes, recommends, or asks the reader to do something."
---

# Draft and Revise

Most drafts get one pass: the model writes, the user receives, the user lives with whatever shape the first attempt produced. The result is competent prose that does not get better between turn 1 and turn 10 because the model is not given the affordance to criticize itself.

This skill builds that affordance into the protocol. Draft and revise are two distinct cognitive moves; doing them in one breath blurs them both. The skill splits them: draft once with full attention on generation, then revise with full attention on the rubric. The two phases use different mental modes — generative open-ended writing in the first, narrow checklist-driven editing in the second — and separating them lets each one work at full strength.

## When to Apply

- The user asks for a draft of any prose artifact (email, message, blog post, memo, README, design doc, PR description, summary, response).
- The user asks for a revision of a draft they already have.
- The user explicitly asks for iteration: "draft this, then improve it," "give me a v1 and a v2," "show me your edits."
- The output is going to be read by someone other than the model; quality is non-trivial.

## When NOT to Apply

- The user asks for a one-shot reply to a simple question (small talk, factual lookup, single-line confirmation).
- The user asks for code; the code-planning and implementation skills are the right tools.
- The artifact is so short (one sentence, one line) that there is no meaningful revision dimension.

## Protocol

The skill is a two-phase loop with an explicit handoff between the phases. The phases use different framings so the model engages the right mode for each.

### Phase 1: Draft

Write the first version. The mode is generative: get the argument on the page, get the structure roughly right, get the voice in the right register. Do not stop to second-guess word choice. Do not insert hedges. Do not pre-criticize the draft mid-sentence.

The draft phase is allowed to overshoot in length. It is easier to cut than to grow during revision; a draft that is too long is a known shape that revision can compress, while a draft that is too short forces revision to invent material, which is a different and harder task.

The draft is internal output. The user does not see the unrevised draft unless the protocol is interrupted (timeout, error, user request). The model continues directly to Phase 2 in the same response.

### Phase 2: Revise

Switch modes. Read the draft as if a stranger wrote it. Apply the rubric in order; for each item, find the place in the draft where the item is unsatisfied, name the failure, and rewrite the offending span.

The rubric is in the frontmatter. The default items are clarity, structure, evidence, voice, length, and closing. The user can override any item by stating an explicit criterion in the request ("keep it under 200 words," "make the tone informal," "open with a question, not a statement"). The user's overrides are checked first; the default items run for everything else.

Revision is not light editing. Revision rewrites. If the closing paragraph repeats the opening, the closing gets replaced, not nudged. If the structure is wrong, paragraphs move. If a section is throat-clearing, the section is cut.

The revised version is what the user sees. The model does not present the draft alongside the revision unless the user has asked for both. Showing both pollutes the deliverable; the user came for the final artifact, not the workshop log.

### Optional: Show the diff

When the user asks "what did you change?" or "show me the revisions," the model summarizes the revision moves in a short list. Format:

```
Revisions applied:
- Clarity: removed two passive constructions in P3; defined "synthesis runtime" inline.
- Structure: moved the example from P5 to P2 so the argument lands earlier.
- Voice: dropped "It is worth noting that" (twice). Tightened P4's tone from advisory to direct.
- Closing: replaced the summary paragraph with a one-line recommendation.
```

This list is a diagnostic, not the deliverable. The deliverable is the revised text.

## How the Rubric Should Be Used

The rubric is a checklist between drafts, not a label dispenser. The model does not annotate the revision with "[CLARITY: improved]" tags. It applies the rubric quietly and ships the rewritten prose.

Each rubric item has a `check` field that names a concrete property of the draft. The model reads the draft and asks: does this property hold? When the answer is no, the model rewrites the offending span until the answer is yes.

When the model cannot improve an item further without losing something the rubric does not measure (voice, intent, the user's stated constraint), the model stops. Over-revising is its own failure mode; the rubric is a floor, not a ceiling.

## Anti-patterns the Skill Catches

The two-phase split exists to defeat several recurring failure modes in single-pass AI writing.

**Throat-clearing.** Single-pass drafts open with "I'll outline the argument and then address the objections" and equivalents. The revise phase deletes these on sight. Open with the argument; the reader does not need a roadmap for a 400-word draft.

**Mid-sentence hedging.** "This may be useful in some cases, depending on context." A revise pass picks one: either the model means it or the model does not. The hedge is replaced with the load-bearing claim, or the sentence is cut.

**Closing repetition.** Single-pass drafts often close by restating the opening. The revise pass replaces summary closings with conclusions, recommendations, or questions. The closing earns its own line.

**Scaffolding stuck in the deliverable.** Phrases like "in this draft I will," "as discussed above," "in summary." These are first-draft scaffolding the writer used to keep their place; they belong in the cut pile, not the published artifact.

**Voice drift.** A single-pass draft can start in one register and end in another (informal opening, formal middle, conversational close). The revise pass picks the register the audience requires and rewrites to fit.

## Output Format

By default, the model returns the revised draft only. No preamble, no postscript, no meta-commentary about the revision process.

When the user has asked for both versions, the model returns them in this order:

```
## Draft (v1)
[first version]

## Revised (v2)
[revised version]
```

When the user has asked for the diff, the model appends a short list of revision moves after the revised text (see Phase 2 above).

## Relationship to Other Starter Pack Skills

- `workspace-search-with-citations` supplies the evidence that the draft cites. Drafts that need workspace facts run the retrieval skill first.
- `fact-check-claims` runs after revision to verify claims that came from training or that the user supplied as inputs.
- `agent-self-review` re-runs the rubric one more time as a final pass and adds the groundedness check.

The three downstream skills can be invoked separately. The user gets the cleanest results when the chain runs end-to-end on a high-stakes artifact.
