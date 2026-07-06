---
title: <Replace with descriptive title>
status: draft
kind: design
scope: arc
area: <shared/foundations | <repo>/architecture | ...>
governs:
  - <glob or path this design governs, e.g. scripts/**>
children:
  - <child-design-filename.md>
seeded: <YYYY-MM-DD>
approved: <YYYY-MM-DD or leave empty>
---

<!--
  crickets architecture-hld template (v0.1.0) -- the multi-system /
  parent-HLD rung, generalized from agentm's `agentm-hld.md` +
  `agentm-foundations-hld.md` (the AG HLD set).

  A THIRD rung alongside the full 10-section design-doc template and the
  abbreviated-design template: for a design that composes multiple
  sub-designs (a parent-of-children HLD) or spans multiple systems, not a
  single-system feature/capability.

  `children:` IS the composition claim -- every filename listed there is a
  sibling design this doc composes. `/design finalize`'s stale-placeholder
  check + a dedicated `architecture_rung.py review` pass verify every
  declared child actually resolves to a real file (a dangling child is a
  broken composition claim, caught mechanically).

  Design call (documented, not silently decided): the two real precedent
  docs each state their cross-system relationship in doc-specific prose
  ("How agentm and crickets work together", "How it all connects") --
  there is no single generic heading string both share verbatim, so this
  template names its own two slots generically ("Composition" and
  "Architecture review") for NEW docs authored through it, rather than
  requiring an exact heading match against prose that predates this
  template. `architecture_rung.py`'s own composition-analysis + review
  logic works off the `children:`/`governs:` frontmatter, not section
  headings, so it applies identically to a doc using this template's
  generic headings and to a real doc using its own descriptive prose.
-->

# <Replace with title>

## Objective

*What problem does this multi-system design solve, and why does it need a parent-of-children (or cross-system) shape rather than a single design doc? 3-4 plain sentences, max.*

## Composition

*How do the systems/children this design composes relate to each other? Name the dependency direction explicitly if there is one (e.g. "crickets may lean on agentm; agentm never leans on crickets") -- this is the doc's composition claim, the prose counterpart to the `children:`/`governs:` frontmatter above.*

<!--
  Real precedent: agentm-hld.md's "How the pillars fit together" section;
  agentm-foundations-hld.md's "How agentm and crickets work together"
  section. Name this section whatever reads best for the specific systems
  involved -- "Composition" is this template's generic default, not a
  required literal heading.
-->

## Architecture review

*How does the composition hold together end to end -- what would break if one child/system changed, and what's the reader's path through the pieces?*

<!--
  Real precedent: agentm-hld.md's "How the pillars fit together" +
  agentm-foundations-hld.md's "How it all connects" sections. This is the
  doc's own narrative review; `architecture_rung.py review <path>` is the
  separate, mechanical review that every declared `children:` entry
  actually resolves -- the two complement each other, prose for the reader,
  the script for CI.
-->

## Dependencies

*What does this design depend on? Internal services, libraries, teams, other designs.*

## Risks & open questions

*Known compromises, open decisions, and what would trigger a re-audit. `[PENDING-IMPL]` markers for designed-but-unbuilt pieces are expected here -- `/design finalize` flags a stale one rather than silently collapsing over it.*

## References

*Citations to code + linked designs (including every `children:` entry, cross-referenced with a one-line gloss of what each child owns).*

## Amendment log

*Dated entries, newest first, tracing the design's evolution -- what changed, why, and the re-audit trigger it names (if any). `/design finalize` auto-collapses same-day entries into one row telling that day's whole story, mirroring the full design-doc template's Document History consolidation convention.*

**<YYYY-MM-DD>** — Initial draft created via `/design author --rung architecture`.
