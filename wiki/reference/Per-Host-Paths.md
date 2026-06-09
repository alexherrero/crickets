# Per-host paths

crickets generates native host plugins from `src/<group>/` into committed `dist/<host>/plugins/<group>/` (the [source → generator model](crickets-v3-native-plugins#overview)). Each primitive `kind` lands at a host-specific path *inside* that plugin, and the host's plugin manager installs the whole plugin (`claude plugin install` / `agy plugin install <path>`) — nothing is copied into `.claude/` or the project tree. This page is the kind → in-plugin path lookup, per host.

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

See [Hooks](Hooks) for what each `hooks/<name>/` dir contains and how hooks run from the plugin.

## Where the hosts differ

- **Plugin manifest.** Claude Code reads `.claude-plugin/plugin.json`; Antigravity reads `plugin.json` at the plugin root.
- **Hook manifest.** Claude wraps the hook records in `hooks/hooks.json`; Antigravity keys them in `hooks.json` at the plugin root. (Antigravity runs plugin hooks observe-only — see [Compatibility](Compatibility).)
- **Snippets.** Antigravity ships instruction files, so a `snippet` emits to `rules/<name>.md`; Claude Code has no instruction-file primitive in the plugin surface, so snippets are dropped (the generator logs each drop).
- **Marketplace pointer** (repo root, for `<host> plugin marketplace add`): Claude `.claude-plugin/marketplace.json`; Antigravity `.agents/plugins/marketplace.json`.

## Source → emitted

The generator mirrors the source layout. A skill authored at `src/<group>/skills/<name>/SKILL.md` emits to `dist/<host>/plugins/<group>/skills/<name>/SKILL.md` for each host in its `supported_hosts`; agents, commands, hooks, and snippets follow the same `src/<group>/<kind-dir>/…` → in-plugin-path rule. A group's `scripts/` dir copies wholesale to the plugin. Run `python3 scripts/generate.py build` after editing `src/` — see [Modify a plugin](Modify-A-Plugin).

## Kinds not emitted yet

crickets ships the five kinds above — `skill`, `agent`, `command`, `hook`, `snippet`. The `kind` enum also allows `mcp-server`, `status-line`, `output-style`, `workflow`, `rule`, and `settings-fragment`, but no primitive uses them today, so the generator emits none. The full enum lives in [Manifest Schema](Manifest-Schema).

## Related

- [Plugin anatomy](Plugin-Anatomy) — what a plugin is + its overall structure.
- [Customization Types](Customization-Types) — what each kind means.
- [Manifest Schema](Manifest-Schema) — the frontmatter + `group.yaml` contract.
- [Modify a plugin](Modify-A-Plugin) — edit `src/`, regenerate, dogfood.
- [Install crickets plugins](Install-Into-Project) — how the host installs a plugin.
