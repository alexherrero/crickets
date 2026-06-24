<!-- mode: index -->
# Designs

The architecture behind crickets and Agent M — the high-level design docs that explain *how* each system works, in depth. Each design's sub-parts live in this section's sidebar.

## What's here

**Crickets**

- **[Crickets — High Level Design](crickets-hld)** — the live parent design: the thirteen-capability toolbox, build-once-generate-everywhere, and composition onto agentm. Reconciles the two designs below. All children content-final (AG Phase 3, 2026-06-24).
  - [Build system](crickets-build-system) — single source → per-host generated, drift gate, host-subset coverage.
  - [Composition](crickets-composition) — capability↔capability and capability↔opinion, the full relationship map, the one-way arrow onto agentm, role-retirement.
  - [Model + effort routing](https://github.com/alexherrero/agentm/wiki/agentm-model-effort-routing) — T0…T4 tier scale; persona→tier map; `tier:` manifest axis. *(agentm-parented; enforcement surface is crickets agent-defs.)*
  - [development-lifecycle](crickets-development-lifecycle) — the spine: setup / plan / work / review / release / bugfix + launch / deprecate / retire.
  - [code-review](crickets-code-review) — adversarial review, cross-model variant, `/code-review`.
  - [design](crickets-design) — design authoring: abbreviated / full / architecture rungs.
  - [developer-safety](crickets-developer-safety) — the recoverability gate: skill + hook + carve-out tests.
  - [wiki](crickets-wiki) — docs upkeep: diataxis-author + documenter + wiki-watcher.
  - [github-projects](crickets-github-projects) — board-sync: vault → board ≥4 deep, per-commit comment trail; driven by the Planner (TPM).
  - [maintenance](crickets-maintenance) — keep the codebase healthy: dependency repair, CVE, tech-debt, tentative content-refresh.
  - [conventions](crickets-conventions) — 8-domain base-standards shell (testing · releasing · ci · code-quality · agentic-engineering · reliability · coding · documentation).
  - [obsidian-vault](crickets-obsidian-vault) — the storage backend.
  - [token-audit](crickets-token-audit) — token metering; absorbs status-line-meter.
  - [privacy](crickets-privacy) — PII + extensible data-protection layer.
  - [research](crickets-research) — deep research.
  - [diagnostics](crickets-diagnostics) — observability / troubleshooting.

**Architecture (Agent M)**

- **[MemoryVault](https://github.com/alexherrero/agentm/wiki/memoryvault)** — permanent agent memory.
- **[Agent Memory Evolution V1→V7](https://github.com/alexherrero/agentm/wiki/agent-memory-evolution)** · **[Device-Wide Architecture](https://github.com/alexherrero/agentm/wiki/device-wide-architecture)** · **[Memory-OS (V5)](https://github.com/alexherrero/agentm/wiki/memory-os-architecture)**.

## Recent changes

<!-- maintained by the wiki tooling -->

- **2026-06-24** — AG Wave 2: the eight superseded designs (developer-plugin-suite, crickets-v3-native-plugins, the six wiki/CI designs) subsumed into the living children; diataxis-author vault-archived. `wiki/designs/` is now canonical-only.
- **2026-06-24** — AG Phase 3: 15 crickets child designs lifted (all content-final); crickets-hld.md re-synced (thirteen capabilities, rename ledger, 3 amendment entries).
- **2026-06-08** — moved to `designs/`; this index added.
- **2026-06-09** — Continuous Integration + Wiki designs added; the four earlier designs updated to shipped reality; Wiki Maintenance is now launched.

## See also

[Reference](Reference) · [Decisions](Decisions) · [Explanation](Explanation) · [Home](Home)
