---
title: "Antigravity emitter + cross-host divergences"
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
part_slug: antigravity-emitter
dependencies: [generator-claude]
estimated_scope: M
---

# Antigravity emitter + cross-host divergences

## Scope

Add the **Antigravity emitter** to the generator: the shared `.claude-plugin/plugin.json`, `hooks.json` with the AG event-name mapping (`PreToolUse` / `PostToolUse` / `PreInvocation` / `PostInvocation` / `Stop`; relative script paths, no `${CLAUDE_PLUGIN_ROOT}`), `mcp_config.json` (`serverUrl`, strict JSON, no `timeout`), and the AG `.agents/plugins/marketplace.json` (`interface.displayName`, `source:{source:local,path}`, `policy`, `category`). Composition: **thin** — AG dependents carry only their own primitives plus a documented `requires:`. Coverage-gap: emit `snippets` to AG `rules/`. Handle the **SessionStart→AG gap**: a hook bound to `SessionStart`/`UserPromptSubmit` emits Claude-only or maps to `PreInvocation` (no boot semantics). Record the AG-native-dependency re-audit on first install.

## Dependencies

- **generator-claude** — extends the generator + emitter interface proven on Claude.

## Verification criteria

- `generate.py build` emits AG plugin dirs + `.agents/plugins/marketplace.json` for every group with `antigravity` in `supported_hosts`.
- AG hooks use only the AG event-name set; no `SessionStart`/`UserPromptSubmit` leaks into an AG `hooks.json`.
- A dependent group's AG plugin contains only its own primitives (no inlined base) + a documented `requires:`.
- A generated AG plugin installs (`agy plugin install`/`link`) and loads.
- Re-audit recorded: AG native-dependency support confirmed-or-denied against a real `plugin.json` on first install (verify-on-dogfood trigger).

## Parent design

This part implements one slice of [Crickets v3.0 — Native Host Plugins from a Single Source of Truth](../../crickets-v3-native-plugins.md) (`Status: final`). See the parent for Context, Alternatives Considered, Quality Attributes, and Operations. Mid-execution scope changes must be appended to the parent's Document History.
