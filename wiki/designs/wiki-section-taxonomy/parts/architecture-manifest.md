---
title: "The per-project Architecture manifest"
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
part_slug: architecture-manifest
dependencies: [static-frame]
estimated_scope: M
---

# The per-project Architecture manifest

## Scope

Teach `wiki_init.py` to read a net-new per-repo manifest — `wiki/architecture.yml` — since the generator reads no per-repo config today (it's CLI-flag-driven). The manifest lists each large component as `{slug, title, summary, overview}` plus an optional `pillars:` list of recurring toggles (`host-adapters · sibling-interface · distribution`). The generator:

- expands each `pillars:` toggle to its known component template;
- scaffolds `architecture/<slug>/` + a section landing (built from `summary` + `overview`) per `components:` entry;
- exposes the ordered component list to the sidebar renderer (consumed in #3).

The block is **validated** (required keys per component; known pillar names) and **fails closed** with a clear error rather than scaffolding garbage. An absent/empty manifest suppresses the Architecture section entirely (conditional gate #1).

## Dependencies

- **static-frame** — needs the `architecture` section slot + the conditional tagging the frame introduces, so an absent manifest cleanly suppresses the section.

## Verification criteria

- A fixture `architecture.yml` with N components scaffolds N `architecture/<slug>/` folders + landings, in manifest order.
- `pillars:` toggles expand to their known templates.
- A malformed manifest (missing required key / unknown pillar) fails closed with a clear error and scaffolds nothing.
- An absent/empty manifest suppresses the Architecture section.
- Battery green (manifest-expansion fixtures).

## Parent design

This part implements DD §2 of [Wiki Section Taxonomy Design](../../wiki-section-taxonomy.md) (`Status: final`). The manifest is the design's real new surface — the mechanic that makes Architecture per-project. See the parent for the manifest-schema risk. Mid-execution scope changes append to the parent's Document History.
