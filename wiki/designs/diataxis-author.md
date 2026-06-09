---
title: diataxis-author skill — author + maintain a Diátaxis wiki for any repo
status: launched
visibility: published
author: alex
contributors: []
created: 2026-05-22
updated: 2026-05-22
last_major_revision: 2026-05-22
prd: <none — codified from ROADMAP item #13 + ADR 0004 + migrate-to-diataxis predecessor>
project: <none>
---

<!--
  Created via `/design author` on 2026-05-22 as the entry point to plan #13.
  Skeleton pre-filled from:
    - ROADMAP item #13 (agentm) — "write and maintain a Diátaxis-style
      wiki for any repo; redesign of harness's migrate-to-diataxis from
      one-shot migration to ongoing authoring + maintenance"
    - ADR 0004 (agentm wiki) — Diátaxis Documentation Spec
      (4 modes, 4 templates, machine-enforceable rules, scripts/check-wiki.py)
    - agentm/harness/skills/migrate-to-diataxis.md — predecessor
      one-shot-migration skill (~250 lines; preview-first, classifies by
      heading shape, mode-mixed flagged for human split)
    - Established convention: `/memory` skill's multi-sub-command shape
      (save / evolve / reflect / promote / etc.) — likely template for
      diataxis-author's own sub-commands

  Status will transition draft → review → final → launched per the
  `/design author` lifecycle. Walk-sections pass is the next step
  after operator answers the 4 load-bearing questions in the
  "design questions to operator" exchange (2026-05-22).
-->

# diataxis-author skill — author + maintain a Diátaxis wiki for any repo

## Context

### Objective

