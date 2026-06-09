---
title: "Generated-in-sync CI gate + generator tests"
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
part_slug: ci-gate
dependencies: [generator-claude, antigravity-emitter]
estimated_scope: S-M
---

# Generated-in-sync CI gate + generator tests

## Scope

Implement `generate.py check` — build to a temp dir, diff against committed `dist/`, exit non-zero on drift — as the CI gate that **replaces `check-lib-parity.sh`**. Add generator unit tests covering both emitters, the per-host mapping table, the hook event-name mapping, snippet handling, and determinism. Extend the PII scan to cover `dist/` (generated output) in addition to `src/`. Wire all three into crickets CI across the OS matrix.

## Dependencies

- **generator-claude** + **antigravity-emitter** — the gate diffs the output of both emitters.

## Verification criteria

- `generate.py check` exits 0 when `dist/` matches a fresh build, and non-zero when a `src/` primitive is edited without re-generating.
- Generator unit tests pass and cover both emitters + the cross-host divergences (hook names, paths, MCP fields, composition).
- The PII scan runs over `src/` AND `dist/`; a planted personal path in a generated artifact fails the gate.
- CI is green across the matrix on a freshly-generated `dist/`.

## Parent design

This part implements one slice of [Crickets v3.0 — Native Host Plugins from a Single Source of Truth](../../crickets-v3-native-plugins.md) (`Status: final`). See the parent for Context, Alternatives Considered, Quality Attributes, and Operations. Mid-execution scope changes must be appended to the parent's Document History.
