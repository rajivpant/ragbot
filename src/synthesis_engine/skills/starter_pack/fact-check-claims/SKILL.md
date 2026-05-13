---
name: fact-check-claims
description: "Extract factual claims from a text, retrieve supporting context for each, and assign a verdict of supported, contradicted, or unknown. Use when asked to: fact check, verify claims, check accuracy, audit for errors, validate the assertions, ground-truth the draft, find unsupported claims."
license: "Apache-2.0"
scope: universal
depends_on: []
metadata:
  author: "Synthesis Engineering"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/ragbot"
  source_type: "starter_pack"
tools:
  - name: claim_check
    description: "Retrieve supporting or contradicting evidence for a single claim from the active workspace's memory. Returns top hits with similarity scores and the surrounding chunk text. The model interprets the hits and assigns the verdict; the tool does not assign the verdict itself."
    input_schema:
      type: object
      properties:
        claim:
          type: string
          description: "A single atomic factual claim. Compound claims should be split before calling; the tool is not responsible for decomposition."
        k:
          type: integer
          description: "Maximum number of evidence chunks to return. Defaults to 6, which is the floor for confident triangulation when sources disagree."
          default: 6
          minimum: 1
          maximum: 20
      required:
        - claim
    output_schema:
      type: object
      properties:
        evidence:
          type: array
          items:
            type: object
            properties:
              document_id:
                type: string
              char_range:
                type: array
                items:
                  type: integer
              text:
                type: string
              score:
                type: number
              source_workspace:
                type: string
            required:
              - document_id
              - char_range
              - text
              - score
      required:
        - evidence
verdicts:
  - id: supported
    label: "Supported"
    meaning: "At least one retrieved chunk directly affirms the claim, and no retrieved chunk contradicts it. The supporting text is unambiguous."
  - id: contradicted
    label: "Contradicted"
    meaning: "At least one retrieved chunk directly contradicts the claim. A claim is contradicted even when other chunks weakly support it; surface the conflict in the report."
  - id: unknown
    label: "Unknown"
    meaning: "Retrieval returned no chunks, or the retrieved chunks are off-topic or too ambiguous to decide. The workspace does not have a confident position."
---

# Fact-Check Claims

This skill takes a text — a draft, a summary, a transcript, an article — and audits every factual claim it contains against the workspace's memory. Each claim gets a verdict (supported, contradicted, unknown) and the evidence behind that verdict. The output is a structured report the user can act on: ship the supported claims, fix the contradicted ones, decide what to do with the unknowns.

The skill exists because models confabulate, and confabulation is hardest to catch in your own draft. A separate fact-check pass uses the retriever as an external memory check — claims that survive the pass are claims the workspace can corroborate; claims that fail it are claims that need a citation, a correction, or a deletion.

## When to Apply

- A draft is going to be published or sent to someone who will treat it as authoritative.
- A summary was generated and the user wants to verify it tracks the source.
- The user explicitly asks: "fact-check this," "verify these claims," "what here is wrong."
- A prior turn's response is being audited (the self-review skill calls into this one for the groundedness rubric item).

## When NOT to Apply

- The text is opinion, prediction, or rhetoric. Claims about the future and about the author's stance are not subject to retrieval-based fact-check. The model says so and skips them.
- The text is fiction or creative writing where factual accuracy is not the contract.
- The user wants stylistic editing — that is `draft-and-revise`, not this skill.

## Protocol

The skill is a four-stage pipeline. Each stage produces a typed artifact the next stage consumes. The pipeline is sequential because verdicts depend on evidence and evidence depends on which claims were extracted.

### Stage 1: Extract atomic claims

Read the input text. Identify every assertion of fact. Split compound claims into atomic ones. "The staging deployment uses Cloud Run with Anthropic's Claude Sonnet 4.6 model" is three claims:

1. Staging is deployed on Cloud Run.
2. Staging uses Anthropic's Claude.
3. The Claude model in staging is Sonnet 4.6.

Atomicity matters because verdicts are per-claim. A compound claim that is partly right and partly wrong gets a misleading single verdict; splitting forces the truth to come out.

Exclude:

- Opinion statements ("the design is elegant").
- Hedged statements ("the model might be Sonnet 4.6"). Hedges are flagged for the user to either commit to or remove, but they are not subject to the verdict pass.
- Tautologies and definitions.
- The user's own stated preferences ("I want the email to be informal").

