---
page-template: home
sections:
  - hero
  - intro
  - get-started
  - task-scenarios
  - lookup
  - why-it-works
  - major-designs
  - decisions-index
  - contribute
---
<!--
  PAGE TEMPLATE: home / landing — a COLLECTION OF SECTIONS.

  The `sections:` list in the frontmatter IS the page: each name resolves to
  templates/sections/<name>.md and they compose in that order. Author a landing by
  editing the list — drop sections that don't apply, reorder freely. Every section
  but `hero` is reusable (`reusable: true` in its frontmatter), so it composes into
  other page types too — a per-plugin home, a project landing — authored once,
  used anywhere.

  Each section file carries its own purpose, shape, and baked-in opinion. The
  cross-cutting opinions a LANDING page enforces:
    - curated, not an exhaustive sitemap (completeness lives in the sidebar)
    - organize "do" by user intent (scenarios), not a how-to dump
    - long enumerations (decisions, design sub-parts) sit behind an index link
    - user-facing vs contributor-facing are separated (dev specs → sidebar/CONTRIBUTING)
    - plain, present-tense prose (see the `user-facing-prose` voice lesson)

  FOLLOW-UP (not built yet): a composer that reads this manifest, loads each
  section file, applies the resolved voice (base ⊕ overlay) and the target
  language, and concatenates them into the page. Until then this manifest is the
  spec + the human-readable assembly order; author from the section files directly.
-->
