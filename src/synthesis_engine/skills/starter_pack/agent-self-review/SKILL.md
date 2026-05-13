---
name: agent-self-review
description: "Score the agent's previous turn against an explicit rubric covering groundedness, completeness, safety, and format. Surface failures the agent can fix before the user has to flag them. Use when asked to: self review, audit your response, check your previous answer, score this turn, was that grounded, did you cover everything, post-response review."
license: "CC0-1.0"
scope: universal
depends_on: []
metadata:
  author: "Synthesis Engineering"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/ragbot"
  source_type: "starter_pack"
rubric:
  description: "Four orthogonal dimensions. Each scores PASS / WARNING / FAIL with a one-line rationale. A FAIL on any dimension means the previous turn ships only after the agent has addressed the failure."
  items:
    - id: groundedness
      label: "Groundedness"
      check: "Every factual claim the previous turn made is either traceable to a workspace document via citation, traceable to the user's own input, or labeled as model knowledge with appropriate hedging. No invented sources, no invented numbers, no invented quotes."
      failure_signal: "An unattributed assertion of fact about an external system, a named person's stated position, or a specific quantitative figure."
    - id: completeness
      label: "Completeness"
      check: "The previous turn addresses every sub-question and every deliverable the user asked for. When the user listed N items, the response addresses N items, not N-1. Implicit asks (a constraint stated in the same message, a follow-up implied by the framing) are addressed as well."
      failure_signal: "A list item from the user's request that has no corresponding section, action, or answer in the response."
    - id: safety
      label: "Safety"
      check: "The previous turn does not violate the user's stated constraints, does not bypass guardrails (no-secrets-in-public-repos, no-send-as-user, etc.), and does not expose confidential information. Sensitive operations (deploys, destructive git operations, sends-on-behalf) have explicit user authorization in this turn or a prior one."
      failure_signal: "A confidential name in a public-repo commit message; a slack_send_message call where a draft was the policy; a destructive command run without explicit authorization; a forbidden phrase from the operator's voice rules."
    - id: format
      label: "Format and rules"
      check: "The previous turn follows the operator's stated format rules: full absolute paths in chat hyperlinks, hyperlinks rendered as markdown not plain text, the requested output structure (sections, ordering, length), and any project-specific conventions in CLAUDE.md or the active skill's frontmatter."
      failure_signal: "A relative path or tilde-prefixed path in a chat link; a missing required section; a violated length cap; a forbidden costume phrase in a draft analysis."
---

# Agent Self-Review

The agent's most useful audit is the one it runs on itself before the user has to. This skill makes that audit explicit: a four-dimension rubric the agent applies to its own previous turn, with a verdict per dimension and a rewrite path when any dimension fails.

The skill exists because agents are blind to their own failure modes in proportion to how subtle the failure mode is. A confident-sounding paragraph with two unattributed figures looks fine on first glance; the rubric forces the second glance. A response that addressed four of five user requests reads complete; the rubric counts the requests and catches the missing one. A draft that uses a forbidden phrase from the operator's voice rules sounds fine in isolation; the rubric scans against the rules and catches it.

The rubric is in the frontmatter. Four items: groundedness, completeness, safety, format. Each scores PASS, WARNING, or FAIL with a one-line rationale.

## When to Apply

- Immediately before sending a response to the user on any non-trivial turn (a deliberate pre-send hook).
- When the user asks "did you cover everything?" or "review your last answer."
- After completing a multi-step task (implementation, summary, draft, audit) and before declaring it done.
- When the agent itself suspects a previous turn fell short and wants to verify before the user notices.

## When NOT to Apply

- Trivial one-line responses (acknowledgments, confirmations). The rubric overhead exceeds the response.
- The previous turn was a clarifying question, not a deliverable; there is nothing to score.
- The user has already corrected the previous turn and is moving on. Re-scoring after the user's correction is a waste of attention.

## Protocol

The skill runs in four phases. The first three score the rubric; the fourth produces output and, when warranted, triggers a rewrite.

### 1. Re-read the previous turn

Read the response the agent produced in full. Not a summary of it, not a paraphrase of it — the actual text. Self-review fails most often when the agent scores its intention instead of its output.

When the previous turn was code (a diff, a file write), read the file or the diff. When the previous turn included a tool call (slack_send_message, gh pr create, deploy), include the tool call and its arguments in the re-read.

### 2. Apply each rubric item in order

For each of groundedness, completeness, safety, format:

- Read the item's `check` field from the rubric.
- Identify the property the check requires.
- Scan the previous turn for evidence the property holds.
- Score: PASS, WARNING, or FAIL.
- Write one line of rationale.

PASS means the property holds. WARNING means the property holds with caveats the user should know about. FAIL means the property does not hold; the turn needs revision before it ships.

