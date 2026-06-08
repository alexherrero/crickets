# Operator-control hooks

The `developer-safety` plugin ships three hooks that give you precise control over a long-running Claude Code session: **halt** it, **redirect** it, and **recover** its work after a crash. They run from the plugin (declared in its `hooks.json`) — installing `developer-safety@crickets` is all the setup; nothing lands in `.claude/hooks/`.

## ⚡ Quick Reference

| Hook | Event | Trigger | Effect |
|---|---|---|---|
| `kill-switch` | `PreToolUse` (every tool call) | `<repo>/.harness/STOP` exists | Blocks the tool call (exit 2 + a halt message); `rm` the file to resume. |
| `steer` | `PreToolUse` (every tool call) | `<repo>/.harness/STEER.md` exists | Prints its contents into the agent's context, then renames the file to `STEER.consumed-<ts>.md`. |
| `commit-on-stop` | `Stop` (end of each turn) | working tree is dirty | Commits all changes to an `auto-save/<ts>` branch, then restores your branch clean. Never touches your branch or pushes. |

**Claude Code only.** On Antigravity these run observe-only (no veto/inject) — see [Compatibility](Compatibility); a manual fallback is below.

## Trigger files

| File | Who writes it | Lifecycle |
|---|---|---|
| `.harness/STOP` | you | `touch` to halt; `rm` to resume |
| `.harness/STEER.md` | you | the hook renames it to `STEER.consumed-<ts>.md` after reading |
| `.harness/STEER.consumed-*.md` | the hook | audit trail; clean up yourself (`rm`, or `find .harness -name 'STEER.consumed-*.md' -mtime +30 -delete`) |
| `auto-save/<ts>` (branch) | the hook | recover (below), then `git branch -D auto-save/<ts>` to remove |

All per-repo. (Device-scope halting — one `STOP` for every session — is future work.)

## Usage

**Halt a runaway session** — in another terminal at the repo root:

```bash
touch .harness/STOP     # next tool call is blocked; rm .harness/STOP to resume
```

**Redirect mid-run** — write the correction; the next tool call injects it into context:

```bash
cat > .harness/STEER.md <<'EOF'
Use the existing helper at src/utils.py:format_record() instead of writing a new one.
EOF
```

To **halt *and* redirect**, write `STEER.md` first, then `touch .harness/STOP`. When you `rm` STOP, the next call passes kill-switch, then steer injects the redirect.

**Recover crashed work** — `commit-on-stop` saved each dirty turn to a branch:

```bash
git branch -a | grep auto-save                        # find the safety branches
git checkout auto-save/<ts>                            # keep working there, or…
git checkout main && git cherry-pick auto-save/<ts>    # …bring the commit onto main
```

The hook never modifies your current branch or pushes — recovery is always your call.

## Ordering

`kill-switch` and `steer` both fire on `PreToolUse`. The plugin's `hooks.json` declares them in order — **kill-switch before steer** — so a halt always wins: when `.harness/STOP` is present, the call is blocked before `steer` reads `STEER.md`.

> Re-audit on every Claude Code release: if hook firing ever stops being declaration-ordered, this invariant breaks. The rationale + the re-audit trigger live in [ADR 0003](0003-base-operator-hooks).

## Troubleshooting

- **A hook didn't fire.** Confirm the plugin is enabled — `claude plugin list` shows `developer-safety`. The hooks run from the plugin (`${CLAUDE_PLUGIN_ROOT}/hooks/…`), not from `.claude/hooks/`; re-sync with `claude plugin install developer-safety@crickets`.
- **`.harness/STOP` ignored.** The check matches a regular file — `touch` it, don't `mkdir`. It's resolved against the session's cwd (the repo root).
- **No `STEER.consumed-*` file.** The hook renames only on a successful read; if a filesystem-permission error blocks the rename, the steer still prints but the file stays.
- **No `auto-save` branch.** A silent no-op when git is absent, you're not in a work tree, or the tree is already clean. Two `Stop` events in the same second can collide on the branch name (rare) — the first wins; recover the second from a stash.

## Manual fallback (Antigravity)

Antigravity has no first-class hook surface, so the hooks run observe-only. Approximate them with an always-on rule (`.agents/rules/operator-control.md`):

```markdown
Before each step, check the repo root:
- `.harness/STOP` present → halt; don't proceed until the operator removes it.
- `.harness/STEER.md` present → apply it as a redirect, then rename it to
  `.harness/STEER.consumed-<ts>.md`. If both exist, halt wins.
At the end of a change with a dirty tree, save it to an `auto-save/<ts>` branch.
```

Best-effort — the agent has to remember to check, and it lacks the Claude Code hook's before-every-tool-call precision.

## See also

- [Hooks](Hooks) — the full hook catalog + how hooks work.
- [Compatibility](Compatibility) — per-host hook effectiveness.
- [Install crickets plugins](Install-Into-Project) — get `developer-safety` onto your host.
- [Modify a crickets plugin](Modify-A-Plugin) — edit the hook scripts and dogfood.
- [ADR 0003 — base operator hooks](0003-base-operator-hooks) — the design rationale + re-audit triggers.
