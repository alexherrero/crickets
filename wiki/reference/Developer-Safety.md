<!-- mode: reference -->
# Developer Safety

## Architecture

Developer Safety keeps you in control of an agent that works on its own. The longer an agent runs unattended, the more you want three things: a way to stop it, a way to redirect it without starting over, and the confidence that nothing is lost if a session ends unexpectedly. This plugin gives you all three — a kill switch, a steering note, and an automatic snapshot of in-flight work — plus a few ground rules for what the agent may decide for itself. It needs nothing else to work, and its safety hooks quietly engage across the rest of your workflow when the other plugins are installed.

### Diagram

How the hooks wrap the running workflow — every tool call passes the operator's live controls, guided by the recoverability doctrine, with a snapshot catching anything unsaved:

![Developer Safety wrapping the workflow: the developer-workflows phase loop (/plan, /work, /review, /release) sends every tool call through the kill-switch hook — fed by the operator's STOP trigger file — before it runs, while steer surfaces the operator's STEER.md note as additional context on their next submitted prompt; the recoverability doctrine guides each call, and commit-on-stop snapshots a dirty working tree to refs/auto-save at each turn's end](diagrams/developer-safety-hooks.svg)

### How it works

Developer Safety runs on three hooks, each watching for a simple trigger file in your project. Two of them give you live control while the agent works. The **kill switch** checks before every step: drop in a `STOP` file and the agent stops at once; delete it and it carries on — no restart. **Steer** works differently: write a "do it this way instead" note in `STEER.md` and the agent picks it up on your next submitted prompt, then sets it aside so you keep a record of what you asked. A `STOP` file still blocks the very next tool call regardless of what you type, while `STEER.md` waits for your next prompt — the two no longer fire on the same event, so there's no "which one wins" question; to both halt and redirect, drop `STOP`, write `STEER.md`, then send your next message before removing `STOP`. The third hook, **commit-on-stop**, is the safety net: when a turn ends with unsaved changes, it records a snapshot of your work to a separate ref, so a session that ends unexpectedly never loses what was in flight.

Under the hooks sits the **recoverability** doctrine — the judgment the agent applies on its own. Before it acts, it asks one question: can this be undone? If it can, it goes ahead and tells you; if it can't, it stops and checks with you first. Two short conventions round it out: no `Co-Authored-By` line on commits, and new worktrees only when you ask for one. One thing to know — the hooks do their full job on Claude Code; on Antigravity `kill-switch` and `commit-on-stop` still fire but can't block, and `steer` doesn't fire at all, so there you lean on an always-on rule that checks the same trigger files before each step.

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
| [`steer`](https://github.com/alexherrero/crickets/blob/main/src/developer-safety/hooks/steer/hook.md) | hook | Surfaces `.harness/STEER.md` on your next submitted prompt, then renames it for audit — mid-run redirect (Claude-effective). |
| [`commit-on-stop`](https://github.com/alexherrero/crickets/blob/main/src/developer-safety/hooks/commit-on-stop/hook.md) | hook | Snapshots a dirty tree to a hidden `refs/auto-save/<ts>` ref at Stop, without touching your work (both hosts). |
| [`commit-no-coauthor`](https://github.com/alexherrero/crickets/blob/main/src/developer-safety/snippets/commit-no-coauthor.md) | snippet | The no-`Co-Authored-By`-trailer commit convention. |
| [`worktrees-operator-initiated`](https://github.com/alexherrero/crickets/blob/main/src/developer-safety/snippets/worktrees-operator-initiated.md) | snippet | Worktrees are first-class but operator-initiated — never spawned autonomously. |

### Configuration

No configuration — the plugin works out of the box. The three hooks are driven entirely by trigger files you create under `.harness/` (`STOP`, `STEER.md`), and recovery snapshots land on `refs/auto-save/` refs.

## See also

- [Hooks](Hooks) — the full hook catalog and per-host effectiveness.
- [Compatibility](Compatibility) — per-hook Antigravity effectiveness (observe-only vs. doesn't fire at all).
- [Developer-safety design](crickets-developer-safety) · [Composition design](crickets-composition) — the deeper design.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)