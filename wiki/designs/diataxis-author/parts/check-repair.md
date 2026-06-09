---
parent_design: ../../diataxis-author.md
part_slug: check-repair
title: "Check + repair — drift detection wrapping check-wiki.py + interactive repair flow with documenter dispatch"
status: pending
visibility: published
author: alex
contributors: []
created: 2026-05-22
updated: 2026-05-22
last_major_revision: 2026-05-22
dependencies: [skill-scaffold, author-classify]
estimated_scope: M
plan: "13-part-4"
prd:
project:
---

# Check + repair — drift detection wrapping check-wiki.py + interactive repair flow with documenter dispatch

**Parent design:** [diataxis-author](../../diataxis-author.md) — see Detailed Design §2 (`/diataxis check`) + §3 (`/diataxis repair`); §7 for the `documenter` sub-agent dispatch (this part is documenter's first consumer); Tech Debt §6 (check-wiki.py version-mismatch handling).

## Scope

`/diataxis check [--strict]` and `/diataxis repair` ship together because repair consumes check's output. Part 4 builds the drift-detection engine (wraps `scripts/check-wiki.py` as a subprocess + adds skill-side heuristics for mode-mixed / stale-ref / template-drift / convention-drift) + the interactive repair flow (preview-first, never silent, dispatches `documenter` for the heavy writing work).

**`/diataxis check [--strict]`** — drift detection:

- Subprocess call to `scripts/check-wiki.py` (harness-side) for the validator's rules.
- Skill-side heuristics extend with: (a) mode-mixed page detection (page has both how-to-shape + explanation-shape sections); (b) stale cross-references (link target file no longer exists); (c) template-shape drift (page authored with template X but body evolved toward template Y); (d) convention drift (page violates an operator convention stored in AgentMemory but not yet codified in check-wiki.py rules).
- Outputs structured report (per-file findings + suggested fixes + grouped by mode).
- Non-zero exit on findings.
- `--strict` mode mirrors check-wiki.py's strict mode.
- Graceful-skip on check-wiki.py subprocess failure → in-skill heuristic-only mode + clear stderr warning + log a "version mismatch" / "check-wiki.py absent" / "check-wiki.py error" line.

**`/diataxis repair`** — interactive fix-application:

- For each finding from `check`, present a suggested fix:
  - Cross-ref rewrite → automated path replacement preview.
  - Mode reclassification → `/diataxis classify` re-runs + suggests new mode.
  - Template realignment → skill rewrites page body to match the intended template's structure.
  - Split-mode-mixed-into-N-pages → operator chooses split; skill dispatches `documenter` sub-agent for the actual write.
- Operator approves / edits / rejects per finding (matches `/memory watchlist review` interactive flow).
- All file modifications preview-first; never silent.
- Repairs that involve splitting mode-mixed pages route through `documenter` sub-agent dispatch (the mechanical write worker; this is documenter's first consumer post-#13).

**`documenter` sub-agent repurposing** (operational here):

- Sub-agent's existing mode-aware write rules per ADR 0004 §4 stay unchanged.
- New: dispatched from `/diataxis repair` (not just harness `/release` as today).
- Tool allowlist: Read+Glob+Grep+Write (Write scoped to wiki/ only).
- Caller-supplies-inline-rubric pattern: caller (the skill) provides the page-to-split + the proposed N-page split + the operator's confirmed mode-classification for each split.

## Scripts shipped

- `crickets/skills/diataxis-author/scripts/check.py` (~200 lines — wraps check-wiki.py subprocess; adds skill-side drift heuristics; structured-report output).
- `crickets/skills/diataxis-author/scripts/repair.py` (~250 lines — interactive repair loop; preview-first per finding; documenter dispatch for splits).
- SKILL.md `## /diataxis check` + `## /diataxis repair` sub-command bodies (from stub to full).
- `documenter` sub-agent body updated harness-side: dispatch contract now includes diataxis-author invocations (not just /release).

## Tasks (DRAFT — refine via `/plan` when promoted)

1. Write `scripts/check.py` — subprocess wrap + 4 skill-side drift heuristics + structured report.
2. Write `scripts/repair.py` — interactive repair loop + documenter dispatch + preview-first.
3. Update SKILL.md `## /diataxis check` + `## /diataxis repair` sub-command bodies.
4. Update harness-side `documenter` sub-agent body: dispatch contract extended.
5. Smoke install tests (bash + pwsh): fixture drift cases (mode-mixed page + stale cross-ref + template-shape drift + convention-drift) + `/diataxis check` against fixture asserts findings + `/diataxis repair --stub` non-interactive (skip operator-prompt path; assert dry-run output structure).
6. Local verification + push + CI wake.

## Verification criteria

1. `/diataxis check` against fixture-with-known-drift correctly identifies all 4 drift types.
2. `/diataxis check` graceful-skips when check-wiki.py absent (in-skill-heuristic-only mode + stderr warning).
3. `/diataxis repair --stub` (non-interactive) produces structured preview for each fix without writing.
4. Mode-mixed split dispatch to `documenter` sub-agent gated via `--stub` flag in CI (no live LLM calls in smoke tests).
5. Harness `/release` phase spec amendment lands: `documenter` dispatch now goes via `/diataxis check` if `diataxis-author` is installed; graceful-skip to direct dispatch if not.
6. Smoke install + check-syntax + check-no-pii clean on 3-OS CI.

## Out of scope

- AgentMemory write-back of repair decisions — handled in part 5.
- New ADR 0008 (skill design rationale) — handled in part 5.
- Paired release v0.11.0 + v2.4.3 — handled in part 5.

## Locked design calls (inherited)

- Q1 scope = author + maintain + migrate (this part is the maintain piece: check + repair).
- Q3 documenter relationship = skill calls documenter as worker (this part is the first consumer).
- Per parent design's Detailed Design §2 (`/diataxis check`) + §3 (`/diataxis repair`) + Migrations §2 (documenter dispatch transition).

## Risks / Open questions

- **`documenter` dispatch transition risk** (Tech Debt §3 in parent): harness `/release` phase spec amendment must graceful-skip when `diataxis-author` not installed. Smoke install tests verify both paths (with + without skill installed).
- **check-wiki.py version-mismatch** (Tech Debt §6 in parent): skill versions itself against a specific check-wiki.py contract; mismatch fires clear stderr warning. Define the contract during /plan refinement — likely a `MIN_CHECK_WIKI_VERSION` constant in `check.py`.
- **Drift heuristic false positives**: same ship-instrumented + tune-from-real-use pattern as classification ambiguity. v1 errs toward false-negatives.
