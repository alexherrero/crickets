# Hooks

A **hook** is a script crickets runs at a fixed point in an agent session — before a tool call, at session start, when a prompt is submitted, when a turn ends — to observe or steer what the agent does. Each plugin declares its hooks in a single `hooks.json` (Claude Code: `<plugin>/hooks/hooks.json`; Antigravity: `<plugin>/hooks.json`), and the host runs them straight from the plugin. Installing the plugin is the whole setup — nothing lands in `.claude/hooks/`.

## ⚡ The hooks

| Hook | Plugin | Event | What it does | Details |
|---|---|---|---|---|
| `harness-context` | `development-lifecycle` | `SessionStart` | surfaces `.harness/PLAN.md` + `progress.md` at boot so the agent reads the plan first | [spec](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/hooks/harness-context-session-start/hook.md) |
| `compact-nudge-resume` | `development-lifecycle` | `UserPromptSubmit` | on every user prompt, checks context size (PCT≥60% or >400 assistant turns) and injects an `additionalContext` nudge toward `/clear` over `/compact`; silent no-op on a fresh session or below threshold | [spec](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/hooks/compact-nudge-resume/hook.md) |
| `kill-switch` | `developer-safety` | `PreToolUse` | halts the next tool call when `.harness/STOP` exists | [how to use](Developer-Safety#driving-the-control-trio) |
| `steer` | `developer-safety` | `UserPromptSubmit` | surfaces `.harness/STEER.md` on your next submitted prompt via `additionalContext`, then archives it | [how to use](Developer-Safety#driving-the-control-trio) |
| `commit-on-stop` | `developer-safety` | `Stop` | saves a dirty tree to an `auto-save/<ts>` branch for crash recovery | [how to use](Developer-Safety#driving-the-control-trio) |
| `evidence-tracker` | `code-review` | `PreToolUse` | blocks flipping a `PLAN.md` task to `[x]` until evidence for it is recorded (default-FAIL `/work` gate) | [spec](https://github.com/alexherrero/crickets/blob/main/src/code-review/hooks/evidence-tracker/hook.md) |

**Hosts:** `compact-nudge-resume` and `evidence-tracker` are Claude-only. Every other hook installs on both hosts and is effective on both: on Antigravity they run through a small adapter that translates between Claude's hook contract and `agy`'s — see [Compatibility](Compatibility).

> The **Details** links point at how each hook operates — the `developer-safety` trio at the [Developer Safety](Developer-Safety) plugin page's control-trio section, the rest at their hook spec.

## How hooks function

- **Events.** A hook registers on one host event — `SessionStart` (session boot), `PreToolUse` (before every tool call), `UserPromptSubmit` (when the operator submits a prompt), or `Stop` (end of each turn). The host fires every hook registered on that event.
- **Effect.** A `PreToolUse` hook can **block** the tool call (a non-zero exit — e.g. `kill-switch`). A `UserPromptSubmit` hook can **inject** text into context by emitting `{"additionalContext": "<text>"}` as JSON on stdout — e.g. `steer`, which surfaces `.harness/STEER.md` on the next submitted prompt this way. A `Stop` hook runs as a side effect (e.g. `commit-on-stop`); a `SessionStart` hook seeds context.
- **Ordering.** When several hooks share an event, they run in the order the plugin's `hooks.json` declares them. `kill-switch` (`PreToolUse`) and `steer` (`UserPromptSubmit`) no longer share an event, so there is no install-order relationship between them: a `STOP` file still blocks the very next tool call regardless of what's submitted, while a `STEER.md` surfaces independently on the next prompt.
- **Per-host effectiveness.** Both hosts honour a block and an inject, in different words. On Antigravity each hook is registered as `python3 ./hooks/_agy_hook_adapter.py <Event> <the original command>`. The adapter rebuilds Claude's stdin payload from `agy`'s, runs the script from the workspace root the way Claude Code does, and turns the result into `agy`'s JSON. See [Compatibility](Compatibility) for which hooks were watched running.
- **The adapter's translation.**

  | Claude hook event | `agy` event | A hook that exits 2 | A hook that prints text or `additionalContext` |
  |---|---|---|---|
  | `PreToolUse` | `PreToolUse` | `{"decision": "deny", "reason": <stderr>}` | — |
  | `PostToolUse` | `PostToolUse` | ignored | ignored |
  | `SessionStart` | `SessionStart` | ignored | a system message that stays in the conversation |
  | `UserPromptSubmit` | `PreInvocation`, once per user message | stops the turn and shows the user the message | a one-turn message |
  | `Stop` | `Stop` | keeps the agent going (`"decision": "continue"`) | — |

  With nothing to say, a `PreToolUse` hook prints nothing (`agy` reads `{}` there as a deny); every other event answers `{}`. If the adapter itself breaks, it answers the same "nothing to say" and exits 0, so a broken hook never stalls the agent. That also means a guard fails open, so the adapter's tests are what keep `kill-switch` honest.
- **Matchers.** `agy` names tools differently (`run_command`, `view_file`). The adapter hands the script Claude's names (`Bash`, `Read`) and the emitter rewrites a hook's matcher to match.
- **Authoring a portable hook.** The two hosts invoke hooks differently — Claude Code runs them at the project root (and sets `$CLAUDE_PROJECT_DIR`); Antigravity runs them in the *plugin* dir and passes the workspace only as stdin JSON (`{"workspacePaths":["<root>"]}`). A portable hook reads stdin, parses it with a real JSON parser (top-level keys only — a `sed`/regex parser mismatches nested payloads), resolves the root as `workspacePaths[0]` → stdin `cwd` → `$CLAUDE_PROJECT_DIR` → `cwd`, then `cd`s in before any relative logic. The shipped `developer-safety` hooks do this (`scripts/test_developer_hooks_workspace.py` for the `.sh` twins, `scripts/test_developer_hooks_workspace_ps1.py` for the `.ps1` twins).
- **On-disk layout.** Each hook lives in its own `hooks/<name>/` dir in the plugin: the script as both `<name>.sh` (POSIX) and `<name>.ps1` (PowerShell), its `hook.md` spec, and `settings-fragment-{bash,pwsh}.json` (the event registration merged into the host config). The host runs the script from `${CLAUDE_PLUGIN_ROOT}/hooks/<name>/…` per the manifest. ([Per-host paths](Per-Host-Paths) carries the manifest location per host.)

## See also

- [Developer Safety](Developer-Safety) — how to drive the `developer-safety` trio (halt / redirect / recover).
- [Compatibility](Compatibility) — per-host hook effectiveness.
- [Customization Types](Customization-Types) — what `kind: hook` is, and where hook sources live.
- [Modify a crickets plugin](Modify-A-Plugin) — edit a hook script and dogfood it.
