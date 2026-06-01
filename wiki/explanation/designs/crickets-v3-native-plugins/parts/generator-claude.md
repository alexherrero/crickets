---
title: "Generator core + Claude Code emitter"
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
part_slug: generator-claude
dependencies: [foundations]
estimated_scope: M
---

# Generator core + Claude Code emitter

## Scope

Build `scripts/generate.py` (Python, stdlib-only): discover group folders, parse `group.yaml` + primitive frontmatter, dispatch to a per-host **emitter interface** (`manifest` / `hooks` / `mcp` / `marketplace`), and write committed artifacts under `dist/plugins/<group>/`. Implement the **Claude Code emitter**: `.claude-plugin/plugin.json` (including native `dependencies` derived from `requires:`), `hooks/hooks.json` (Claude event names + `${CLAUDE_PLUGIN_ROOT}` paths), MCP (`.mcp.json`), output-styles, and the Claude `.claude-plugin/marketplace.json`. Coverage-gap on Claude: fold `snippets` text into the owning skill/agent (or drop, flagged). Output must be deterministic (sorted iteration, stable JSON key order, no timestamps). Prove Claude end-to-end: generate → `claude --plugin-dir` → loads.

## Dependencies

- **foundations** — needs the `src/<group>/` layout + manifest schema to read from.

## Verification criteria

- `generate.py build` emits `dist/plugins/<group>/.claude-plugin/plugin.json` + components for every group with `claude-code` in `supported_hosts`.
- A dependent group (e.g. Testing `requires: [developer]`) emits `dependencies: [developer]` in its `plugin.json`.
- A generated Claude plugin installs via `claude --plugin-dir dist/plugins/<group>` and its skill/command/hook loads + fires in a real session.
- Re-running `generate.py build` produces byte-identical output (determinism).

## Parent design

This part implements one slice of [Crickets v3.0 — Native Host Plugins from a Single Source of Truth](../../crickets-v3-native-plugins.md) (`Status: final`). See the parent for Context, Alternatives Considered, Quality Attributes, and Operations. Mid-execution scope changes must be appended to the parent's Document History.
