---
page-template: plugin-home
sections:
  - intro
  - get-started
  - task-scenarios
  - plugin-composition
  - why-it-works
  - contribute
  - see-also
---
<!--
  PAGE TEMPLATE: plugin-home — the per-plugin page (one per shipped plugin), a
  COLLECTION OF SECTIONS. The `sections:` list IS the page: each name resolves to
  templates/sections/<name>.md and composes in that order. Author a plugin page by
  editing the list — drop sections that don't apply, reorder freely.

  This is the wave-2 target: each shipped plugin (developer-workflows,
  developer-safety, code-review, github-ci, pii, wiki-maintenance) gets one page on
  this shape. The GENERIC structure they instantiate is the [Plugin anatomy]
  reference; a plugin page is the SPECIFIC instance — what THIS plugin is, ships,
  composes with, and how to install it.

  Cross-cutting opinions a plugin page enforces:
    - intro says what the plugin IS in one plain paragraph (no marketing)
    - "do" organizes by user intent (task-scenarios), not a primitive dump
    - composition states standalone / requires / enhances explicitly + host reach
    - user-facing body; authoring/contributor detail → Modify-a-plugin + the sidebar
    - plain, present-tense prose (the `user-facing-prose` voice lesson)

  FOLLOW-UP (not built yet): the composer (§6) reads this manifest, loads each
  section, applies the resolved voice (base ⊕ overlay) + the target language, and
  concatenates. Until then this manifest is the spec + the assembly order; author
  from the section files directly.
-->
