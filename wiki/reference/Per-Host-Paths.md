# Per-host paths

crickets generates native host plugins from `src/<group>/` into committed `dist/<host>/plugins/<group>/`. This uses the [source → generator model](crickets-build-system#overview). Each primitive `kind` lands at a host-specific path inside that plugin. The host's plugin manager installs the whole plugin (`claude plugin install` / `agy plugin install <path>`). Nothing is copied into `.claude/` or the project tree. This page shows the kind → in-plugin path lookup, per host.

## ⚡ Quick Reference

Paths are relative to the plugin root, `dist/<host>/plugins/<group>/`.

| Kind | Claude Code | Antigravity |
|---|---|---|
| `skill` | `skills/<name>/SKILL.md` | `skills/<name>/SKILL.md` |
| `agent` | `agents/<name>.md` | `agents/<name>.md` |
| `command` | `commands/<name>.md` | `commands/<name>.md` |
| `hook` | `hooks/hooks.json` + `hooks/<name>/` | `hooks.json` (plugin root) + `hooks/<name>/` |
| `snippet` | — dropped (no instruction-file primitive) | `rules/<name>.md` |
| plugin manifest | `.claude-plugin/plugin.json` | `plugin.json` (plugin root) |
| `scripts/` (group asset) | `scripts/<name>` | `scripts/<name>` |

See [Hooks](Hooks) for what each `hooks/<name>/` dir contains. It also shows how hooks run from the plugin.

## Where the hosts differ

- **Plugin manifest.** Claude Code reads `.claude-plugin/plugin.json`. Antigravity reads `plugin.json` at the plugin root.
- **Hook manifest.** Claude wraps the hook records in `hooks/hooks.json`. Antigravity keys them in `hooks.json` at the plugin root. Antigravity runs plugin hooks observe-only. See [Compatibility](Compatibility) for details.
- **Snippets.** Antigravity ships instruction files. A `snippet` emits to `rules/<name>.md`. Claude Code has no instruction-file primitive in the plugin surface. You will see snippets dropped. The generator logs each drop.
- **Marketplace pointer** (repo root, for `<host> plugin marketplace add`): Claude uses `.claude-plugin/marketplace.json`. Antigravity uses `.agents/plugins/marketplace.json`.
- **MCP servers.** No `mcp-server` primitive ships today. It is reserved-unused. The host shapes differ when one lands. Claude Code reads `.mcp.json` (or inline config). Antigravity reads `mcp_config.json`. Antigravity requires a `serverUrl` and strict JSON. It has **no `timeout`** field.

## Source → emitted

The generator mirrors the source layout. You author a skill at `src/<group>/skills/<name>/SKILL.md`. It emits to `dist/<host>/plugins/<group>/skills/<name>/SKILL.md` for each host in its `supported_hosts`. Agents, commands, hooks, and snippets follow the same `src/<group>/<kind-dir>/…` → in-plugin-path rule. A group's `scripts/` dir copies wholesale to the plugin. Run `python3 scripts/generate.py build` after editing `src/`. See [Modify a plugin](Modify-A-Plugin).

## In-plugin paths for all emitted kinds

Paths are relative to the plugin root, `dist/<host>/plugins/<group>/`.

| Kind | Claude Code | Antigravity |
|---|---|---|
| `output-style` | `output-styles/<name>.md` | `output-styles/<name>.md` |
| `rule` | `rules/<name>.md` | `rules/<name>.md` |

These two ship as of v3.13–3.14. The `development-lifecycle` plugin ships `terse` and `edit-over-write`. The `kind` enum also allows `mcp-server`, `status-line`, `workflow`, and `settings-fragment`. No primitive uses them today. The full enum lives in [Manifest Schema](Manifest-Schema).

## Related

- [Plugin anatomy](Plugin-Anatomy) — what a plugin is + its overall structure.
- [Customization Types](Customization-Types) — what each kind means.
- [Manifest Schema](Manifest-Schema) — the frontmatter + `group.yaml` contract.
- [Modify a plugin](Modify-A-Plugin) — edit `src/`, regenerate, dogfood.
- [Install crickets plugins](Install-Into-Project) — how the host installs a plugin.
