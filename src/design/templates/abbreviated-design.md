---
title: <Replace with descriptive title>
status: draft
kind: design
scope: feature
area: <repo>/<capability>
parent: <parent-hld-filename.md, or leave empty for a standalone design>
seeded: <YYYY-MM-DD>
approved: <YYYY-MM-DD or leave empty>
---

<!--
  crickets abbreviated-design template (v0.1.0) -- today's AG shape-spec,
  packaged as a runnable `/design` template. The default rung most work
  lands on: a single-system capability or child design, smaller than the
  full 10-section design-doc template warrants.

  Seven sections (vs. the full template's ten): no Alternatives Considered,
  no Migrations, no Project management (work estimates/documentation
  plan/launch plans), no Operations subsections -- those collapse into
  Dependencies + Risks + References for a design at this scale. Ends with
  an Amendment log (dated, newest-first), not a Document History table --
  matches the real AG living-design corpus's own convention.

  Status lifecycle is identical to the full template: draft -> review ->
  final -> launched, `/design author`-managed.
-->

# <Replace with title>

## Objective

*What problem does this solve, and why now? 3-4 plain sentences, max. No N/A -- every design needs an objective.*

## Overview

*The shape of the design in 1-3 paragraphs -- what it is at a high level. A reader who doesn't know the codebase should get the shape from this section alone.*

## Design

*The actual substance -- subsections per component are fine. Probably the longest section.*

## Dependencies

*What does this design depend on? Internal services, libraries, other designs. N/A appropriate for fully self-contained changes; say so explicitly.*

## Risks & open questions

*Known compromises, open decisions, and what would trigger a re-audit. `[PENDING-IMPL]` markers for designed-but-unbuilt pieces are expected here -- `/design finalize` flags a stale one rather than silently collapsing over it. N/A is not appropriate here; every design has at least one risk.*

## References

*Citations to code + linked designs.*

## Amendment log

*Dated entries, newest first, tracing the design's evolution -- what changed, why, and the re-audit trigger it names (if any). `/design finalize` auto-collapses same-day entries into one row telling that day's whole story.*

**<YYYY-MM-DD>** — Initial draft created via `/design author --rung abbreviated`.
