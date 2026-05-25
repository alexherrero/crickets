---
parent_design: ../../diataxis-author.md
part_slug: author-classify
title: "Author + classify — live authoring guidance + single-page mode classification + diataxis-evaluator sub-agent"
status: pending
visibility: published
author: alex
contributors: []
created: 2026-05-22
updated: 2026-05-22
last_major_revision: 2026-05-22
dependencies: [skill-scaffold]
estimated_scope: M
plan: "13-part-3"
prd:
project:
---

# Author + classify — live authoring guidance + single-page mode classification + diataxis-evaluator sub-agent

**Parent design:** [diataxis-author](../../diataxis-author.md) — see Detailed Design §1 (`/diataxis author <slug>`) + §5 (`/diataxis classify <file>`); §7 for the `documenter` sub-agent's repurposing-as-worker pattern (this part exercises the dispatch shape).

## Scope

`/diataxis author <slug>` and `/diataxis classify <file>` ship together because they share the mode-classification engine. Part 3 builds the engine (`classify.py`) + both sub-command bodies + the operational flow for `diataxis-evaluator` sub-agent dispatch on ambiguous cases.

**`/diataxis author <slug>`** — live authoring guidance:

- Operator invokes when starting a new wiki page (e.g. `/diataxis author Use-The-Diataxis-Author-Skill`).
- Skill prompts for: (a) mode classification (tutorial / how-to / reference / explanation; if uncertain, sub-agent classifies from one-sentence intent statement); (b) template selection (auto-picks the right Diátaxis template from the 4 templates in ADR 0004); (c) filename style (defaults to `CamelCase-With-Dashes` per AgentMemory always-load entry).
- Output: pre-filled `wiki/<mode>/<filename>.md` page with mode-appropriate skeleton, frontmatter for ADR / Status pages where applicable, and inline `<!-- guidance -->` comments. Operator edits in their editor; skill doesn't write further content.

**`/diataxis classify <file>`** — single-page mode classification:

- Operator-debug + the sub-agent's primary invocation surface.
- Takes a single file path; returns mode classification + confidence + rationale + (if ambiguous) suggested splits.
- Pure-Python heuristic for clear cases (heading shape + frontmatter signals from ADR 0004's machine-enforceable rules).
- Dispatches `diataxis-evaluator` sub-agent for ambiguous cases (mode-mixed pages where heuristic scoring is tight).

**`diataxis-evaluator` sub-agent** (operational flow lands here; stub shipped in part 1):

- Read-only allowlist (`Read, Glob, Grep` + optional `WebFetch` for ADR 0004 cross-reference).
- Caller-supplies-inline-rubric pattern: caller dispatches with the page contents + the 4-mode contract + operator's per-repo conventions.
- Returns classification + confidence + rationale + suggested splits.
- Mirrors `adapt-evaluator` (plan #7b task 4)'s shape — same dispatch contract.

## Scripts shipped

- `crickets/skills/diataxis-author/scripts/classify.py` (~250 lines — heuristic mode-classification engine; deterministic; ADR 0004 rules + operator-convention overrides; sub-agent dispatch for ambiguous cases).
- `crickets/skills/diataxis-author/scripts/author.py` (~180 lines — invocation entry for `/diataxis author`; calls into classify.py for mode-selection + template loading + skeleton emit).
- 4 template files at `crickets/skills/diataxis-author/templates/{tutorial.md,how-to.md,reference.md,explanation.md}` — the Diátaxis-mode-aware skeleton each `/diataxis author` invocation populates.
- `diataxis-evaluator` sub-agent body filled in (stub from part 1 → operational with caller-supplies-inline-rubric contract).

## Tasks (DRAFT — refine via `/plan` when promoted)

1. Write the 4 template files (`templates/{tutorial,how-to,reference,explanation}.md`).
2. Write `scripts/classify.py` — heuristic engine + sub-agent dispatch for ambiguous cases.
3. Write `scripts/author.py` — invocation entry + template loading + skeleton emit.
4. Fill in `diataxis-evaluator` sub-agent body — operational flow + caller-supplies-inline-rubric contract.
5. Update SKILL.md `## /diataxis author` + `## /diataxis classify` sub-command bodies (from stub to full).
6. Smoke install tests (bash + pwsh): fixture wiki + `/diataxis classify` against known-mode fixture files (4 modes covered) + `/diataxis author` template-skeleton output verification + `--stub` flag for sub-agent dispatch (CI-skipped sub-agent invocation).
7. Local verification + push + CI wake.

## Verification criteria

1. `/diataxis classify` correctly classifies all 4 mode fixtures (1 each: tutorial / how-to / reference / explanation).
2. `/diataxis classify` flags an intentional mode-mixed fixture for sub-agent dispatch (`needs_subagent: true`).
3. `/diataxis author <slug>` outputs the right template skeleton (4 modes verified via dry-run-prompt fixtures).
4. Filename style defaults to `CamelCase-With-Dashes` from AgentMemory; per-invocation `--filename-style snake_case` override works.
5. Smoke install tests pass on 3-OS CI with `--stub` mode (sub-agent invocation gated via fixture stub; no live LLM calls).
6. `diataxis-evaluator` sub-agent's tool allowlist enforced (no Bash, no Write).

## Out of scope

- AgentMemory write-back of operator decisions during authoring — lands in part 5.
- `/diataxis check` + `/diataxis repair` — part 4.
- `documenter` dispatch from skill (mechanical-write worker) — lands when first needed; part 4's repair flow is the natural first consumer.

## Locked design calls (inherited)

- Q1 scope = author + maintain + migrate (this part is the author + classify pieces).
- Q4 sub-command shape = single skill with multi-sub-commands.
- Per parent design's Detailed Design §1 (`/diataxis author`) + §5 (`/diataxis classify`).

## Risks / Open questions

- **Mode classification ambiguity** (Tech Debt §1 in parent): ship-instrumented + tune-from-real-use pattern. v1 errs toward false-negatives. Operator tunes thresholds via AgentMemory conventions as patterns emerge.
- **Sub-agent budget** (Tech Debt §7): hard `--limit N` cap (default 5) per invocation; tested in part 4's `/diataxis check` flow where the cap matters most.
- **Template content**: 4 templates need to be authored. Diátaxis spec doesn't dictate exact skeleton — operator preferences (e.g. tutorial template structure) need locked. Capture during /plan refinement.
