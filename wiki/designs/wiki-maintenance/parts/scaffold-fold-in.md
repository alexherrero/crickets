---
title: "Scaffold, fold-in & rename: src/wiki → src/wiki-maintenance"
status: draft
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-04
updated: 2026-06-04
last_major_revision: 2026-06-04
prd:
project: https://github.com/users/alexherrero/projects/5
parent_design: ../../wiki-maintenance-design.md
part_slug: scaffold-fold-in
dependencies: []
estimated_scope: M
---

# Scaffold, fold-in & rename: `src/wiki` → `src/wiki-maintenance`

## Scope

The foundational, broad-but-mechanical part: turn the thin `src/wiki/` stub into the real `wiki-maintenance` group with its primitives folded in.

- **Group rename + composition flip.** `src/wiki/` → `src/wiki-maintenance/`. Flip `group.yaml` from the inherited `requires: [developer-workflows]` / `standalone: false` to `requires: []` / `standalone: true` + a capability-targeted `enhances: [{group: developer-workflows, capability: documentation, effect: …}]`; re-categorize `Coding` → `documentation`. The plugin *group* is `wiki-maintenance`; `wiki-author` is the authoring/learning *skill* inside it (resolves the group==skill name collision).
- **Bucket-A fold-in — copy-not-move, parallel-run.** Copy the wiki-owned primitives from agentm into `src/wiki-maintenance/`: the `wiki-author` + `diataxis-author` skills (including their `scripts/` + `templates/`), the `documenter` agent, `check-wiki.py`, `recent-wiki-changes`, and the `diataxis-evaluator` agent. The agentm copies **stay** (parallel-run) until the V5 ⑤ slim deletes them *after this proves out*.
- **Bucket B is explicitly NOT folded.** `harness_memory.py` / `repo_registry.py` / `agentm_config.py` are kernel-resident shared infra — the plugin depends on them with graceful-skip; vendoring them would orphan and diverge.
- **Regenerate `dist/`.** Run `scripts/generate.py` to emit `dist/<host>/plugins/wiki-maintenance/` for both hosts (Claude Code + Antigravity `agy`), plus the marketplaces + root pointer. The old `wiki` plugin leaves the marketplaces/default-set; `wiki-maintenance` takes its place. Update the test suite to match the new group name + shape.

## Dependencies

None — this is the foundational part. Every other part builds on the scaffolded group + folded-in primitives.

## Verification criteria

- `src/wiki-maintenance/group.yaml` carries `requires: []`, `standalone: true`, the `enhances` edge targeting `developer-workflows`'s `documentation` capability, and `category: documentation`.
- All five wiki-owned primitives (`wiki-author`, `diataxis-author`, `documenter`, `check-wiki.py` + `recent-wiki-changes`, `diataxis-evaluator`) are present under `src/wiki-maintenance/`, with `scripts/`/`templates/` intact and `__pycache__/*.pyc` excluded from the bundle.
- The agentm copies are untouched (parallel-run preserved; no premature deletion).
- `dist/` regenerates clean for both hosts; the marketplaces + root pointer reference `wiki-maintenance`, not `wiki`.
- `bash scripts/check-all.sh` is green (syntax · references · adapters · parity · lib-parity · no-pii · wiki + unit suite + verify-v4).
- **Wake-on-CI before marking `[x]`** — this touches the generator + committed `dist/`, so confirm CI green across the OS matrix first.

## Parent design

This part implements one slice of [Wiki-Maintenance — an opinionated, template-driven wiki maintainer](../../wiki-maintenance.md) (`Status: final`). See the parent for Context, Alternatives Considered, Quality Attributes overview, and Operations strategy. Mid-execution changes to this part's scope must be appended to the parent's Document History.
