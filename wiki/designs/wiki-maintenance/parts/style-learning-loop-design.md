---
title: "Style layer + the learning loop"
status: draft
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-04
updated: 2026-06-04
last_major_revision: 2026-06-04
prd:
project: https://github.com/users/alexherrero/projects/5
parent_design: ../../wiki-maintenance.md
part_slug: style-learning-loop-design
dependencies: [scaffold-fold-in]
estimated_scope: L
---

# Style layer + the learning loop

## Scope

The real new work — the voice layer and the operator-in-the-loop mechanism that grows it.

- **Base style-guide artifact.** A new base artifact alongside the inherited `diataxis-author/templates/*.md`: the operator's house voice (human-first, slop-free, jargon-free, register), seeded from the existing `docs-prose-style` conventions. Templates fix *structure*; the style guide fixes *voice*.
- **Edit-driven generalization capture.** Add an edit-driven path to the existing decision-driven capture in `diataxis-author`: operator edits a drafted page → the skill **diffs** draft vs edited, **clusters** changes by kind (word choice · rhythm · structure · cuts = slop/jargon removed · additions) → for each cluster proposes a **generalizable voice lesson** `{trigger/scenario, scope, guidance, before→after example}` → **confirms generality with the operator** ("I read this as: *in any X, prefer Y* — right, narrower, or broader?"). Never auto-committed.
- **The `style-scope-evaluator` sub-agent (new, read-only).** Recommends where each confirmed lesson belongs — **global / per-project / per-repo** — which the operator confirms. Two operator gates total: generality (operator-validated) and scope (evaluator-recommended, operator-confirmed). Writes the confirmed lesson to that scope's on-demand store via the existing `agentmemory_conventions.py` capture path.
- **`_always-load` → on-demand relocation.** Move the global Diátaxis conventions out of `_always-load/diataxis-*.md` (which injects into *every* session) into a global **on-demand** store (a reserved `_global` slug the resolver reads via its existing per-project path). Operator-vault data → **preview-first, reversible operator-run step**.
- **`convention-drift`: stub → live.** Wire the currently-stubbed `diataxis/convention-drift` check live against the style overlay so `check-wiki.py` / `/diataxis check` flags *voice* drift, not just structural violations.

## Dependencies

- **`scaffold-fold-in`** — needs the folded-in `diataxis-author` skill + its templates/scripts (the learning loop lives in `diataxis-author`; the capture path reuses `agentmemory_conventions.py`).

## Verification criteria

- The base style-guide ships in `src/wiki-maintenance/` and is read at author time as part of `template ⊕ base style-guide ⊕ overlay` (precedence: vault → project → repo, narrower + recent wins).
- An edit-driven capture run produces a confirmed lesson written to the operator-selected scope's on-demand store — not `_always-load`.
- The `style-scope-evaluator` is read-only (no writes) and recommends one of global / per-project / per-repo.
- The `_always-load` → on-demand relocation is **preview-first + reversible** (`--rollback`, mirroring `migrate-harness-to-vault`); the only readers (the wiki primitives via the resolver) switch to the relocated location.
- `convention-drift` surfaces voice-drift findings (findings, not hard failures — unless `--strict`).
- Deterministic parts (resolver read, scope precedence, capture write) are unit-tested under `bash scripts/check-all.sh`.

## Parent design

This part implements one slice of [Wiki-Maintenance — an opinionated, template-driven wiki maintainer](../../wiki-maintenance.md) (`Status: final`). See the parent for Context, Alternatives Considered, Quality Attributes overview, and Operations strategy. Mid-execution changes to this part's scope must be appended to the parent's Document History.
