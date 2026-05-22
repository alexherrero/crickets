---
parent_design: ../../diataxis-author.md
part_slug: migrate-subsume
title: "Migrate subsume — /diataxis migrate ports the predecessor + ships deprecation notice"
status: pending
visibility: published
author: alex
contributors: []
created: 2026-05-22
updated: 2026-05-22
last_major_revision: 2026-05-22
dependencies: [skill-scaffold]
estimated_scope: M
plan: "13-part-2"
prd:
project:
---

# Migrate subsume — `/diataxis migrate` ports the predecessor + ships deprecation notice

**Parent design:** [diataxis-author](../../diataxis-author.md) — see Detailed Design §4 (`/diataxis migrate`) for sub-command contract; Migrations §1 for predecessor deprecation; Tech Debt §5 for single-commit safety net.

## Scope

`/diataxis migrate` ports the existing `migrate-to-diataxis` predecessor (~250 lines in `agentic-harness/harness/skills/migrate-to-diataxis.md`) into agent-toolkit's `diataxis-author` skill. Same contract: preview-first, deterministic classification by heading shape per ADR 0004, `git mv` for blame preservation, mode-mixed pages flagged for human split (delegates to `/diataxis repair` for the actual split — but `/diataxis repair` doesn't exist yet in part 2, so part 2 flags + exits + tells operator to wait for part 4), link rewrites across all `wiki/**/*.md` files. Adds: single-commit safety net (entire migration is one git commit so revert is one `git revert <SHA>`); writes per-repo `wiki/.diataxis-conventions.md` capturing detected conventions; subprocess-call shape into `scripts/check-wiki.py` for post-migration verification (graceful-skip if predecessor isn't installed harness-side).

**Predecessor deprecation**: harness's `migrate-to-diataxis.md` skill body gets a deprecation header — on invocation, prints `[migrate-to-diataxis] DEPRECATED: this skill has been subsumed by agent-toolkit's diataxis-author. Use '/diataxis migrate' instead. This skill will be removed in a future harness release.` Exits non-zero. Operators with existing harness installs see the notice + manually run `/diataxis migrate`. The actual file removal lands in a follow-up harness PATCH release (out of scope for this part — captured in [FOLLOWUPS](../../../../../../agentic-harness/.harness/FOLLOWUPS.md) or as a small follow-up plan post-dogfood).

## Scripts shipped

- `agent-toolkit/skills/diataxis-author/scripts/migrate.py` (~280 lines — port of predecessor logic; Python rather than agent-prose since the deterministic classification benefits from regex compilation + unit-testable shape).
- The skill body's `## /diataxis migrate` sub-section (currently a stub) gets the full 9-step flow + invocation shape + examples.

## Tasks (DRAFT — refine via `/plan` when promoted)

1. Write `scripts/migrate.py` porting predecessor classification rules + preview + link-rewrite + git-mv flow.
2. Update SKILL.md `## /diataxis migrate` sub-command body (from stub to full 9-step flow).
3. Add deprecation header to harness `migrate-to-diataxis.md` skill body.
4. Write smoke install tests (bash + pwsh): fixture legacy-wiki dir + run `/diataxis migrate --preview` + assert classification correctness + assert no destructive writes; then `--execute` + verify `git mv` operations + `.diataxis` marker + `.diataxis-conventions.md` auto-seed.
5. Local verification + push + CI wake.

## Verification criteria

1. Fixture legacy-wiki (3+ pages in old `development/operational/design/architecture` layout) migrates cleanly via `/diataxis migrate --execute`.
2. Mode-mixed page in fixture flagged for human split (status: "needs human split").
3. Single commit covers the entire migration (verifiable via `git log --stat`).
4. `wiki/.diataxis` marker + `wiki/.diataxis-conventions.md` auto-seeded.
5. Predecessor `migrate-to-diataxis.md` (harness-side) emits deprecation notice + exits non-zero when invoked.
6. Smoke install + check-syntax + check-no-pii clean on 3-OS CI.

## Out of scope

- Removal of the harness's `migrate-to-diataxis.md` file (follow-up harness release; deprecation notice is enough for this part).
- `/diataxis repair` interactive flow for mode-mixed splits — handled in part 4.
- AgentMemory write-back of operator-decided splits during migration — handled in part 5.

## Locked design calls (inherited)

- Q1 scope = author + maintain + migrate (this part is the migrate piece).
- Per parent design's Migrations §1: subsume predecessor; deprecation notice + manual operator migration; predecessor removal in follow-up harness release after dogfood.

## Risks / Open questions

- **Harness/toolkit cross-repo coordination**: part 2 touches both repos (toolkit ships /diataxis migrate; harness ships deprecation notice). Sequence: toolkit commit first (so /diataxis migrate exists when the deprecation notice tells operators to use it), then harness commit. Cross-repo testing: smoke install both + verify deprecation notice fires.
- **Predecessor migration testing**: ideally run the new `/diataxis migrate` against a clone of the *agentic-harness* repo's pre-Diátaxis wiki state (preserved in git history) as a dogfood test. Operator may want to do this manually as a v1 validation step before public release.