The dimensions are orthogonal. A response can be perfectly grounded and incomplete; perfectly complete and unsafe; perfectly safe and badly formatted. Scoring them together blurs which axis failed.

### 3. Synthesize the verdict

Roll the four item scores into an overall verdict using these rules:

- All four PASS → overall PASS.
- Any FAIL → overall FAIL.
- Otherwise → overall WARNING.

The overall verdict drives the next action. FAIL triggers a rewrite. WARNING surfaces the caveat in the response without blocking. PASS ships.

### 4. Act on the verdict

**PASS.** Ship the previous turn as-is. The self-review is internal; do not surface the rubric in the response unless the user has explicitly asked for it.

**WARNING.** Surface the caveat. A one-line note appended to the response: "Caveat: [the rubric item] [why it's a warning]." The user can decide whether the caveat matters. The response still ships.

**FAIL.** Do not ship. Rewrite the failing span. The rewrite addresses only the failed dimension; the agent does not also try to optimize the other dimensions in the same edit (cross-dimension edits introduce regressions). After the rewrite, re-run the rubric on the rewritten span. Repeat until the dimension passes.

There is a stopping condition: after three rewrite cycles on the same dimension, the agent surfaces the failure to the user with the best-effort version, rather than looping further. "I was unable to resolve [dimension] within three rewrite attempts. The remaining issue is [description]. Sending the best-effort version for your judgement."

## The Four Dimensions in Detail

The rubric items each catch a distinct failure mode. The agent should internalize the failure signal for each, listed in the frontmatter's `failure_signal` field, so the scan is fast.

**Groundedness** catches confabulation. The failure signal is an unattributed claim that sounds like it should have a source — a number, a quote, a named person's position, a date. When the agent finds one, the fix is to add the citation, label it as model knowledge with hedging, or remove the claim.

**Completeness** catches partial coverage. The failure signal is a user-listed item with no corresponding response. The fix is to add the missing item, not to argue it was implied; if the user listed it, the response addresses it explicitly.

**Safety** catches violated constraints. The failure signal is the operator's specific rules: forbidden phrases in drafts, confidential names in public repos, send-on-behalf calls where drafts were policy, destructive commands without authorization. The fix is to rewrite the unsafe span; in extreme cases (a sent slack message that should have been a draft) the fix is to surface the violation rather than silently moving on.

**Format** catches rule violations on output shape. The failure signal is a path that is not absolute, a markdown link rendered as plain text, a section that was supposed to be present and was not, a length cap exceeded. The fix is mechanical: rewrite to the format the rules require.

## Output Format

When the verdict is PASS, the response is the previous turn unchanged. No rubric appears.

When the verdict is WARNING, the response is the previous turn with a one-line caveat appended:

```
Caveat (format): The hyperlink on line 3 used a tilde path. Replaced with absolute path.
```

When the verdict is FAIL, the response is the rewritten previous turn. The agent does not show the user the broken version; the user sees the fixed deliverable. When the user has explicitly asked for the self-review report, the agent appends a structured report:

```
## Self-Review

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Groundedness | PASS | All three figures cited. |
| Completeness | PASS | All five list items addressed. |
| Safety | FAIL | Forbidden phrase "for now" in P3. Rewrote to commit to the decision. |
| Format | PASS | Headings and length within spec. |

Overall: FAIL → rewrote P3.
```

## Anti-patterns the Skill Catches

**Self-review as flattery.** The rubric is not a place to say "the response was clear and useful." The rubric is a place to find what is wrong. An all-PASS self-review on a non-trivial turn is a signal the agent did not look hard enough; the rubric should produce real findings most of the time on real work.

**Surface-only scoring.** Reading the response for vibes and scoring PASS on all four dimensions because nothing feels off. The check fields are concrete; the agent applies the concrete check, not the vibes check.

**Rewrites that drift.** An agent asked to fix a groundedness FAIL rewrites the whole paragraph and inadvertently breaks the completeness PASS. The rewrite is scoped to the failed dimension; cross-dimension edits go through a fresh re-review.

**Hiding the failure.** When the rewrite cannot fully resolve a dimension within three attempts, the response surfaces the residual issue. Shipping a silent best-effort is worse than naming the gap.

## Relationship to Other Starter Pack Skills

- `workspace-search-with-citations` is the retrieval engine the groundedness dimension uses to verify citations point to real chunks.
- `fact-check-claims` is the deeper version of the groundedness check; self-review's check is the fast first pass, fact-check-claims is the thorough audit on high-stakes turns.
- `draft-and-revise` shares the rubric pattern; this skill's rubric runs on the agent's whole turn, the draft-and-revise rubric runs on a specific drafted artifact.
- `summarize-document` is one possible deliverable type; the format dimension checks that summarize-document outputs match the three-section contract.

The five starter skills form a working set. Retrieve evidence, draft with a rubric, fact-check the result, summarize when condensation helps, and self-review the whole turn before it ships.
