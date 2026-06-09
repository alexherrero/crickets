<!-- mode: index -->
# Developer Safety

The **operator-control + safety** plugin: hooks that let you halt, redirect, and recover an agent session, plus two standing commit conventions. It's the safety half of the developer plugin suite — installable on its own, and it engages with `developer-workflows`' phase loop when both are present.

## Install

```bash
claude plugin install developer-safety@crickets
```

On Antigravity, install by path (see [Install crickets plugins](Install-Into-Project)). The hooks run **observe / side-effect-only on Antigravity** — the veto/inject behaviour is Claude-effective ([Compatibility](Compatibility)).

## What it ships

| Primitive | Kind | What it does |
|---|---|---|
| **`kill-switch`** | hook · `PreToolUse` | halt the next tool call when `.harness/STOP` exists — emergency operator stop |
| **`steer`** | hook · `PreToolUse` | inject `.harness/STEER.md` into context, then archive it — mid-run redirect |
| **`commit-on-stop`** | hook · `Stop` | save a dirty tree to an `auto-save/<ts>` branch at session end — crash recovery (never touches your branch, never pushes) |
| **`commit-no-coauthor`** | snippet | never append a `Co-Authored-By` trailer — the user is the sole author |
| **`worktrees-never-auto`** | snippet | never auto-create git worktrees |

Drive the control trio from [Operator-control hooks](Operator-Control-Hooks); the full hook catalog is in [Hooks](Hooks). The snippets emit as Antigravity `rules/` and drop on Claude (where the conventions live in `CLAUDE.md`/`AGENTS.md` instead — see [Customization types](Customization-Types)).

## How it composes

- **Standalone** — installs and works on its own; depends on nothing.
- **Enhances `developer-workflows`** — soft: its hooks engage across the phase loop (`/plan` · `/work` · `/review` · `/release`) when both are installed.
- **Hosts** — both; Claude-effective, **observe-only on Antigravity** ([Compatibility](Compatibility)).

## Why it works

The primitives compose into a safety net: **operator-controllable** (kill-switch + steer), **recoverable** (commit-on-stop saves to a side branch, never your own), and **convention-enforcing** (the commit guards). The agent stays steerable and its mistakes stay recoverable.

## Related

- [Operator-control hooks](Operator-Control-Hooks) — how to use kill-switch / steer / commit-on-stop.
- [Hooks](Hooks) — the hook catalog + per-host effectiveness.
- [Plugin anatomy](Plugin-Anatomy) — what a crickets plugin is + its structure.
- [Install crickets plugins](Install-Into-Project) — all three install modes.
- [Developer Plugin Suite design](developer-plugin-suite) — the developer-workflows / safety / code-review split.
