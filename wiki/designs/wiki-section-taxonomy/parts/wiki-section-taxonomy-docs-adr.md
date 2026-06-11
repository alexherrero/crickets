---
title: "Docs + the taxonomy ADR"
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
part_slug: docs-adr
dependencies: [static-frame, architecture-manifest, render-and-gate]
estimated_scope: S
---

# Docs + the taxonomy ADR

## Scope

Document the shipped taxonomy and record its decisions:

- Update `diataxis-author/templates/README.md` §3 (the authoring spec) for the 7-section frame, the Architecture nesting level, and the conditional-section rules.
- A how-to — **"Declare a project's Architecture"** — writing `wiki/architecture.yml`, the recurring-pillar toggles, what the generator scaffolds.
- Update the [Wiki design](wiki-design) (taxonomy joins provisioning + authoring).
- An **ADR** for the three load-bearing calls — the 7-section frame, the per-project Architecture manifest (vs hard-coded sub-sections), and the conditional-section gates (Architecture-on-declaration, Operational-on-visibility) — each with its re-audit trigger. Register it in `Decisions.md` + `decisions/_Sidebar.md`.

Covers the parent's Documentation Plan.

## Dependencies

- **static-frame · architecture-manifest · render-and-gate** — documents the generator surface those parts ship; the ADR records the calls once the mechanic is built.

## Verification criteria

- README §3 describes the 7-section frame + Architecture nesting + conditional gates.
- The how-to walks writing `architecture.yml` end-to-end.
- The ADR records the three calls with explicit "why not" + re-audit triggers, registered in `Decisions.md` and `decisions/_Sidebar.md`.
- The [Wiki design](wiki-design) reflects the taxonomy joining provisioning + authoring.
- `check-wiki.py` green.

## Parent design

This part implements the Documentation Plan of [Wiki Section Taxonomy Design](../../wiki-section-taxonomy.md) (`Status: final`). The ADR follows the operator-locked shape (`> [!NOTE]` Status/Date · Context · Decision with "why not" · Consequences with re-audit triggers · Related). Mid-execution scope changes append to the parent's Document History.
