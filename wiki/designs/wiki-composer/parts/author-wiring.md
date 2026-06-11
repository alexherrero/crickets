---
title: "Manifest dispatch + monolith fallback"
status: draft
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-11
updated: 2026-06-11
last_major_revision: 2026-06-11
prd:
project: https://github.com/users/alexherrero/projects/5
parent_design: ../../wiki-composer.md
part_slug: author-wiring
dependencies: [compose-core]
estimated_scope: S
---

# Manifest dispatch + monolith fallback

## Scope

Give `author.py` the dispatch that chooses compose-vs-verbatim — a single branch on the presence of a `sections:` frontmatter list:

- **`sections:` present** (`component-overview`, `home`, `plugin-home`, `section-index`) → **compose**: expand the list, run the pipeline, emit the assembled scaffold.
- **no `sections:`** (`how-to`, `tutorial`, `reference`, `explanation`) → **fallback**: today's verbatim `read_text()` + voice-comment injection, unchanged.

This is what lets the two shapes coexist (the resolved monolith fork). `/diataxis author <page-type>` routes to the same `author_page()` entry point; only the internal branch differs, so the command surface doesn't change. A manifest naming a section absent from the library, or a section file that won't parse, fails closed with the manifest + section name — never a partial page, mirroring the taxonomy's fail-closed manifest validation.

## Dependencies

Depends on `compose-core`: the compose branch calls `compose_page()`, so the dispatch is meaningless until the pipeline exists. Transitively needs `section-schema`.

## Verification criteria

- A manifest (`sections:` present) routes to compose; a monolith (no `sections:`) routes to verbatim emit — the four modes' output is byte-unchanged from today.
- The dispatch is a single branch sharing `author_page()`'s tail (voice injection, H1 handling) across both paths.
- A manifest naming an unknown section, or an unparseable section file, fails closed with the manifest + section name — no partial page.
- Existing monolith authoring is non-destructively preserved.
- Battery green.

## Parent design

This part implements DD §3 of [Wiki Composer Design](../../wiki-composer.md) (`Status: final`). See the parent for the verbatim-fallback-fork-can-rot risk (re-audit when the first monolith converts → the fork narrows; when the last does → it closes). Mid-execution scope changes append to the parent's Document History.
