---
title: "Dogfood proof (both hosts) + ADRs + how-tos"
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
part_slug: dogfood-proof-docs
dependencies: [distribution-clean-break]
estimated_scope: M
---

# Dogfood proof (both hosts) + ADRs + how-tos

## Scope

**Dogfood proof:** install the generated plugins on both hosts across agentm / crickets / sherwood, confirming skills / commands / hooks / MCP load and fire as they did under the old install model. Write the **3 ADRs** — "bundles = native host plugins", "#40 install-decoupling", "#36 partial revision" (documents the deferred design/diataxis-author/ship-release moves). **How-tos:** "Install crickets plugins" (all three modes, per host) and "Develop a crickets plugin locally" (the `--plugin-dir` / `agy link` dev loop). Update crickets `AGENTS.md` / `README.md` for the new model; remove `install.sh` references. When this part completes, the parent design transitions to `launched`.

## Dependencies

- **distribution-clean-break** — proof + docs describe the final install model after the clean break.

## Verification criteria

- Generated plugins install + load on Claude Code AND Antigravity across all three repos; a per-host smoke test (a hook fires, a skill runs) passes.
- 3 ADRs published in `wiki/explanation/decisions/` following the ADR shape (`> [!NOTE]` status/date, "why not the alternative" per call, explicit re-audit triggers).
- Install + dev-loop how-tos published and pass `check-wiki.py --strict`.
- `AGENTS.md` / `README.md` no longer reference the `install.sh` dispatch; the install how-to is the canonical entry.

## Parent design

This part implements one slice of [Crickets v3.0 — Native Host Plugins from a Single Source of Truth](../../crickets-v3-native-plugins.md) (`Status: final`). See the parent for Context, Alternatives Considered, Quality Attributes, and Operations. Mid-execution scope changes must be appended to the parent's Document History.