Operators authoring documentation for a project that follows the [Diátaxis](https://diataxis.fr/) four-mode discipline (`tutorials/` + `how-to/` + `reference/` + `explanation/`) currently work without skill-level support — they hand-write pages, rely on `scripts/check-wiki.py --strict` to catch mode violations after the fact, and manually invoke the harness's `documenter` sub-agent at `/release` for periodic sweeps. There's no skill that **proactively guides authoring** ("you want a how-to here; pick the right template; here are the rules"), no skill that **detects + repairs drift** as the wiki evolves (stale cross-refs, mode-mixed pages that emerge from edits, missing-template content), and no skill that **encodes the operator's preferred conventions** (filename-style `CamelCase-With-Dashes`, mode-mixed → human-split, ADR shape with NOTE block + re-audit triggers, etc.). This design ships that skill — `diataxis-author` — as the second major skill in `crickets` (after `memory`) and the natural next step after the MemoryVault parent design fully shipped (#7a + #7b Completed 2026-05-22).

### Background

**Prior art in the personal-dev-env**:

- **ADR 0004 — Diátaxis Documentation Spec** ([agentm wiki](../../../../agentm/wiki/explanation/decisions/0004-diataxis-documentation-spec.md), 2026-05-15) — locks the four-mode discipline + four templates (Tutorial / How-To / Reference / Explanation) + machine-enforceable authoring rules (no `## Rationale` in how-tos; no numbered-step lists in references; etc.) + `documenter` sub-agent mode-aware write rules + reader-journey `Home.md` + `_Sidebar.md` shape + per-repo `wiki/.diataxis` marker. This is the canonical specification this skill enforces.
- **`scripts/check-wiki.py`** ([agentm scripts/](../../../../agentm/scripts/check-wiki.py)) — strict-mode validator that the harness CI runs on every commit. Catches mode violations + cross-ref breakage after the fact. The skill should leverage this as the verification surface.
- **`migrate-to-diataxis` skill** ([agentm harness/skills/migrate-to-diataxis.md](../../../../agentm/harness/skills/migrate-to-diataxis.md)) — one-shot migration from old audience-based layout (`development/` / `operational/` / `design/` / `architecture/`) to Diátaxis. Preview-first, deterministic classification by heading shape, mode-mixed pages flagged for human split, link rewrites + `git mv` for blame preservation. This skill is **the predecessor** that diataxis-author redesigns from one-shot-migration to ongoing-authoring-and-maintenance.
- **`documenter` sub-agent** (mentioned in ADR 0004 + harness `/release`) — currently mode-aware writer that the harness dispatches at `/release` for sweep-style updates. diataxis-author's relationship to documenter is one of the load-bearing design questions (subsume / coordinate / coexist).

**Why now**:

1. **MemoryVault is fully shipped** (both #7a + #7b roadmap items Completed 2026-05-22). The natural next major skill per the locked execution-order ("natural fit after MemoryVault; wiki-style preferences can be stored there") — diataxis-author can store the operator's Diátaxis preferences (template overrides, classification edge cases, filename-style conventions) as `personal-private/_always-load/diataxis-*.md` entries, so the skill behaves consistently across every project the operator authors docs in.
2. **The `documenter` sub-agent works** but only fires at `/release` boundaries and only against changed files — there's no live authoring guidance. Operators writing a new how-to today must remember the rules manually + wait for `check-wiki.py --strict` to catch violations.
3. **`migrate-to-diataxis` is one-shot** — once a project's wiki is migrated, the skill never fires again, and the operator's ongoing authoring is unsupported. Redesigning this from migration-only to ongoing-author-and-maintain extends the skill's lifecycle to match the operator's actual usage pattern.
4. **The dogfood surface is rich** — the operator maintains multiple Diátaxis-shaped wikis already (agentm, crickets, plus operator-private siblings) plus the just-shipped MemoryVault parent design. Plenty of real authoring to validate the skill against.
5. **Plan #6's `/design` skill is the natural designer** — per the locked execution-order note, #13 is "designed via design skill". This design doc is the first dogfood of `/design author` post-MemoryVault.

## Design

### Overview

`diataxis-author` is a **single crickets skill** with five sub-commands covering the full Diátaxis-wiki lifecycle: live authoring guidance + drift detection + repair + one-shot migration of legacy wikis + per-page classification. Architecturally it mirrors the `/memory` skill's shape: one SKILL.md with multi-sub-command bodies, deterministic Python pipelines under `skills/diataxis-author/scripts/`, and a single read-only sub-agent (`diataxis-evaluator`) for the semantic mode-classification work that's too judgment-heavy for regex heuristics alone. The skill **subsumes** the harness's existing `migrate-to-diataxis` predecessor (`/diataxis migrate` becomes the new entry point; old skill ships a deprecation notice in v1 then is removed in a follow-up harness release). The harness-side `documenter` sub-agent is **repurposed as the skill's worker**: diataxis-author dispatches it for the heavy writing work (same pattern as `/memory adapt-skills` dispatching `adapt-evaluator`); `documenter` becomes Diátaxis-aware and operates only via dispatch. **AgentMemory integration is read + write**: skill loads operator conventions from `personal-private/_always-load/diataxis-*.md` at startup; when the operator makes a judgment call (e.g. "this mode-mixed page should split as X+Y"), the skill offers to capture the decision back via `/memory save` so the same pattern applies on next encounter. Per-repo overrides live in an optional `<repo>/wiki/.diataxis-conventions.md` file alongside the existing `.diataxis` marker.

### Infrastructure

**No new infrastructure required.** Pure-Python pipeline under `skills/diataxis-author/scripts/`; stdlib-only (no new third-party deps) — matches the established convention from `/memory` (per ADR 0007 D7). One new sub-agent (`diataxis-evaluator`) for ambiguous-page semantic classification; same dispatch shape as `adapt-evaluator` + `memory-idea-researcher` (read-only allowlist + caller-supplies-inline-rubric pattern). Leverages existing infrastructure: `scripts/check-wiki.py` (called as a subprocess by `/diataxis check`); existing `documenter` sub-agent (repurposed as worker per the design above); existing `.diataxis` per-repo marker (signals which projects this skill applies to). No new MCP server, no new hook (the skill is operator-invoked + optionally fires from `/release` like `documenter` does today). Local-first + offline-capable; no network calls in the core path.

### Detailed Design

#### 1. `/diataxis author <slug>` — live authoring guidance

Operator invokes when starting a new wiki page. Skill prompts for: (a) **mode classification** — operator picks tutorial / how-to / reference / explanation; if uncertain, sub-agent classifies based on a one-sentence intent statement; (b) **template selection** — auto-picks the right template from the 4 Diátaxis templates per ADR 0004; (c) **filename style** — defaults to operator's preferred `CamelCase-With-Dashes` per AgentMemory always-load entry (operator can override per-invocation). Output: pre-filled `wiki/<mode>/<filename>.md` page with mode-appropriate skeleton, frontmatter (where applicable for ADRs / Status pages), and inline `<!-- guidance -->` comments stripped before final save. Operator edits in their editor; skill does not write content beyond the skeleton.

#### 2. `/diataxis check [--strict]` — drift detection

Wraps `scripts/check-wiki.py` as a subprocess; surfaces results as a structured report (per-file findings + suggested fixes + grouped by mode). `--strict` mode mirrors `check-wiki.py --strict`. Adds Diátaxis-author-specific drift signals beyond what the validator catches: (a) **mode-mixed page detection** (page has both how-to-shape + explanation-shape sections in body); (b) **stale cross-references** (link target file no longer exists at that path); (c) **template-shape drift** (page was authored with template X but body has evolved toward template Y); (d) **convention drift** (page violates an operator convention stored in AgentMemory but not in check-wiki.py rules). Outputs a structured report; non-zero exit on findings.

#### 3. `/diataxis repair` — apply suggested fixes for detected drift

For each finding from `check`, present a suggested fix (cross-ref rewrite / mode reclassification / template realignment / split-mode-mixed-into-N-pages) + ask operator to approve / edit / reject. Pattern matches `/memory watchlist review`'s interactive flow. Repairs that involve splitting a mode-mixed page route through `documenter` sub-agent dispatch (the heavy writing work). All file modifications preview-first; never silent.

#### 4. `/diataxis migrate` — one-shot legacy → Diátaxis migration

Subsumes the harness's `migrate-to-diataxis` predecessor (~250 lines). Same contract: preview-first; deterministic classification by heading shape per ADR 0004's machine-enforceable rules; `git mv` for blame preservation; mode-mixed pages flagged for human split (delegates to `/diataxis repair` for the actual split); link rewrites across all `wiki/**/*.md` files. Runs at most once per repo (`wiki/.diataxis` marker existence aborts subsequent invocations).

#### 5. `/diataxis classify <file>` — single-page mode classification

Operator-debug + the sub-agent's primary invocation surface. Takes a single file path; returns mode classification + confidence + rationale + (if ambiguous) suggested splits. Pure-Python heuristic for the clear cases (heading shape + frontmatter signals); dispatches `diataxis-evaluator` sub-agent for the ambiguous cases (mode-mixed pages where heuristic scoring is tight).

#### 6. AgentMemory integration

**Read** (on every skill invocation): glob `<vault>/personal-private/_always-load/diataxis-*.md` → load operator conventions (filename style / mode-mixed split preferences / template overrides / project-specific exceptions). Falls back to ADR 0004's defaults if no AgentMemory entries exist.

**Write** (operator-confirmed via permeable_boundary helper): when the operator makes a judgment call during `/diataxis author` / `/diataxis repair` / `/diataxis classify` (e.g. "this mode-mixed page should always split as how-to+reference, not as my default how-to+explanation"), the skill offers to capture the decision as a new always-load entry. Operator confirms → entry lands via `/memory save --always-load`. Same A3 permeable-write-boundary contract as `/memory reflect`'s idea capture.

**Per-repo overrides**: optional `<repo>/wiki/.diataxis-conventions.md` (operator-edited markdown). When present, overrides global AgentMemory conventions for that specific repo. Auto-seeded on `/diataxis migrate` with the project's detected conventions; operator edits over time.

#### 7. `documenter` sub-agent repurposing

Existing `documenter` sub-agent (harness-side, fires at `/release` per current spec) becomes diataxis-author's worker. The sub-agent's tool allowlist + Diátaxis-aware write rules per ADR 0004 §4 stay unchanged. New: it only fires via `diataxis-author` dispatch (operator invocation) or `/release` (harness-side, unchanged). The harness `/release` phase spec gets a small amendment: `documenter` dispatch becomes `/diataxis check` invocation if `diataxis-author` is installed; graceful-skip to current `documenter` direct-dispatch if not. Backward-compatible.

#### 8. Hooks integration (optional, deferred)

v1 is operator-invoked only. v2 candidates (deferred to a future task): SessionStart hook surfaces "you have N drift findings — `/diataxis check`"; UserPromptSubmit hook when operator types "I want to document X" auto-dispatches `/diataxis author X`. Out of scope for this design's v1 ship.

## Alternatives Considered

1. **Extend `documenter` sub-agent instead, skip the skill layer.** Rejected: `documenter` fires only at `/release` boundaries; the gap is live authoring guidance during regular work, not periodic sweeps. A skill exposes operator-invocable surface (`/diataxis author <slug>`) that sub-agents alone can't.
2. **Keep `migrate-to-diataxis` + add a separate `diataxis-doctor` skill.** Rejected: operator's mental model is "one Diátaxis skill, not two" (per the Q1 answer). Lifecycle split (migrate-once vs. ongoing) is real but better captured as sub-commands inside one skill than as two skills the operator has to remember.
3. **Encode all conventions in `check-wiki.py --strict` + skip the skill layer entirely.** Rejected: validators catch violations after the fact; the skill provides **proactive** guidance (template selection, mode classification, filename style) at authoring time. Both layers complement: skill prevents drift at write time; `check-wiki.py` catches drift at commit time + during `/diataxis check`.
4. **Multiple discrete skills (`diataxis-author` + `diataxis-doctor` + `diataxis-migrate`).** Rejected per Q4 answer: single skill with sub-commands matches the established `/memory` pattern; reduces install surface + cognitive load. Operator can still invoke individual sub-commands directly when needed.
5. **AgentMemory read-only (no write-back of operator decisions).** Rejected per Q3 answer: the skill becomes consistent across the operator's multiple Diátaxis-shaped wikis only if learned conventions write back to `_always-load/`. Read-only would force operator to manually `/memory save` every judgment call.
6. **No AgentMemory integration at all.** Rejected per Q3 answer + the locked execution-order note ("wiki-style preferences can be stored there"). Decoupling diataxis-author from MemoryVault would lose the cross-project convention sync that motivates this skill's existence post-MemoryVault.
7. **Replace `documenter` sub-agent entirely with diataxis-author writing directly.** Rejected per Q3 answer: keep `documenter` as the heavy-write worker; diataxis-author is the operator-facing orchestration + guidance surface. Same separation as `/memory adapt-skills` (orchestration) vs. `adapt-evaluator` (sub-agent worker) — proven shape from #7b.

## Dependencies

- **AgentMemory (#7a + #7b ✅ done)** — for storing + retrieving operator conventions as `_always-load/diataxis-*.md` entries. Read-side uses the existing recall engine; write-side uses `/memory save --always-load` with permeable_boundary helper.
- **`documenter` sub-agent** ([agentm](https://github.com/alexherrero/agentm)) — repurposed as diataxis-author's worker. The sub-agent's existing mode-aware write rules per ADR 0004 §4 stay unchanged; only its dispatch path changes (now via diataxis-author rather than `/release` direct).
- **`scripts/check-wiki.py`** ([agentm/scripts/check-wiki.py](https://github.com/alexherrero/agentm/blob/main/scripts/check-wiki.py)) — called as subprocess by `/diataxis check`. Validator stays harness-side; skill consumes its output.
- **ADR 0004 — Diátaxis Documentation Spec** ([agentm wiki](../../../../agentm/wiki/explanation/decisions/0004-diataxis-documentation-spec.md)) — the canonical convention source. Skill enforces this spec; ADR's machine-enforceable rules become the skill's heuristic backbone.
- **Existing `migrate-to-diataxis` skill** ([agentm/harness/skills/migrate-to-diataxis.md](https://github.com/alexherrero/agentm/blob/main/harness/skills/migrate-to-diataxis.md)) — subsumed (see Migrations); v1 ships deprecation notice in predecessor; follow-up harness release removes it.
- **`/design` skill** — used to author *this* design doc; runtime independence (skill doesn't depend on `/design` once shipped).
- **Permeable-boundary helper** (`crickets/skills/memory/scripts/permeable_boundary.py`, shipped in plan #7a part 4) — reused for the AgentMemory write-back step; `confirm_write_outside_diataxis-author()` follows the same A3 contract.
- **Python stdlib only** for skill scripts (no new third-party deps; matches ADR 0007 D7).

## Migrations

**1. `migrate-to-diataxis` predecessor subsumed.** Plan #13 part 1 (or part 2 — TBD at translate time) ships a deprecation notice in the harness's existing `migrate-to-diataxis.md` skill: when invoked, prints `[migrate-to-diataxis] DEPRECATED: this skill has been subsumed by crickets's diataxis-author. Use '/diataxis migrate' instead. This skill will be removed in a future harness release.` Exits non-zero. Operators with existing harness installs see the notice + manually run `/diataxis migrate`. Follow-up harness PATCH release (after dogfood window) removes the predecessor file entirely + adds a `REMOVED_HARNESS_SKILLS` entry in `check-references.py` analogous to the `REMOVED_HOSTS` dict from plan #15.

**2. `documenter` sub-agent dispatch path change.** Currently `documenter` is dispatched directly from harness `/release` Step N. After #13 ships, the harness `/release` phase spec gets amended: if `diataxis-author` is installed (detected via skill-presence check), dispatch `/diataxis check` instead of direct `documenter`; graceful-skip to current direct dispatch if `diataxis-author` not installed. Backward-compatible — operators without the new skill see unchanged behavior.

**3. Per-repo `.diataxis-conventions.md` auto-seed.** When `/diataxis migrate` runs against a legacy wiki, it writes a `<repo>/wiki/.diataxis-conventions.md` capturing the project's detected conventions (filename style observed, any mode-mixed-split patterns it had to flag). Operator edits over time. Optional file; absent means use AgentMemory + ADR 0004 defaults.

**4. AgentMemory always-load entry seeding.** Skill ships with a one-shot seed step on first install: writes a minimal set of `_always-load/diataxis-*.md` entries (filename-style preference, default mode-mixed split convention, ADR 0004 cross-reference). Operator edits as conventions evolve via the write-back flow.

## Technical Debt & Risks

1. **Mode classification ambiguity is the core hard problem.** Predecessor `migrate-to-diataxis` flags mode-mixed pages for human split — punts. New skill must handle live during `/diataxis author` + `/diataxis classify`. Risk: false positives interrupt authoring flow ("this page you're writing looks like a how-to with explanation creep — split?"). **Mitigation**: ship-instrumented + tune-from-real-use pattern (same as `recall.py` rank-merge weights from plan #7a part 5 task 6 + `adapt_skills.py` 6-rule rubric from #7b task 4). v1 errs toward false-negatives (less interruption); operator tunes thresholds in AgentMemory conventions as patterns emerge.

2. **Convention drift across operator's Diátaxis wikis**. If skill learns a convention in one repo + applies in another but conventions differ subtly, operator sees surprise. **Mitigation**: per-repo `.diataxis-conventions.md` override file (per Migrations §3). Always-load conventions are global defaults; per-repo file overrides for that one project.

3. **`documenter` sub-agent dispatch transition** (Migrations §2). Risk: harness `/release` phase spec change breaks for operators who install harness but not toolkit. **Mitigation**: graceful-skip to direct dispatch when `diataxis-author` not installed.

4. **AgentMemory write-back fatigue**. If skill offers to capture every judgment call as a new always-load entry, operator drowns in confirmation prompts. **Mitigation**: only offer write-back when (a) operator made a non-trivial decision (not just accepting defaults) AND (b) the decision diverges from existing conventions. Same `MEMORY_REVIEW_MODE=silent` env var as `/memory reflect` for operators who want zero prompts.

5. **`/diataxis migrate` deletion semantics** inherited from predecessor. Predecessor uses `git mv` for blame preservation but the operation is still a structural rearrangement. Risk: if the migration is wrong (mode-mixed page misclassified), operator has to manually revert via git. **Mitigation**: predecessor's preview-first contract carries forward unchanged + the new skill adds a single-commit safety net (entire migration is one commit; revert is `git revert <SHA>`).

6. **`check-wiki.py` subprocess dependency** for `/diataxis check`. If the operator's check-wiki.py has divergent rules from skill expectations, the report can confuse. **Mitigation**: skill versions itself against a specific check-wiki.py contract; mismatch triggers a clear "check-wiki.py version mismatch; skill expects vN.M; got vX.Y" stderr warning + falls back to in-skill heuristics.

7. **Sub-agent budget for `/diataxis classify`**. Heavy ambiguous-page classification could fire many sub-agent dispatches if operator runs `/diataxis check` on a large wiki with many ambiguous pages. **Mitigation**: hard `--limit N` cap (default 5) per `/diataxis check` invocation; surface "N more ambiguous pages — re-run with --limit M" rather than runaway dispatch.

## Quality Attributes

### Security

N/A: internal developer-tooling skill operating against operator-owned wiki files; no external surface, no untrusted input handling beyond standard markdown parsing. The `documenter` sub-agent's tool allowlist (Read+Glob+Grep+Write to wiki/ only) provides the same defense-in-depth as the other read-only-with-scoped-write sub-agents (`adapt-evaluator`, `memory-idea-researcher`, `evaluator`).

### Reliability

Preview-first contract for every file modification (inherited from `migrate-to-diataxis` predecessor). Skill never writes to wiki/ without operator confirmation. `check-wiki.py` subprocess failure → graceful-skip to in-skill heuristic-only mode + clear stderr warning. AgentMemory unavailable → falls back to ADR 0004 defaults. Same graceful-skip pattern as `/memory adapt-skills`.

### Data Integrity

`git mv` for all file moves preserves blame history (inherited from `migrate-to-diataxis` predecessor). Single-commit-per-migration safety net (entire `/diataxis migrate` operation is one commit; revert is `git revert <SHA>`). Per-page modifications during `/diataxis repair` are also single-commit when batched; operator can review the diff before commit.

### Privacy

N/A: skill operates on operator-owned wiki files; no PII handling, no telemetry, no data exfiltration. Same posture as the rest of the toolkit per ADR 0001.

### Scalability

Wiki sizes scale linearly with project. Realistic operator scale: a primary repo has ~20-25 wiki pages; smaller siblings have ~15 pages. `/diataxis check` walltime scales linearly with page count via `check-wiki.py` subprocess (~1-2s per project). `/diataxis migrate` is one-shot per repo; even a 100-page legacy wiki classifies + previews in under 30s on M-series hardware. Sub-agent dispatch for ambiguous classification capped by `--limit N` (default 5) so a single `/diataxis check` invocation can't burn unlimited sub-agent budget.

### Latency

No hard time budget (operator-invoked, not hook-driven). `/diataxis check` target <5s end-to-end on a 50-page wiki (check-wiki.py subprocess + skill-side aggregation + report formatting). `/diataxis author <slug>` target <2s for skeleton generation. `/diataxis classify <file>` target <1s for heuristic path; sub-agent dispatch adds whatever the LLM call costs (operator-perceived as an interactive prompt, not a blocker).

### Abuse

N/A: single-user personal tooling, no external surface, no rate-limiting needs, no anti-spam, no malicious-input handling beyond standard Claude Code sandboxing. The wiki is trusted-source-only (operator-owned).

### Accessibility

N/A: text-only on-disk markdown output; no UI provided by this design. Operator accesses output via their editor (which provides its own accessibility per editor's own compliance). Agent-side surface is Claude Code's standard text-based UX.

### Testability

Smoke install tests follow established pattern (per `/memory` skill suite): one test block per sub-command + fixture wiki dir. Mode classification heuristic is deterministic + unit-testable (regex + heading-shape rules; no LLM in the heuristic path). Sub-agent dispatch tested via stub mode (sub-agent returns canned response when `--stub` flag set; same pattern as embed.py stub mode). Per-OS smoke tests on Linux + Mac + Windows via existing CI matrix. Predecessor `migrate-to-diataxis` has no automated tests (manual operator verification); diataxis-author lifts that to full smoke-test coverage.

### Internationalization & Localization

N/A: skill emits English-only template content + log messages. Operator can override templates via per-repo `wiki/.diataxis-conventions.md` to ship localized templates if needed; skill doesn't gate on locale.

### Compliance

N/A: no regulatory requirements for personal developer tooling.

## Project management

### Work estimates

Expect **5 parts of S-M sizing** — tighter than #7's 6-part decomposition since this is a single skill with focused scope:

1. (S) **Skill scaffold + frontmatter** — SKILL.md skeleton with manifest + 5 sub-command stubs + installer wiring + smoke install path tests + `diataxis-evaluator` sub-agent stub.
2. (M) **`/diataxis migrate` subsumes predecessor** — port `migrate-to-diataxis.md` logic from harness to toolkit; add deprecation notice to predecessor; preview-first contract preserved; smoke install tests against fixture legacy wiki.
3. (M) **`/diataxis author <slug>` + `/diataxis classify <file>`** — live authoring guidance + single-page classification; sub-agent dispatch for ambiguous cases; smoke install tests against 4-template fixture wiki.
4. (M) **`/diataxis check` + `/diataxis repair`** — drift detection via check-wiki.py subprocess + skill-side mode-mixed/stale-ref/template-drift heuristics; interactive repair flow; smoke install tests against fixture drift cases.
5. (S) **AgentMemory integration + documenter dispatch + docs + paired release** — read/write conventions per A3 boundary; harness `/release` phase-spec amendment for documenter dispatch transition; new wiki/how-to/Use-Diataxis-Author.md (later moved to [Agent M wiki](https://github.com/alexherrero/agentm/wiki/Use-Diataxis-Author) in v2.0.0 per V4 #36); new ADR (toolkit-side, number TBD — likely 0008); paired release (toolkit MINOR + harness PATCH paired-doc-only).

Sub-agent (`diataxis-evaluator`) lands as part of part 3 (scoped use; doesn't need its own part).

### Documentation Plan

- **New how-to** at `crickets/wiki/how-to/Use-Diataxis-Author.md` — comprehensive page covering 5 sub-commands + worked scenarios (author new page / detect drift / repair / migrate legacy wiki / classify ambiguous page) + AgentMemory integration walkthrough + per-repo override pattern + troubleshooting (mode-mixed false positives / check-wiki.py version mismatch / documenter dispatch transition). *(Moved to [Agent M wiki — Use-Diataxis-Author](https://github.com/alexherrero/agentm/wiki/Use-Diataxis-Author) in v2.0.0 per V4 #36.)*
- **New ADR** at `crickets/wiki/explanation/decisions/0008-diataxis-author.md` (or next available number) — locked design calls from this design (Q1-Q4 + key Tech Debt items + load-bearing assumptions). Distinct from harness-side ADR 0004 (which is the *Diátaxis spec*; this ADR is the *skill design*).
- **Updates**: `Home.md` + `_Sidebar.md` (add diataxis-author to reader-intent sections); `Customization-Types.md` (add as second `kind: skill` example after `memory`); harness `/release` phase spec amendment for documenter dispatch transition.
- **This design doc** (`diataxis-author.md`) becomes the canonical "Why we built this" wiki entry point per the locked design call from plan #6 (same pattern as MemoryVault parent design).

### Launch Plans

Ships as **toolkit MINOR + harness PATCH paired release** (continues the 3-pair pattern established across v2.4.0/v2.4.1/v2.4.2 per ADR 0007 documentation). Likely toolkit `v0.11.0` (since v0.10.0 just shipped); harness `v2.4.3` paired-doc-only. Each of the 5 parts ships as its own commit; final part 5 is the release-pair commit.

No feature flags; no phased rollout (single operator, no user segments). Escape hatches: `diataxis-author.enabled: false` skill-level config to disable; `bash crickets/install.sh --uninstall diataxis-author` to remove entirely; per-repo `wiki/.diataxis-conventions.md` for project-specific overrides without touching global state.

## Operations

### SLAs

N/A — internal personal-dev-env tooling, no external SLA exposure.

### Monitoring and Alerting

No runtime monitoring (developer-tooling skill, operator-invoked, no production runtime). The monitoring surface for the *output* (wiki quality) is `check-wiki.py --strict` running in CI on every commit + the new `/diataxis check` invocation. Skill itself has no SLAs to monitor.

### Logging Plan

Stderr-only structured log lines for skill invocations: mode-classification decisions (with confidence + rationale for operator-debug); drift findings (per-file counts); cross-ref repairs (per-file diff); sub-agent dispatches (with `--limit N` budget tracking). No persistent log files beyond what the harness's standard verification log captures. Operator can grep `diataxis-author` stderr lines for audit.

### Rollback Strategy

Three rollback levels:

1. **Soft disable** (most common): set `diataxis-author.enabled: false` in skill config → all sub-commands become no-ops with clear "skill disabled" stderr. Reversible by flipping back. Useful for "I want to author manually for a session without skill prompts".
2. **Skill uninstall**: `bash crickets/install.sh --uninstall diataxis-author` removes the skill + sub-agent from host destinations. Per-repo `.diataxis-conventions.md` files + AgentMemory always-load entries are operator-owned data, untouched.
3. **Wiki rollback**: every skill-driven modification is git-tracked (skill never writes outside git-controlled paths). Per-page rollback: `git revert <SHA>` on the modification commit. `/diataxis migrate`'s single-commit safety net means the entire migration can be reverted with one `git revert`. Mode-mixed misclassifications surface at preview time (operator catches before commit); if one slips through, normal git workflow recovers.

No schema migrations involved in rollback — markdown + frontmatter format is backwards-compatible by design. The deprecated predecessor `migrate-to-diataxis` skill stays in the harness through v1's dogfood window so operators can roll back the skill choice itself (use predecessor) if needed; predecessor is removed only in a follow-up harness release after dogfood confirms diataxis-author is the better surface.

## Document History

| Date | Change | Status |
|---|---|---|
| 2026-05-22 | **Initial draft created via `/design author`.** Pre-filled Context (Objective + Background) + skeleton placeholders for Design / Alternatives / Dependencies / Migrations / Tech Debt / QA / Project management / Operations. 4 load-bearing design questions surfaced to operator (scope; predecessor handling; AgentMemory depth; sub-command shape). Walk-sections pass kicks off after operator answers. | draft |
| 2026-05-22 | **Walk-sections pass complete.** Operator answered all 4 load-bearing questions (all "recommended" defaults): (Q1) scope = author + maintain + migrate (subsume `migrate-to-diataxis` predecessor); (Q2) AgentMemory depth = read + write conventions (per-repo overrides via `.diataxis-conventions.md`); (Q3) `documenter` relationship = skill calls documenter as worker (separation of orchestration vs. mechanical write — mirrors `/memory adapt-skills` + `adapt-evaluator`); (Q4) sub-command shape = single skill with multi-sub-commands (matches `/memory`). Filled in: Design overview + 8 Detailed Design subsections (5 sub-commands + AgentMemory integration + documenter repurposing + deferred-hooks-v2); 7 Alternatives Considered with rejection rationale; 7 Dependencies; 4 Migrations (predecessor deprecation + documenter dispatch transition + per-repo conventions + AgentMemory seed); 7 Tech Debt + Risks; 11 Quality Attributes (Security N/A / Reliability preview-first / Data Integrity git mv + single-commit / Privacy N/A / Scalability linear + sub-agent budget cap / Latency operator-invoked / Abuse N/A / Accessibility N/A / Testability stub-mode + smoke install / i18n N/A / Compliance N/A); Project management (5 parts S-M sizing; Documentation Plan with new how-to + new ADR 0008; Launch Plans paired-release v0.11.0 + v2.4.3); Operations (no runtime monitoring; stderr-only logging; three-level rollback). **Status transitions to review** — awaiting operator approval to lock as `final` before `/design translate` can run. | review |
| 2026-05-22 | **Approved as final via fast-path** (per-section review pass skipped per operator signal "approve diataxis-author as final"). Doc is now immutable until either `/design translate` runs (next step) or a human manually edits the file + reverts Status to `review`. Unblocks `/design translate` (split into structural parts) and `/design sequence` (generate PLAN.md per part). | final |
| 2026-05-22 | **Translated + sequenced** via `/design translate` → 5 parts at `wiki/explanation/designs/diataxis-author/parts/` (`skill-scaffold` + `author-classify` + `check-repair` + `migrate-subsume` + `agentmemory-docs-release`) + `/design sequence` → 5 PLAN.md files (1 active at `.harness/PLAN.md`, 4 queued at `.harness/designs/diataxis-author/queued-plans/`). Topological order via Kahn's algorithm + alphabetical tie-breaking: skill-scaffold → author-classify → check-repair → migrate-subsume → agentmemory-docs-release. Status stays `final` (translate doesn't transition Status). | final |
| 2026-05-22 | **All 5 parts executed + paired release shipped.** Plan #13 closes with `crickets v0.11.0` (substantive; 8 commits across plan parts 1-5) + `agentm v2.4.3` (paired-doc-only; 4th consecutive paired-release-as-documentation pair). Status transitions `final → launched` per `/design` skill lifecycle (automatic when last part's PLAN.md hits Status: done). Second real dogfood of plan #6's `/design` skill (first was MemoryVault parent design closed 2026-05-22 earlier today). All locked design calls Q1-Q4 honored end-to-end. **3 Windows-specific CI failures caught + fixed mid-plan** per `[[wake-on-ci-pattern]]` (Start-Process arg split; git mv cwd dependence; cp1252 stdout encoding); cross-platform Python gotcha pattern now firmly locked. **Subsumes predecessor**: harness's `migrate-to-diataxis` deprecated (file removal in follow-up harness PATCH after dogfood). | launched |
