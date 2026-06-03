---
title: "Auto-enable runtime: probe + conditional /review dispatch"
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
part_slug: auto-enable-runtime
dependencies: [developer-workflows, code-review]
estimated_scope: S
---

# Auto-enable runtime: probe + conditional `/review` dispatch

## Scope

The runtime half of `enhances:` — make the soft composition actually engage:

- **Local deterministic probe** — a shared crickets helper that answers *"is capability X / plugin Y available?"* by checking the installed-plugin state. Deterministic (not agent-judgment), reproducible, **graceful-skip** (clean no-op) when absent.
- **Conditional `/review` dispatch** — wire `developer-workflows`' thin `/review` spec to: *if `code-review`'s `review` capability is available → dispatch `adversarial-reviewer` (+ `-cross`); else run deterministic gates only and note the lighter review.*

The probe is the **local fallback** for the generalized **agentm capability-discovery API** (tracked as agentm **V5-8**); when that host feature lands, plugins query the host and these local probes retire. The runtime contract is identical either way — a deterministic yes/no with graceful-skip.

## Dependencies

- **developer-workflows** — owns the `/review` phase being made conditional.
- **code-review** — provides the adversarial agents the conditional dispatch targets.

## Verification criteria

- With `code-review` installed, `/review` dispatches the adversarial pass.
- Without `code-review`, `/review` runs deterministic gates only + notes the lighter review — **no error, no hang** (clean graceful-skip).
- The probe returns a deterministic, reproducible yes/no across runs (present vs absent).
- The hand-off to the agentm V5-8 capability-discovery API is documented (the local probe is explicitly the interim fallback).

## Parent design

This part implements one slice of [Developer Plugin Suite](../../developer-plugin-suite.md) (`Status: final`) — Detailed Design §5. See the parent for Context, Alternatives Considered, Quality Attributes, and Operations. Mid-execution scope changes must be appended to the parent's Document History.
