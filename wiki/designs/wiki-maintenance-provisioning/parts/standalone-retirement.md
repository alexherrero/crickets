---
title: "Selective, supersession-gated standalone retirement"
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
part_slug: standalone-retirement
dependencies: []
estimated_scope: S-M
---

# Selective, supersession-gated standalone retirement

## Scope

Extend the reconcile to the primitive level. The pre-v3 install left `~/.claude/{skills,agents,commands}/<name>` standalones that **shadow** the installed plugins (confirmed systemic 2026-06-10 — the phase commands, `explorer`, the reviewers, `recent-wiki-changes`, and the wiki trio). For each **installed** crickets plugin, enumerate the primitives it provides; for each, if a `~/.claude/` standalone exists that the plugin supersedes, remove it (preview-first, report each). **Never** touch a standalone no installed plugin provides — `design`, `memory`, `doctor`, `ship-release`, `last30days`, `adapt-evaluator`, `memory-idea-researcher` are agentm-native or third-party and must stay. Match by primitive name **and** crickets-plugin provenance, not name alone.

Extends the shipped `scripts/reconcile_plugins.py` (plugin-level) to the primitive level; coordinates with the V5 ⑤ slim (which deletes agentm's *source* copies — this owns the `~/.claude/` symlink side, so the two don't double-handle). Covers Detailed Design §4.

## Dependencies

None — this is the `~/.claude/` reconcile, orthogonal to the repo-provisioning parts. Reuses the `reconcile_plugins.py` pattern that already shipped.

## Verification criteria

- Given a fixture `~/.claude/` set mixing superseded standalones (a plugin provides them) and genuinely-standalone ones, the reconcile removes **only** the superseded set and keeps the rest.
- The kept set always includes the agentm-native / third-party primitives (`design`, `memory`, `doctor`, `ship-release`, `last30days`, `adapt-evaluator`, `memory-idea-researcher`).
- The supersession diff is a pure function, unit-tested without a host CLI (like `reconcile_plugins.py`); preview-first is the default — apply requires explicit confirmation.
- The full gate battery is green.

## Parent design

This part implements one slice of [Wiki-Maintenance Provisioning Design](wiki-maintenance-provisioning) (`Status: final`). See the parent for Context, Alternatives Considered (blind-removal rejected), Quality Attributes (Data Integrity — no false-remove), and Operations. Mid-execution scope changes append to the parent's Document History.
