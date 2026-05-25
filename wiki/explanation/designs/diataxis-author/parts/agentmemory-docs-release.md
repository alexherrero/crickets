---
parent_design: ../../diataxis-author.md
part_slug: agentmemory-docs-release
title: "AgentMemory integration + docs + ADR 0008 + paired release v0.11.0 + v2.4.3"
status: pending
visibility: published
author: alex
contributors: []
created: 2026-05-22
updated: 2026-05-22
last_major_revision: 2026-05-22
dependencies: [skill-scaffold, migrate-subsume, author-classify, check-repair]
estimated_scope: S
plan: "13-part-5"
prd:
project:
---

# AgentMemory integration + docs + ADR 0008 + paired release v0.11.0 + v2.4.3

**Parent design:** [diataxis-author](../../diataxis-author.md) — see Detailed Design §6 (AgentMemory integration); Migrations §3 (per-repo `.diataxis-conventions.md` auto-seed) + §4 (AgentMemory always-load seed); Documentation Plan; Launch Plans.

## Scope

Final part of plan #13. Lands the AgentMemory integration (read + write conventions per Q2) + the harness-side documenter dispatch transition (per Migrations §2) + new how-to + new ADR + paired release. Plan-completion close-out: archive PLAN.md, move ROADMAP item #13 to Completed, parent design transitions `final → launched` (per the established `/design` lifecycle from plan #6 ADR 0004).

**1. AgentMemory integration**:

