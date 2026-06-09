---
title: "Three install modes + clean-break deletion"
status: draft
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-01
updated: 2026-06-01
last_major_revision: 2026-06-01
prd:
project:
parent_design: ../../crickets-v3-native-plugins.md
part_slug: distribution-clean-break
dependencies: [antigravity-emitter, ci-gate]
estimated_scope: S-M
---

# Three install modes + clean-break deletion

## Scope

Implement the **three install modes**: (1) a **one-line installer** (`curl … | bash`) that detects the installed host(s), adds the crickets marketplace, and installs the default config — reading the **default-set list emitted by the generator** (data, not hard-coded); a thin wrapper that only calls native `plugin install`. (2) Marketplace add/install. (3) Manual pick-and-choose (`claude --plugin-dir` / `agy link` against a committed plugin dir). Then the **clean break**: delete `install.sh` / `install.ps1` dispatch, the crickets copy of `lib/install/`, `sync-lib.sh`, `check-lib-parity.sh`, and the old top-level primitive dirs (now living under `src/`).

## Dependencies

- **antigravity-emitter** — needs both hosts' plugin dirs to install.
- **ci-gate** — the parity gate must move to `generate.py check` before the old `check-lib-parity.sh` is deleted.

## Verification criteria

- The one-line installer installs the default config on a clean machine (both hosts) with zero clicks; the result matches a manual marketplace install.
- The installer reads the default-set from generated data — changing the catalog changes the installed set with no installer code edit.
- Manual `--plugin-dir` / `agy link` installs a single chosen plugin without the marketplace.
- `install.sh` dispatch, `lib/install/`, `sync-lib.sh`, `check-lib-parity.sh`, and the old top-level dirs are gone; CI stays green (parity now via `generate.py check`).

## Parent design

This part implements one slice of [Crickets v3.0 — Native Host Plugins from a Single Source of Truth](../../crickets-v3-native-plugins.md) (`Status: final`). See the parent for Context, Alternatives Considered, Quality Attributes, and Operations. Mid-execution scope changes must be appended to the parent's Document History.
