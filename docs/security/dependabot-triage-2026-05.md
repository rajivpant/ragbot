# Dependabot Triage — 2026-05 (Ragbot v3.4)

Triage record for the 28 open Dependabot alerts on `synthesisengineering/ragbot` at the start of Phase 5 of the v3.4 release. Phase 0 inventory listed 41 alerts; 13 had already been auto-fixed between Phase 0 and Phase 5 by interim Dependabot PRs that landed.

This document is the source of truth for every classification, pin bump, and ignore decision made during this triage. The `.github/dependabot.yml` and `SECURITY.md` files reference this doc.

## Summary

| Bucket | Count |
| --- | --- |
| Open at triage start | 28 |
| Fixed by pin bump (`next` 16.0.10 to 16.2.6) | 22 |
| Fixed by transitive override (`flatted`, `minimatch`, `picomatch`, `ajv`, `brace-expansion`, `postcss`) | 6 |
| Remaining open after triage | 0 |
| Accepted risk (rationale only, no fix possible) | 0 |

Target was fewer than 10. Final: 0.

## Inventory by package

### `next` — 22 alerts, all resolved by pin bump

| # | Severity | GHSA | CVE | Fixed in | Classification |
| --- | --- | --- | --- | --- | --- |
| 65 | high | GHSA-26hh-7cqf-hhc6 | CVE-2026-45109 | 15.5.18, 16.2.6 | real-exposure |
| 63 | low | GHSA-3g8h-86w9-wvmq | CVE-2026-44572 | 15.5.16 | real-exposure |
| 61 | medium | GHSA-h64f-5h5j-jqjh | CVE-2026-44577 | 15.5.16 | real-exposure |
| 59 | high | GHSA-mg66-mrh9-m8jx | CVE-2026-44579 | 15.5.16 | real-exposure |
| 57 | medium | GHSA-wfc6-r584-vfw7 | CVE-2026-44576 | 15.5.16 | real-exposure |
| 55 | medium | GHSA-ffhc-5mcf-pf4q | CVE-2026-44581 | 15.5.16 | real-exposure |
| 53 | medium | GHSA-gx5p-jg67-6x7h | CVE-2026-44580 | 15.5.16 | real-exposure |
| 51 | low | GHSA-vfv6-92ff-j949 | CVE-2026-44582 | 15.5.16 | real-exposure |
| 49 | high | GHSA-267c-6grr-h53f | CVE-2026-44575 | 15.5.16 | real-exposure |
| 47 | high | GHSA-c4j6-fc7j-m34r | CVE-2026-44578 | 15.5.16 | real-exposure |
| 45 | high | GHSA-492v-c6pp-mqqv | CVE-2026-44574 | 15.5.16 | real-exposure |
| 43 | high | GHSA-36qx-fr4f-26g5 | CVE-2026-44573 | 15.5.16 | real-exposure |
| 41 | high | GHSA-8h8q-6873-q5fj | (no CVE) | 15.5.16 | real-exposure |
| 37 | high | GHSA-q4gf-8mx6-v5v3 | (no CVE) | 15.5.15 | real-exposure |
| 29 | medium | GHSA-3x4c-7xq6-9pq8 | CVE-2026-27980 | 16.1.7 | real-exposure |
| 27 | medium | GHSA-ggv3-7p47-pfv8 | CVE-2026-29057 | 16.1.7 | real-exposure |
| 25 | medium | GHSA-h27x-g6w4-24gq | CVE-2026-27979 | 16.1.7 | real-exposure |
| 23 | medium | GHSA-mq59-m269-xvcx | CVE-2026-27978 | 16.1.7 | real-exposure |
| 21 | low | GHSA-jcc7-9wpm-mj36 | CVE-2026-27977 | 16.1.7 | real-exposure |
| 9 | medium | GHSA-5f7q-jpqc-wp7h | CVE-2025-59472 | 16.1.5 | real-exposure |
| 7 | high | GHSA-h25m-26qc-wcjf | (no CVE) | 15.0.8 | real-exposure |
| 5 | medium | GHSA-9g9p-9gw9-jx7f | CVE-2025-59471 | 15.5.10 | real-exposure |