- **Read** (every skill invocation): glob `<vault>/personal-private/_always-load/diataxis-*.md` → load operator conventions. Falls back to ADR 0004 defaults if no entries exist.
- **Write** (operator-confirmed via permeable_boundary helper): when operator makes a judgment call during `/diataxis author` / `/diataxis repair` / `/diataxis classify`, skill offers to capture as new always-load entry. Operator confirms → entry lands via `/memory save --always-load`.
- **Per-repo overrides**: optional `<repo>/wiki/.diataxis-conventions.md` (operator-edited). When present, overrides global AgentMemory conventions for that repo. Auto-seeded on `/diataxis migrate` (already lands in part 2; this part wires the read-side).
- **Initial seed** on first install: ship minimal `_always-load/diataxis-*.md` entries — filename-style preference, default mode-mixed split convention, ADR 0004 cross-reference.
- **`permeable_boundary` helper** reused (no new code; existing helper from plan #7a part 4).

**2. `documenter` dispatch transition** (Migrations §2):

- Harness `/release` phase spec amendment: `documenter` dispatch becomes `/diataxis check` invocation if `diataxis-author` is installed (detect via skill-presence check); graceful-skip to current direct dispatch if not. Backward-compatible.
- Updates `agentm/harness/phases/05-release.md` (canonical) + adapter files.

**3. New how-to** at `crickets/wiki/how-to/Use-Diataxis-Author.md`:

- Comprehensive page covering 5 sub-commands + worked scenarios (author new page / detect drift / repair / migrate legacy wiki / classify ambiguous page) + AgentMemory integration walkthrough + per-repo override pattern + troubleshooting (mode-mixed false positives / check-wiki.py version mismatch / documenter dispatch transition).
- Same shape + depth as `Use-The-Memory-Skill.md`.

**4. New ADR** at `crickets/wiki/explanation/decisions/0008-diataxis-author.md`:

- Locked design calls from this design (Q1-Q4 + key Tech Debt items + load-bearing assumptions).
- Distinct from harness-side ADR 0004 (which is the *Diátaxis spec*; this ADR is the *skill design*).
- Same shape as ADR 0007 (MemoryVault Discovery + Mining): Status + Date + Related; Context; Decision (with rationale per call); Consequences (positive / negative / load-bearing assumptions with re-audit triggers); Related.

**5. CHANGELOG + Completed-Features updates** + paired release pair:

- Toolkit CHANGELOG `v0.11.0` entry (Minor — discovery + maintenance via diataxis-author skill).
- Harness CHANGELOG `v2.4.3` entry (Patch — paired-doc-only; 4th consecutive paired-release-as-documentation pair after v2.4.0/v2.4.1/v2.4.2).
- Harness Completed-Features.md row + narrative.
- MemoryVault parent design (if relevant): no new row needed; diataxis-author is a sibling design, not a MemoryVault extension.
- Tag + GH release for both repos via `gh release create`.

**6. Plan close-out**:

- Parent design transitions `final → launched` (per `/design` lifecycle — automatic when last part's PLAN.md hits Status: done).
- Archive PLAN.md to `.harness/PLAN.archive.YYYYMMDD-diataxis-author.md`.
- Move ROADMAP item #13 to Completed section with full narrative.

## Tasks (DRAFT — refine via `/plan` when promoted)

1. Wire AgentMemory read-side: `scripts/` modules load `_always-load/diataxis-*.md` at invocation.
2. Wire AgentMemory write-side: `confirm_diataxis_convention_save()` helper (reuses permeable_boundary contract); offer-to-save during author / repair / classify.
3. Write initial seed for `_always-load/diataxis-*.md` (3 entries: filename-style, mode-mixed-split, ADR 0004 cross-ref).
4. Harness `/release` phase spec amendment + adapter files updated.
5. Write `wiki/how-to/Use-Diataxis-Author.md`.
6. Write `wiki/explanation/decisions/0008-diataxis-author.md`.
7. Toolkit CHANGELOG `v0.11.0` entry + harness CHANGELOG `v2.4.3` entry + harness Completed-Features.md row + narrative.
8. Tag v0.11.0 (toolkit) + v2.4.3 (harness); `gh release create` both with cross-links.
9. Plan close-out: archive PLAN.md, ROADMAP item #13 → Completed, parent design status `final → launched`.
10. Local verification + push + CI wake (both repos).

## Verification criteria

1. AgentMemory read works on a fresh vault: skill loads default conventions (no `_always-load/diataxis-*.md` entries) → falls back to ADR 0004 defaults.
2. AgentMemory write works: operator says "save this as a convention" during `/diataxis author` → permeable-boundary confirmation fires → entry lands at `_always-load/diataxis-<slug>.md`.
3. Per-repo `.diataxis-conventions.md` override works: skill reads global vault conventions THEN overrides with per-repo file when present.
4. Harness `/release` phase spec: `documenter` dispatch transitions correctly (verifiable via fixture-install on a project with diataxis-author installed vs. without).
5. how-to + ADR 0008 + CHANGELOG entries clean `check-wiki.py --strict`.
6. CI green on 3-OS for both toolkit + harness release commits.
7. `gh release create` returns both release URLs.
8. PLAN.md archived; ROADMAP entry moved; parent design transitions to `launched`.

## Out of scope

- Hooks integration (SessionStart surface; UserPromptSubmit auto-dispatch) — deferred to a v2 task per parent design's §8 Hooks Integration.
- Predecessor `migrate-to-diataxis` file removal from harness — separate follow-up release after dogfood (predecessor stays through v1 dogfood window per Migrations §1).
- Cross-skill integration with other roadmap items (#19 Ideas.md format; #20 transfer-context; #21 harness self-audit; #22 cross-surface; #23 auto-orchestration) — sibling work; diataxis-author ships independently.

## Locked design calls (inherited)

- All 4 (Q1-Q4) per parent design.
- Per parent design's Documentation Plan + Launch Plans + Migrations §2/§3/§4.

## Risks / Open questions

- **AgentMemory write fatigue** (Tech Debt §4): only offer write-back when (a) operator made a non-trivial decision (not just default-accept) AND (b) the decision diverges from existing conventions. `MEMORY_REVIEW_MODE=silent` env var for zero-prompt operators.
- **Paired release cadence**: continues 3-pair pattern from v2.4.0/v2.4.1/v2.4.2. v0.11.0 + v2.4.3 is the 4th consecutive paired-release-as-documentation pair.
- **ADR 0008 numbering**: next available number toolkit-side (ADR 0007 was just shipped for MemoryVault Discovery + Mining in v0.10.0; 0008 is the next slot). Verify at /plan time.