### Stage 2: Retrieve evidence per claim

For each atomic claim, call `claim_check(claim)` with `k=6` by default. The retriever returns up to six chunks ranked by similarity. The model reads each chunk.

When the top score is below 0.3 and no chunk appears to address the claim, the evidence base is too weak to issue a verdict; the verdict will be `unknown`. The model does not invent supporting evidence from training.

When the top score is high but the chunk is on a related but distinct topic (the document mentions Claude Sonnet 4.6 but in a different deployment context), the model marks it as weak evidence in the report and the verdict is `unknown` unless a different chunk lands directly.

### Stage 3: Assign verdicts

Three verdicts, defined in the frontmatter:

- **supported** — at least one chunk directly affirms the claim, and no chunk contradicts it.
- **contradicted** — at least one chunk directly contradicts the claim. The verdict is `contradicted` even when other chunks weakly support it; surface the conflict in the report.
- **unknown** — retrieval returned nothing useful, or the chunks are ambiguous.

Verdicts are conservative. When the model is unsure between `supported` and `unknown`, the verdict is `unknown`. The cost of an over-confident `supported` is a false-positive that the user does not catch; the cost of a conservative `unknown` is a re-check the user can do quickly.

### Stage 4: Produce the report

The report is a structured list. One entry per claim. Each entry has:

- The claim, verbatim or lightly paraphrased.
- The verdict.
- The supporting or contradicting evidence with document identifier and character range.
- A one-line rationale when the verdict is not obvious from the evidence.

Example format:

```
Claim: The Claude model in staging is Sonnet 4.6.
Verdict: contradicted
Evidence:
  - deploy-config.yaml [142-167]: "model: claude-opus-4.7"
  - release-notes.md [88-95]: "Staging upgraded to Opus 4.7 on 2026-04-22."
Rationale: Two independent sources show Opus 4.7, not Sonnet 4.6.
```

When the user wants a compact rollup, append a summary line:

```
Summary: 4 claims supported, 1 contradicted, 2 unknown. Top issue: model version (see claim 3).
```

## Chain of Thought the Model Should Follow

The verdict assignment is not mechanical. The model reads each chunk and decides whether it speaks to the claim. The reasoning should follow a short, repeatable pattern that the model applies to every claim — not just the easy ones.

1. **Re-read the claim.** What exactly is being asserted? Is the subject the same as the subject in the chunk? Is the temporal frame the same?
2. **Read the top hit.** Does it directly address the claim? If yes, is it support or contradiction?
3. **Scan the remaining hits.** Do any contradict the top hit? If yes, the verdict is `contradicted` until the conflict is resolved by a third source.
4. **Check for stale evidence.** If the chunk is dated and the claim is about the current state, note the date in the rationale.
5. **Issue the verdict.** Default to `unknown` when in doubt. The user can re-check; the model cannot un-publish a false `supported`.

## Edge Cases

**Numerical claims.** Verdicts hinge on exact figures. A chunk that says "deployed in early April" does not support a claim of "deployed April 2, 2026" — the chunk is too coarse. Mark this as `unknown` and surface the imprecision.

**Names and identifiers.** A claim that "the project lead is X" requires a chunk that names X in that role. A chunk that mentions X in passing does not support the claim. The model is precise here because names are where confident hallucinations are most damaging.

**Negations.** "The system does not use OAuth" is supported by a chunk that lists authentication methods and OAuth is absent — but only if the chunk is plausibly comprehensive. A passing-mention chunk does not support a negation. Mark as `unknown` if the chunk does not establish that the list was exhaustive.

**Self-referential claims.** A claim about the source workspace itself ("the workspace has 142 documents") is checkable by counting, not by retrieval; flag for the user that the answer requires a different tool.

## Output Format

Default output is the structured report from Stage 4. When the user is iterating ("just the failures"), the model returns only the contradicted and unknown entries. The summary line always appears at the top of the response so the user can scan and decide where to dig in.

## Relationship to Other Starter Pack Skills

- `workspace-search-with-citations` is the retrieval engine; `claim_check` shares the same underlying memory but presents the hits per-claim.
- `draft-and-revise` produces the text this skill audits. A draft that fails fact-check goes back to revision with the failed claims as inputs.
- `agent-self-review` invokes this skill on its own previous turn as part of the groundedness rubric item.
