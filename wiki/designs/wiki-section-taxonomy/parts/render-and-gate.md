---
title: "Nested Architecture render + the Operational visibility gate"
status: draft
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-10
updated: 2026-06-10
last_major_revision: 2026-06-10
prd:
project: https://github.com/users/alexherrero/projects/5
parent_design: ../../wiki-section-taxonomy.md
part_slug: render-and-gate
dependencies: [static-frame, architecture-manifest]
estimated_scope: M
---

# Nested Architecture render + the Operational visibility gate

## Scope

Two render-layer changes:

1. **The third nesting level (DD §3).** The root `_Sidebar.md` Architecture entry expands into its declared components, each linking to its overview page — a third level on top of the existing two-level per-folder-sidebar model ([ADR 0018](0018-per-folder-sidebars)). Per-component folders still get their own `_Sidebar.md` for the pages *within* a component (GitHub Wiki renders the nearest sidebar). This is the only new render mechanic.
2. **The Operational visibility gate (DD §4).** Operational renders only when `--visibility != public` — both `private` and `internal` are non-public (the distinction is audience, not content-sensitivity; both get Operational); `public` and `unknown` suppress it.

## Dependencies

- **static-frame** — gates the frame's two conditional sections.
- **architecture-manifest** — renders the ordered component list the manifest produces.

## Verification criteria

- The rendered root sidebar shows the nested Architecture block with one sub-entry per declared component, in manifest order.
- `public` suppresses Operational; `private` and `internal` render it; `unknown` suppresses (conservative).
- Per-component `_Sidebar.md` is still rendered for intra-component pages.
- Battery green (render fixtures: no-manifest · single-component · recurring-pillars · public-vs-private-vs-unknown).

## Parent design

This part implements DD §3 + §4 of [Wiki Section Taxonomy Design](../../wiki-section-taxonomy.md) (`Status: final`). See the parent for the nested-render and visibility-gate rationale. Mid-execution scope changes append to the parent's Document History.
