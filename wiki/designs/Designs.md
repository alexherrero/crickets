<!-- mode: index -->
# Designs

The architecture behind crickets and Agent M — the high-level design docs that explain *how* each system works, in depth. Each design's sub-parts live in this section's sidebar.

## What's here

**Crickets**

- **[Crickets v3.0 — Native Host Plugins](crickets-v3-native-plugins)** — the `src/` → generate → `dist/` model.
- **[Developer Plugin Suite](developer-plugin-suite)** — the developer-workflows / safety / code-review split + `enhances:`.
- **[Wiki Maintenance](wiki-maintenance-design)** — the diataxis-author + documenter + wiki-watcher system.
- **[diataxis-author](diataxis-author)** — the authoring + style-learning skill.
- **[Continuous Integration](continuous-integration)** — the gate battery · the 3-OS matrix · the PII layers.
- **[Wiki](wiki-design)** — the intent-grouped IA · per-folder sidebars · linting + publish.
- **[Wiki-Maintenance Provisioning](wiki-maintenance-provisioning)** — provision a target repo end-to-end (init · template-ship · gate distribution · standalone retirement).
- **[Wiki Section Taxonomy](wiki-section-taxonomy)** — the 7-section frame · per-project Architecture manifest · conditional sections · the two dogfood restructures.

**Architecture (Agent M)**

- **[MemoryVault](https://github.com/alexherrero/agentm/wiki/memoryvault)** — permanent agent memory.
- **[Agent Memory Evolution V1→V7](https://github.com/alexherrero/agentm/wiki/agent-memory-evolution)** · **[Device-Wide Architecture](https://github.com/alexherrero/agentm/wiki/device-wide-architecture)** · **[Memory-OS (V5)](https://github.com/alexherrero/agentm/wiki/memory-os-architecture)**.

## Recent changes

<!-- maintained by the wiki tooling -->

- **2026-06-08** — moved to `designs/`; this index added.
- **2026-06-09** — Continuous Integration + Wiki designs added; the four earlier designs updated to shipped reality; Wiki Maintenance is now launched.

## See also

[Reference](Reference) · [Decisions](Decisions) · [Why it works](Why-It-Works) · [Home](Home)