**Exposure analysis.** `next` is the App Router runtime for `web/` (`web/src/app/**`). All advisories above target either the App Router request pipeline, the Middleware / Proxy layer, the Image Optimization API, Server Components serialization, or PPR/Cache Components. Ragbot's `web/` surface uses App Router, Middleware (via `next.config.ts`), Server Components, and `next/image`, so each advisory is a real exposure on the deployed runtime, not a transitive-only concern.

**Affected import paths in Ragbot's code (sample).**

- `web/src/app/layout.tsx`, `web/src/app/page.tsx` — App Router root pages.
- `web/src/components/Chat.tsx` — uses RSC streaming.
- `web/src/lib/api.ts` — client-side fetcher for the FastAPI backend.

**Resolution.** Bumped `next` and `eslint-config-next` from `16.0.10` to `16.2.6` in `web/package.json`. 16.2.6 is the latest fixed version that closes every advisory above (it carries forward all 15.5.x and 16.1.x patches as well as 16.2.x patches).

**Test verification.** `npm run test` 24/24 passed; `npm run build` succeeded (App Router build produced `/` and `/_not-found`); `pytest tests/ --ignore=...` 761/4-skipped passed.

### `postcss` — 1 alert, resolved by override

| # | Severity | GHSA | CVE | Fixed in | Classification |
| --- | --- | --- | --- | --- | --- |
| 38 | medium | GHSA-qx2v-qp2m-jg93 | CVE-2026-41305 | 8.5.10 | transitive (became real-exposure after deeper analysis, see below) |

**Initial classification: transitive-only.** Direct dependency pulling `postcss@8.4.31` is `next@16.2.6` (Next.js ships its own pinned copy for CSS processing during build).

**Re-classified: real-exposure path-conditional.** Although the postcss copy under `next/` only runs at build time, Ragbot ships the build output to production via `next start`. A maliciously crafted CSS module imported into a Server Component could trigger the unescaped `</style>` XSS at build time, persisting into the static HTML served to clients. Ragbot's `web/src/` has no third-party CSS imports today, but the supply-chain risk is non-trivial.

**Resolution.** Added a global `overrides` entry in `web/package.json` forcing `postcss@<8.5.10` to resolve as `>=8.5.10`. npm re-resolves the entire postcss tree (including `next/node_modules/postcss`) to `8.5.14`. Verified via `npm ls postcss`: every node now points to `8.5.14`, including the one inside `next/`.

### `flatted` — 1 alert, resolved by override

| # | Severity | GHSA | CVE | Fixed in | Classification |
| --- | --- | --- | --- | --- | --- |
| 30 | high | GHSA-rf6f-7fwh-wjgh | CVE-2026-33228 | 3.4.2 | transitive-only |

**Direct dependencies pulling it.** `@vitest/ui` and `eslint` (via `file-entry-cache` and `flat-cache`).

**Exposure analysis.** Prototype pollution via `parse()` in `flatted`. Only triggered if Ragbot's dev tools deserialize untrusted JSON via flat-cache, which they do not — flat-cache is used by ESLint for its own cache file on the developer's local machine and by Vitest's UI for the run history. Both consume only data they produced themselves. Real-exposure rating: low even though CVSS is high.

**Resolution.** Added `"flatted": ">=3.4.2"` to `overrides`. npm now resolves all `flatted` to `3.4.2` or newer. Dev-time fix only; no production impact.

### `minimatch` — 2 alerts, resolved by override

| # | Severity | GHSA | CVE | Fixed in | Classification |
| --- | --- | --- | --- | --- | --- |
| 17, 15 | high | GHSA-7r86-cg39-jmmj | CVE-2026-27903 | 10.2.3 | transitive-only |

**Direct dependencies pulling it.** ESLint, eslint-plugin-import, eslint-plugin-jsx-a11y, eslint-plugin-react, typescript-eslint, @eslint/config-array, @eslint/eslintrc.

