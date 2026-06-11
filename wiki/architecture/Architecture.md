<!-- mode: index -->
# Architecture

The structural component map — how crickets is built. Five components, each a folder under `architecture/`. These pages link *out* to [Reference](Reference) for the field-level detail rather than duplicating it.

## What's here

- **[Plugins](Plugins)** — the shipped plugins (developer-workflows · developer-safety · code-review · github-ci · wiki-maintenance · pii) and what each contains.
- **[Customization model](Customization-Model)** — the primitive types (skills · commands · agents · hooks · …) and the `enhances:` soft-composition model that lets plugins layer.
- **[Build & distribution](Build-And-Distribution)** — how `src/` is generated into committed `dist/` native host plugins and shipped (bootstrap · marketplace · `--plugin-dir`).
- **[Host adapters](Host-Adapters)** — the per-host surface mapping (Claude Code · Antigravity) and where each primitive lands.
- **[Harness interface ↔ Agent M](Harness-Interface)** — the seam between this toolkit and the sibling `agentm` harness: what each owns and how they compose.

## Recent changes

<!-- maintained by the wiki tooling -->

- **2026-06-11** — Architecture section introduced (wiki-section-taxonomy dogfood); `plugins/` folded in as the first component, four more components added.

## See also

[Reference](Reference) · [How-to](How-To) · [Home](Home)
