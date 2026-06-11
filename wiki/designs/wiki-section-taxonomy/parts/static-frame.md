---
title: "The static 7-section frame"
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
part_slug: static-frame
dependencies: []
estimated_scope: M
---

# The static 7-section frame

## Scope

Reshape the outline source in `src/wiki-maintenance/scripts/wiki_init.py`:

- `DEFAULT_SECTIONS` becomes the ordered seven: `how-to · reference · architecture · designs · explanation · decisions · operational`.
- `SECTION_META` carries the two renames — `do→how-to` (reversing `do→Do`) and `why→explanation` (reversing `why→Why-It-Works`) — with Get-Started/Tutorials folding into How-to.
- `architecture` and `operational` are tagged **conditional** (a `CONDITIONAL_SECTIONS` set, or a fourth tuple field) so the renderer can suppress them when a project doesn't declare Architecture / isn't private.
- Update `check-wiki.py` so the new intent-folder basenames pass the lint gate; the retired `get-started/do/why` basenames stop being valid.

Basenames keep mirroring crickets' own wiki so the no-op invariant holds. This is the foundation every other part renders against — no manifest reader, no nested render, no dogfood yet.

## Dependencies

None — foundational. The frame must exist before the manifest (#2) has an `architecture` slot to populate or the renderer (#3) has a frame to gate.

## Verification criteria

- `DEFAULT_SECTIONS` is the ordered seven; `SECTION_META` carries the renamed basenames + titles.
- `architecture` and `operational` are tagged conditional; a render with neither declared emits exactly the five always-present sections.
- `check-wiki.py` accepts the new intent-folder set and rejects the retired `get-started/do/why` basenames.
- Battery green (unit tests over the reshaped frame).

## Parent design

This part implements DD §1 of [Wiki Section Taxonomy Design](../../wiki-section-taxonomy.md) (`Status: final`). See the parent for Context, Alternatives, and the no-op-invariant risk. Mid-execution scope changes append to the parent's Document History.