**Exposure analysis.** ReDoS via combinatorial backtracking. ESLint is dev-only — never reachable from the deployed runtime. The advisory matters only on the developer's local machine and on CI. CI runs the lint step on trusted code (the repo itself), so an attacker would need to commit a malicious glob pattern. Real-exposure rating: very low.

**Resolution.** Added overrides for the `<3.1.4`, `>=4.0.0 <9.0.7`, and `>=10.0.0 <10.2.3` ranges. After `npm install`, all minimatch nodes are at `3.1.5` or `10.2.5`. Dev-time fix only.

### `picomatch` — 2 alerts, resolved by override

| # | Severity | GHSA | CVE | Fixed in | Classification |
| --- | --- | --- | --- | --- | --- |
| 34, 32 | medium | GHSA-3v7f-55p6-f55p | CVE-2026-33672 | 4.0.4 | transitive-only |

**Direct dependencies pulling it.** Vitest, vite-node, chokidar (via tailwind/vite).

**Exposure analysis.** Method injection in POSIX character classes leads to incorrect glob matching. Dev-only — same logic as minimatch. No production exposure.

**Resolution.** Added `"picomatch@<4.0.4": ">=4.0.4"` to overrides.

### `ajv` — 6.x ReDoS (surfaced by `npm audit`, not in Dependabot list)

GHSA-2g4f-4pwh-qvx6 — `ajv<6.14.0` has ReDoS when using the `$data` option. This was not in the open Dependabot list but `npm audit` flagged it. Dev-only via ESLint. Real-exposure rating: very low.

**Resolution.** Added `"ajv@<6.14.0": ">=6.14.0"` to overrides as a defense-in-depth measure.

### `brace-expansion` — surfaced by `npm audit`, not in Dependabot list

GHSA-f886-m6hf-6m8v — DoS from zero-step sequence. Dev-only via minimatch. Real-exposure rating: very low.

**Resolution.** Added overrides for both the `<1.1.13` and `>=2.0.0 <2.0.3` ranges.

## Final state verification

`npm audit` after the work: **`found 0 vulnerabilities`**.

`gh api repos/synthesisengineering/ragbot/dependabot/alerts` — once GitHub re-scans (within an hour of merging this PR), every open alert is expected to drop to `fixed`. The triage doc is dated `2026-05-14` and will become the citation in the dependabot config for any future alert that surfaces against the same packages but at a lower severity than the level that justified an override.

## Why no `accepted-risk` entries

Every open alert at the start of triage maps to a real or path-conditional exposure that could be fixed by a pin bump or override. None required an `accepted-risk` rationale. If a future Dependabot scan surfaces an alert where the only fix path is a major-version bump that breaks the test suite, that alert will be added to this section with a paragraph explaining why the risk is being carried.

## Test sweep results

| Suite | Before | After |
| --- | --- | --- |
| `pytest tests/ --ignore=test_memory --ignore=test_vectorstore --ignore=test_regressions_v3_1 --ignore=test_models_integration` | 761 passed, 4 skipped | 761 passed, 4 skipped |
| `npm run test` (vitest) | 24 passed | 24 passed |
| `npm run build` (next build) | Built `/` + `/_not-found` | Built `/` + `/_not-found` (Next.js 16.2.6 Turbopack) |

No rollbacks were necessary.

## Architectural decision: prefer overrides to direct lockfile edits

Wherever a transitive dep was vulnerable, the fix used npm's `overrides` field rather than hand-editing `package-lock.json`. The override survives future `npm install` runs from a clean checkout, while a lockfile edit would be silently undone by anyone running `npm update`. Each override is paired with a comment in this triage doc explaining the reason.

The override syntax used (`"<package>@<vulnerable-range>": "<fixed-range>"`) is the npm-supported form. A single global `"<package>": "<version>"` would have worked but would over-constrain non-vulnerable downstream resolutions. The narrow form keeps the lockfile open to picking up future patch updates.

## Gaps and follow-up

No outstanding gaps for this triage cycle. Dependabot will continue running weekly per the new `.github/dependabot.yml`. The next manual triage is scheduled for 2026-06.
