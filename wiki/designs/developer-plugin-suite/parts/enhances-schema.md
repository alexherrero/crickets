---
title: "The enhances: composition schema (+ capabilities, generator/lint)"
status: draft
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-03
updated: 2026-06-03
last_major_revision: 2026-06-03
prd:
project:
parent_design: ../../developer-plugin-suite.md
part_slug: enhances-schema
dependencies: []
estimated_scope: M
---

# The `enhances:` composition schema (+ `capabilities:`, generator/lint)

## Scope

Add the soft-composition mechanism to the crickets plugin schema — the foundation the three plugins compose through. New optional `group.yaml` fields:

- **`enhances:`** on the *enhancer* — a list of `{group, capability?, effect}` entries declaring "when installed alongside `<group>`, I augment it (optionally its `<capability>`)." Keeps the enhancee open/extensible.
- **`capabilities:`** on the *enhancee* — the list of capabilities a plugin offers (e.g. `[setup, plan, work, review, release, bugfix]`), so `enhances` entries can target one by name.

Wire it through the generator chain: `src_model.py` (parse + model the fields), `lint_src.py` (validate), and the emitters (carry into `dist/` metadata + the marketplace "works better with" render). `enhances:` is **orthogonal to `requires:`/`standalone:`** — the `standalone: true ⟺ requires: []` invariant is preserved (it governs hard deps only).

> **Implemented 2026-06-03** across 4 tasks (`6906cae` model · `0fb654f` lint · `7e38716` emitters · the `Manifest-Schema.md` wiki ref). The `bootstrap.sh` install-time *enhancer suggestion* was **deferred to the `developer-safety` part** — it was premature/untestable here (no group declares `enhances` yet); it lands where the first real `enhances` edge exists. The marketplace already carries `enhances` (the discovery surface), so part 1's discovery story is complete.

## Dependencies

- None — this is the foundation the other parts build on.

## Verification criteria

- `lint_src.py` enforces all four rules, each unit-tested: target group exists · no self-enhance · `enhances ∩ requires = ∅` · a named `capability` is declared on the target.
- A `standalone: true` group may carry `enhances:` without violating the `requires: []` invariant.
- A group whose `enhances` names a non-existent group or undeclared capability **fails lint**.
- `generate.py build` carries `enhances`/`capabilities` into `dist/` metadata + the marketplace render; `generate.py check` clean.
- `bootstrap.sh` surfaces an enhancer suggestion when the enhancee is installed without it.

## Parent design

This part implements one slice of [Developer Plugin Suite](../../developer-plugin-suite.md) (`Status: final`) — Detailed Design §1. See the parent for Context, Alternatives Considered, Quality Attributes, and Operations. Mid-execution scope changes must be appended to the parent's Document History.
