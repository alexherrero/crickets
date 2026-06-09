---
title: "Documenter runtime wiring: capability probe → phase-boundary dispatch"
status: draft
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-04
updated: 2026-06-04
last_major_revision: 2026-06-04
prd:
project: https://github.com/users/alexherrero/projects/5
parent_design: ../../wiki-maintenance.md
part_slug: documenter-wiring
dependencies: [scaffold-fold-in]
estimated_scope: M
---

# Documenter runtime wiring: capability probe → phase-boundary dispatch

## Scope

Realize the `enhances:` edge's runtime half — make the soft composition actually engage at phase boundaries (auto-enable-runtime parity).

- **Expose a `documentation` capability** on `developer-workflows`: its phase commands already scaffold a documenter dispatch at every boundary, but today that dispatch is **prose-only graceful-skip with no probe** — the enhance is *declared but unwired*.
- **Wire it deterministically.** The phase commands call `capability_probe.py` and dispatch the `documenter` on a hit (the same deterministic yes/no with graceful-skip that wired conditional `/review`). When `wiki-maintenance` is installed, the documenter runs the template ⊕ style ⊕ overlay flow; when absent, the phase commands graceful-skip exactly as before.
- **Scoped as its own task** because it edits the **already-launched `developer-workflows`** source — never a silent half-wire bundled into another part.

## Dependencies

- **`scaffold-fold-in`** — the `documenter` must live in `wiki-maintenance` to be the dispatch target the probe resolves to.

## Verification criteria

- `developer-workflows` declares a `documentation` capability that `capability_probe.py` can resolve.
- Phase commands probe + dispatch the `documenter` when `wiki-maintenance` is installed; **graceful-skip** (clean no-op, prose note) when it is absent.
- **Non-breaking:** a dev-loop with no `wiki-maintenance` installed behaves exactly as before (still skips cleanly).
- Full gate battery (`bash scripts/check-all.sh`) green; the new capability path is exercised by a test.
- **Wake-on-CI before marking `[x]`** — this edits a launched plugin's source + regenerates `dist/`; confirm CI green across the OS matrix first.

## Parent design

This part implements one slice of [Wiki-Maintenance — an opinionated, template-driven wiki maintainer](../../wiki-maintenance.md) (`Status: final`). See the parent for Context, Alternatives Considered, Quality Attributes overview, and Operations strategy. Mid-execution changes to this part's scope must be appended to the parent's Document History.
