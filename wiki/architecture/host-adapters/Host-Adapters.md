<!-- mode: index -->
# Host adapters

_One authored primitive, two hosts — how each kind lands on Claude Code and Antigravity, and where a host can't follow._

crickets targets two hosts — **Claude Code** and **Antigravity** — from one source. A primitive declares `supported_hosts`, and the generator emits a host-shaped artifact for each — the same `kind`, placed and packaged the way that host expects. Where a host can't honor a primitive, the gap is named rather than hidden.

## How it works

The generator mirrors the source layout into `dist/<host>/plugins/<group>/`, and each `kind` lands at a host-specific path inside that plugin. The host's own plugin manager installs the whole plugin — nothing is copied into `.claude/` or the project tree.

| Kind | Claude Code | Antigravity |
|---|---|---|
| **`skill`** / **`agent`** / **`command`** | same in-plugin path on both hosts | same |
| **`hook`** | `hooks/hooks.json` + `hooks/<name>/` | root `hooks.json` + `hooks/<name>/`; runs observe-only |
| **`snippet`** | dropped — no instruction-file surface | `rules/<name>.md` |

The two hosts agree on most paths and split in a few places: the plugin manifest (`.claude-plugin/plugin.json` vs a root `plugin.json`), the hook manifest location, and the marketplace pointer. Two splits change what you can rely on — Claude Code drops `snippet`s (it has no instruction-file surface), and Antigravity runs hooks observe-only (it ignores exit codes and never reads stdout), so a hook that vetoes or injects is Claude-only-effective.

## How it fits

- **[Build & distribution](Build-And-Distribution)** — the pipeline that runs the emit. Host adapters define *where* each kind lands; build & distribution puts it there.
- **[Customization model](Customization-Model)** — the inputs the adapter switches on. Each primitive's `supported_hosts` + `kind` decide which hosts receive it and what artifact it becomes.

## Host gaps

- **Antigravity authoring gaps.** Hooks, scheduled tasks, and multi-agent orchestration have no file-based authoring path, so a primitive can emit without being effective — each gap is tracked with its re-address trigger in the limitations register.

## See also

Detail:

- [Per-host paths](Per-Host-Paths) — the destination table per primitive × host.
- [Compatibility](Compatibility) — which kinds and hooks are effective on each host.
- [Antigravity limitations](Antigravity-Limitations) — the host-gap register.

[Architecture](Architecture) · [Reference](Reference) · [Home](Home)
