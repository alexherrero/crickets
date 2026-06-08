# Hooks

A **hook** is a script crickets runs at a fixed point in an agent session — before a tool call, at session start, when a turn ends — to observe or steer what the agent does. Each plugin declares its hooks in a single `hooks.json` (Claude Code: `<plugin>/hooks/hooks.json`; Antigravity: `<plugin>/hooks.json`), and the host runs them straight from the plugin. Installing the plugin is the whole setup — nothing lands in `.claude/hooks/`.

## ⚡ The hooks

| Hook | Plugin | Event | What it does | Details |
|---|---|---|---|---|
| `harness-context` | `developer-workflows` | `SessionStart` | surfaces `.harness/PLAN.md` + `progress.md` at boot so the agent reads the plan first | [spec](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/hooks/harness-context-session-start/hook.md) |
| `kill-switch` | `developer-safety` | `PreToolUse` | halts the next tool call when `.harness/STOP` exists | [how to use](Operator-Control-Hooks) |
| `steer` | `developer-safety` | `PreToolUse` | injects `.harness/STEER.md` into context, then archives it | [how to use](Operator-Control-Hooks) |
| `commit-on-stop` | `developer-safety` | `Stop` | saves a dirty tree to an `auto-save/<ts>` branch for crash recovery | [how to use](Operator-Control-Hooks) |
| `evidence-tracker` | `code-review` | `PreToolUse` | blocks flipping a `PLAN.md` task to `[x]` until evidence for it is recorded (default-FAIL `/work` gate) | [spec](https://github.com/alexherrero/crickets/blob/main/src/code-review/hooks/evidence-tracker/hook.md) |

**Hosts:** `harness-context` and `evidence-tracker` are Claude-only. The `developer-safety` trio install on both hosts but run **observe-only on Antigravity** (no veto/inject) — see [Compatibility](Compatibility).

> The **Details** links point at how each hook operates. Today the `developer-safety` trio point at [Operator-control hooks](Operator-Control-Hooks) and the rest at their hook spec; when each plugin gets its own page, these repoint to that page's hooks section.

## How hooks function

- **Events.** A hook registers on one host event — `SessionStart` (session boot), `PreToolUse` (before every tool call), or `Stop` (end of each turn). The host fires every hook registered on that event.
- **Effect.** A `PreToolUse` hook can **block** the tool call (a non-zero exit — e.g. `kill-switch`) or **inject** text into context (stdout — e.g. `steer`). A `Stop` hook runs as a side effect (e.g. `commit-on-stop`); a `SessionStart` hook seeds context.
- **Ordering.** When several hooks share an event, they run in the order the plugin's `hooks.json` declares them — `developer-safety` registers `kill-switch` before `steer`, so a halt always pre-empts a steer.
- **Per-host effectiveness.** On Antigravity, plugin hooks run **observe/side-effect-only**: any hook whose value depends on a veto (exit code) or an inject (stdout) is Claude-only-effective. See [Compatibility](Compatibility).

## See also

- [Operator-control hooks](Operator-Control-Hooks) — how to use the `developer-safety` trio (halt / redirect / recover).
- [Compatibility](Compatibility) — per-host hook effectiveness.
- [Customization Types](Customization-Types) — what `kind: hook` is, and where hook sources live.
- [Modify a crickets plugin](Modify-A-Plugin) — edit a hook script and dogfood it.
