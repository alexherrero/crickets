---
title: "Docs + the provisioning ADR"
status: draft
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-10
updated: 2026-06-10
last_major_revision: 2026-06-10
prd:
project: https://github.com/users/alexherrero/projects/5
parent_design: ../../wiki-maintenance-provisioning.md
part_slug: docs-adr
dependencies: [wiki-sync-template, wiki-init, standalone-retirement]
estimated_scope: S
---

# Docs + the provisioning ADR

## Scope

Document the shipped provisioning surface and record its decisions:

- A how-to — **"Provision a repo's wiki"** — run `wiki-init`, what it drops (`[W] Update Wiki` + the scaffold), and the CI gate wiring.
- Update the [Wiki-Maintenance plugin page](Wiki-Maintenance) (the new init surface) and the [Wiki design](wiki-design) (provisioning joins authoring).
- An **ADR** for the two load-bearing calls: gate distribution **by reference, not vendor**, and the **supersession-gated** standalone retirement — each with its re-audit trigger.

Covers the parent's Documentation Plan.

## Dependencies

- **`wiki-sync-template`**, **`wiki-init`**, **`standalone-retirement`** — the docs describe the shipped behaviour of all three, so they land after the implementation parts.

## Verification criteria

- The how-to walks `wiki-init` end-to-end (scaffold · the dropped workflow · the referenced gate · the non-public warning) and is gate-clean.
- The plugin page + the Wiki design reflect the provisioning surface.
- The ADR records both calls with re-audit triggers (per the operator's ADR shape).
- `check-wiki --strict` is clean; the full gate battery is green.

## Parent design

This part implements one slice of [Wiki-Maintenance Provisioning Design](wiki-maintenance-provisioning) (`Status: final`). See the parent for Context, Documentation Plan, and the decisions this ADR records. Mid-execution scope changes append to the parent's Document History.
