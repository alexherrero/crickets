---
title: "Ship the wiki-sync workflow template + reference the bundled gate"
status: draft
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-10
updated: 2026-06-10
last_major_revision: 2026-06-10
prd:
project: https://github.com/users/alexherrero/projects/5
parent_design: ../../wiki-maintenance-provisioning.md
part_slug: wiki-sync-template
dependencies: []
estimated_scope: S-M
---

# Ship the wiki-sync workflow template + reference the bundled gate

## Scope

Add `templates/workflows/wiki-sync.yml` — crickets' own 72-line publisher, parameterized to be repo-agnostic (no hard-coded owner/repo; the default-branch + `wiki/**` trigger + the case-insensitive dupe-check kept verbatim). The job is opinionated-named **`[W] Update Wiki`**, matching crickets' own publisher and the `[W]` badge convention.

Wire the **gate by reference, not by copy**: a provisioned repo's CI invokes the plugin-bundled `${CLAUDE_PLUGIN_ROOT}/scripts/check-wiki.py` so an upgrade re-points for free and nothing drifts (a `--vendor` mode + a `wiki-init --resync-gate` step cover repos that must vendor). Resolve the open debt this surfaces: `check-wiki.py` is triple-vendored in crickets (`scripts/check-wiki.py` · `src/wiki-maintenance/scripts/check-wiki.py` · the bundled `dist/` copy) — pick a single source so the repo gate and the plugin gate can't diverge.

Covers Detailed Design §1 (template) + §3 (gate distribution).

## Dependencies

None — this is the foundational template + gate-distribution slice; `wiki-init` (part `wiki-init`) drops what this ships.

## Verification criteria

- `templates/workflows/wiki-sync.yml` exists, is repo-agnostic, and its job renders as `[W] Update Wiki` in a target's Actions list; the `wiki/**` trigger + case-insensitive dupe-check are preserved verbatim.
- A provisioned repo's CI step invokes the **bundled** gate (`${CLAUDE_PLUGIN_ROOT}/scripts/check-wiki.py` resolves), not a copied script.
- `check-wiki.py` is single-sourced — one canonical copy generated/bundled; `generate.py check` stays drift-free after the change.
- The full gate battery is green (`bash scripts/check-all.sh`).

## Parent design

This part implements one slice of [Wiki-Maintenance Provisioning Design](wiki-maintenance-provisioning) (`Status: final`). See the parent for Context, Alternatives Considered (vendor-vs-reference), Quality Attributes, and Operations. Mid-execution scope changes append to the parent's Document History.
