---
title: "Dogfood: restructure crickets' wiki (the no-op lock)"
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
part_slug: crickets-dogfood
dependencies: [static-frame, architecture-manifest, render-and-gate]
estimated_scope: M
---

# Dogfood: restructure crickets' wiki (the no-op lock)

## Scope

Restructure crickets' own `wiki/` in place to the new frame:

- Move `do/→how-to/`, `why/→explanation/`, and absorb `plugins/` into `architecture/plugins/`.
- Author crickets' `wiki/architecture.yml` with its five pillars: **plugins · customization-model · build-and-distribution** (PII guardrails fold in here) **· host-adapters · harness-interface** (↔ Agent M).
- Reorder the root + per-folder sidebars to the 7-section frame (How-to · Reference · Architecture · Designs · Explanation · Decisions; Operational suppressed — crickets is public).

The **lock**: after the restructure, `wiki-init` against crickets must be a verified no-op — `SECTION_META` + crickets' `architecture.yml` must render exactly the hand-built result. Add a battery check asserting the rendered crickets sidebar matches the generator output (Risk #3's mitigation). This part is what proves surfaces 1 (generator) and 2 (sidebars) agree.

## Dependencies

- **static-frame · architecture-manifest · render-and-gate** — the full generator surface must exist before crickets can be restructured to match it and the no-op proven.

## Verification criteria

- crickets' `wiki/` renders the 7-section frame; `do/`, `why/`, and standalone `plugins/` are gone/absorbed; the five Architecture pillars exist with landings.
- `wiki-init --preview` against crickets reports a no-op (nothing to create or change).
- The new battery check (rendered crickets sidebar == generator output) passes.
- `check-wiki.py` green on the restructured tree.

## Parent design

This part implements the first half of DD §5 of [Wiki Section Taxonomy Design](../../wiki-section-taxonomy.md) (`Status: final`) — the no-op-invariant lock (Risk #1). See the parent for why the dogfood *is* the lock, not just validation. Mid-execution scope changes append to the parent's Document History.
