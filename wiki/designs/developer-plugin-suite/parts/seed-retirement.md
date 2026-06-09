---
title: "Retire developer seed + sibling re-point + suite dogfood"
status: draft
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-03
updated: 2026-06-03
last_major_revision: 2026-06-03
prd:
project:
parent_design: ../../developer-plugin-suite.md
part_slug: seed-retirement
dependencies: [developer-workflows, developer-safety, code-review]
estimated_scope: M
---

# Retire `developer` seed + sibling re-point + suite dogfood

## Scope

The closeout once all three plugins exist:

- **Retire the `#40` `developer` seed group** — its control hooks now live in `developer-safety`, its `evaluator` agent in `developer-workflows`.
- **Re-point siblings** — `src/wiki` + `src/github-ci` `requires: [developer]` → `[developer-workflows]`. Regenerate `dist/`; `generate.py check` clean.
- **Suite dogfood DoD (composition matrix)** — prove the suite on agentm / crickets / sherwood: each plugin **alone** + every combination (workflows-only · +safety · +code-review · all three). Assert graceful-skip *and* enhancement in each.

**Out of scope (explicit):** removing agentm's baked-in workflow/docs/PM copies — that **slim is V5 bucket ⑤**, gated on this dogfood proof. Parallel-run holds until then; this part never touches agentm internals.

## Dependencies

- **developer-workflows**, **developer-safety**, **code-review** — all three must exist before the seed retires and the suite-wide composition matrix can run.

## Verification criteria

- The `developer` seed group is removed from `src/`; **no dangling `requires: [developer]`** remains (`wiki` + `github-ci` re-pointed to `developer-workflows`).
- `generate.py check` clean after regeneration.
- **Composition matrix green**: each plugin loads alone, and every combination behaves correctly (safety hooks engage with workflows; `/review` upgrades with code-review; each degrades gracefully when a partner is absent).
- Dogfooded on agentm / crickets / sherwood.
- agentm's baked-in copies are **untouched** (verified — the slim is V5 ⑤, not this part).

## Parent design

This part implements one slice of [Developer Plugin Suite](../../developer-plugin-suite.md) (`Status: final`) — Detailed Design §6. See the parent for Context, Alternatives Considered, Quality Attributes, and Operations. Mid-execution scope changes must be appended to the parent's Document History.
