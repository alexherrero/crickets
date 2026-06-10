# Compatibility

Which hosts and OSes crickets runs on, and how each component behaves per host.

## ⚡ Quick Reference

| Host | Status | Notes |
|---|---|---|
| **Claude Code** (Anthropic CLI / IDE) | ✅ supported | the primary surface; CI-verified on every push |
| **Antigravity 2.0** + the **`agy`** CLI | ✅ supported | CI-verified; some hooks run observe-only (below) |

Every customization declares `supported_hosts:` in its manifest, and the generator emits each plugin only for the hosts it supports. Destination paths per kind: [Per-Host Paths](Per-Host-Paths).

## Operating systems

Linux, macOS, and Windows (PowerShell 7+) are tested on **every push and PR** — the per-OS workflows, the aggregate badge, and the gate battery are in [CI gates](CI-Gates).

## Per-plugin host support

Claude Code supports every plugin fully; the **Support** column reflects Antigravity completeness.

| Plugin | Support | Antigravity gaps |
|---|---|---|
| `developer-workflows` | ⚠️ Partial | the `harness-context` SessionStart hook is Claude-only |
| `developer-safety` | ⚠️ Partial | its hooks fire but run **observe-only** (below) |
| `code-review` | ⚠️ Partial | the `evidence-tracker` hook is Claude-only |
| `github-ci` | ✅ Supported | — |
| `pii` | ✅ Supported | — |
| `wiki-maintenance` | ⚠️ Partial | the slash commands + the `wiki-author` skill are Claude-only ([why](Antigravity-Limitations)) |

## Hook effectiveness

A hook can be *emitted* on a host without being *effective* there. Antigravity runs plugin hooks **observe / side-effect-only** — it fires them but ignores exit codes and never reads stdout. So a hook that vetoes a tool call or injects text is inert on Antigravity even though it runs.

| Hook | Plugin | Claude Code | Antigravity | Why |
|---|---|---|---|---|
| `commit-on-stop` | `developer-safety` | ✅ effective | ✅ effective | pure side-effect (it commits) — no exit/stdout contract needed |
| `kill-switch` | `developer-safety` | ✅ effective | ⚠️ advisory only | vetoes via exit code; Antigravity ignores exit codes |
| `steer` | `developer-safety` | ✅ effective | ⚠️ advisory only | injects via stdout; Antigravity never reads hook stdout |
| `evidence-tracker` | `code-review` | ✅ effective | ❌ Claude-only | needs the veto contract Antigravity lacks (`[claude-code]`) |
| `harness-context` | `developer-workflows` | ✅ effective | ❌ Claude-only | SessionStart — Antigravity has no SessionStart surface |

**Rule of thumb:** side-effect-only hooks port to both hosts; any hook whose value depends on a veto (exit code) or an inject (stdout) is Claude-only-effective. The full catalog is in [Hooks](Hooks).

Authoring a host-portable hook? Resolve the workspace from stdin, not `cwd` — see [Hooks](Hooks).

## Snippet emission

The `snippet` kind is an instruction fragment. The generator emits it **as an Antigravity `rules/` file** (`<plugin>/rules/<name>.md`) and **drops it on Claude Code**, which has no instruction-file primitive to land it in. So `developer-safety`'s `commit-no-coauthor` + `worktrees-never-auto` conventions ship as Antigravity rules with no Claude-Code form. See [Per-Host Paths](Per-Host-Paths).

## Antigravity 2.0 gaps

Three Antigravity surfaces have **no file-based authoring path**, so crickets can't ship into them from the manifest model:

- **Hooks** — Antigravity hooks are Python decorators registered at agent creation; there's no `hooks.json` / `.agents/hooks/` to target. (crickets' file-based hooks therefore run observe-only — above.)
- **Scheduled tasks / triggers** — Python registration patterns, no file-based config; crickets ships none.
- **Multi-agent orchestration** — operator-facing (`start_subagent`); no plugin-author surface for spawn policy.

Each is tracked, with its re-address trigger, in the canonical [Antigravity limitations](Antigravity-Limitations) register.

## Out-of-scope hosts

- **Gemini CLI** — dropped in v3.0. Google replaced it with the Antigravity CLI (`agy`), which **is** supported; consumer Gemini CLI sunsets 2026-06-18. ([ADR 0006 — the crickets split](https://github.com/alexherrero/agentm/blob/main/wiki/explanation/decisions/0006-crickets-split.md).)
- **Codex** — never had an adapter.

## See also

- [Antigravity limitations](Antigravity-Limitations) — the host-gap register.
- [Hooks](Hooks) — the full hook catalog.
- [Per-Host Paths](Per-Host-Paths) — destinations per kind, per host.
- [Manifest Schema](Manifest-Schema) — the `supported_hosts` declaration.
