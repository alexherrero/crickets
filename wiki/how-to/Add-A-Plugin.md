# How to add a plugin

> [!NOTE]
> Plugins **moved to [Agent M](https://github.com/alexherrero/agentm)** in v2.0.0 (V4 #36 reorg). The `kind: plugin` enum entry remains in the Crickets manifest schema as reserved-future, but no plugins ship from Crickets in v2.0.0.
>
> See the Agent M wiki for the plugin authoring walkthrough:
>
> - [Agent M wiki — Add-A-Plugin](https://github.com/alexherrero/agentm/wiki/Add-A-Plugin)
>
> Crickets retains pointer here for v1.x search-engine traffic.

## Why plugins moved

Antigravity 2.0 plugins are bundled, multi-skill customizations that ship via `~/.gemini/config/plugins/<name>/`. The compound nature aligns with Agent M's surface (where the compound skills + memory hooks now live) more than with Crickets's base-primitive role. The plugin installer (`install-plugin.sh`) and reference plugin (`example-plugin`) moved together to keep the surface coherent.

## What stays in Crickets

- `kind: plugin` in the manifest schema enum (reserved-future; no v2.0.0 plugins).
- This page (a pointer to Agent M's authoritative documentation).

## Cross-references

- [Manifest-Schema § kind: plugin](../reference/Manifest-Schema.md) — the schema row stays accurate.
- [Device-Wide Architecture HLD](../explanation/designs/device-wide-architecture.md).
- [ADR 0011 — Antigravity 2.0 host support](../explanation/decisions/0011-antigravity-2-host-support.md) — original plugin support decision.
- [ADR 0012 — device-wide-by-default](../explanation/decisions/0012-device-wide-by-default.md).
