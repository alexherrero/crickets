<!-- mode: reference -->
# Developer Safety

## Architecture

Developer Safety is the operator-control layer for a long-running agent session. It gives you a way to halt the agent mid-run, redirect it without a restart, and recover its in-flight work if a session ends unexpectedly — plus the standing autonomy doctrine and two commit conventions that decide what the agent may do on its own. The plugin is standalone: it depends on nothing, and its hooks quietly engage across the phase loop when `developer-workflows` is also installed.

### Diagram

_None / not needed._

### How it works

The heart of the plugin is a trio of hooks driven by trigger files under `.harness/`. `kill-switch` fires on every tool call: if `.harness/STOP` exists it blocks the call, so you `touch .harness/STOP` to halt and `rm` it to resume — no session restart. `steer` also fires on every tool call: write a "do it this way instead" note to `.harness/STEER.md` and the next call picks it up, after which the hook renames the file to `STEER.consumed-<timestamp>.md` for an audit trail. `commit-on-stop` fires when a turn ends: if the working tree is dirty it records a full snapshot on a hidden `refs/auto-save/<timestamp>` ref without switching branches or touching your edits, so a crashed session stops losing work. The two `PreToolUse` hooks run in alphabetical install order, so `kill-switch` always wins over `steer` — a halt takes precedence over a redirect.

Above the hooks sits the `recoverability` skill: the doctrine that classifies every action as recoverable or unrecoverable, proceeds on the former (announced), and stops only on the latter. The skill is the pre-action discipline; the hooks are the in-flight controls that enforce it. Two snippets round out the plugin — `commit-no-coauthor` (never add a `Co-Authored-By` trailer naming the model) and `worktrees-operator-initiated` (worktrees are first-class but never spawned autonomously). On Claude Code the hooks are fully effective; on Antigravity they fire observe-only, so you approximate them with an always-on rule that checks the trigger files before each step.

### Composition

| Direction | Plugin | How |
|---|---|---|
| Enhances (soft) | [Developer-Workflows](Developer-Workflows) | The three hooks engage across the phase loop, and the `recoverability` doctrine backs `/work`'s recoverability gate — only when both are installed. |
| Enhanced by (soft) | — | None. |
| Requires (hard) | — | None. Developer Safety is fully standalone. |
| Required by (hard) | — | None. |

### Why not

Developer Safety is opinionated, and it will not fit every setup. Reach for something else if:

- You prefer a different control model — a custom pre-tool hook, a wrapper script, or your host's own interrupt — over trigger files under `.harness/`.
- You disagree with a convention it ships: some teams do want a `Co-Authored-By` trailer, or a looser worktree policy. The snippets encode a specific stance.
- The change is small or throwaway and you don't need a halt/steer/snapshot safety net — for a quick one-off session the hooks add machinery you won't use.

## Reference

### Commands & skills

Each primitive links to the source that implements it.

| Primitive | Kind | What it does |
|---|---|---|
| [`recoverability`](https://github.com/alexherrero/crickets/blob/main/src/developer-safety/skills/recoverability/SKILL.md) | skill | Classify every action recoverable vs unrecoverable; proceed on one, stop on the other. |
| [`kill-switch`](https://github.com/alexherrero/crickets/blob/main/src/developer-safety/hooks/kill-switch/hook.md) | hook | Blocks every tool call while `.harness/STOP` exists — an operator emergency halt (Claude-effective). |
| [`steer`](https://github.com/alexherrero/crickets/blob/main/src/developer-safety/hooks/steer/hook.md) | hook | Injects `.harness/STEER.md` into the next call, then renames it for audit — mid-run redirect (Claude-effective). |
| [`commit-on-stop`](https://github.com/alexherrero/crickets/blob/main/src/developer-safety/hooks/commit-on-stop/hook.md) | hook | Snapshots a dirty tree to a hidden `refs/auto-save/<ts>` ref at Stop, without touching your work (both hosts). |
| [`commit-no-coauthor`](https://github.com/alexherrero/crickets/blob/main/src/developer-safety/snippets/commit-no-coauthor.md) | snippet | The no-`Co-Authored-By`-trailer commit convention. |
| [`worktrees-operator-initiated`](https://github.com/alexherrero/crickets/blob/main/src/developer-safety/snippets/worktrees-operator-initiated.md) | snippet | Worktrees are first-class but operator-initiated — never spawned autonomously. |

### Configuration

No configuration — the plugin works out of the box. The three hooks are driven entirely by trigger files you create under `.harness/` (`STOP`, `STEER.md`), and recovery snapshots land on `refs/auto-save/` refs.

## See also

- [Hooks](Hooks) — the full hook catalog and per-host effectiveness.
- [Compatibility](Compatibility) — why the hooks are Claude-effective and observe-only on Antigravity.
- [Developer-safety design](crickets-developer-safety) · [Composition design](crickets-composition) — the deeper design.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)