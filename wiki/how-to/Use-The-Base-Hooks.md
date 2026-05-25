# How to use the base operator-control hooks

> [!NOTE]
> **Goal:** Use `kill-switch`, `steer`, and `commit-on-stop` to keep precise control over a long-running Claude Code session — halt at a tool call, redirect mid-run, recover from a crash.
> **Prereqs:** `crickets` installed into the target project (so the three hook scripts land at `.claude/hooks/` and their event registrations land in `.claude/settings.json`); the target is a git repo.

## The three hooks at a glance

| Hook | Event | Trigger file / signal | Effect |
|---|---|---|---|
| [`kill-switch`](https://github.com/alexherrero/crickets/blob/main/hooks/kill-switch/hook.md) | `PreToolUse` (every tool call) | `<repo>/.harness/STOP` exists | Block the tool call (exit 2 + halt-message stderr) |
| [`steer`](https://github.com/alexherrero/crickets/blob/main/hooks/steer/hook.md) | `PreToolUse` (every tool call) | `<repo>/.harness/STEER.md` exists | Print contents to stdout (Claude Code injects into agent context); rename file to `STEER.consumed-<iso-ts>.md` |
| [`commit-on-stop`](https://github.com/alexherrero/crickets/blob/main/hooks/commit-on-stop/hook.md) | `Stop` event (end of each turn) | working tree is dirty | Create `auto-save/<iso-ts>` branch and commit all changes there; return HEAD to original branch with clean tree |

All three are **Claude-Code-only** for v0.7.0. Manual equivalents for Antigravity and Gemini CLI are below.

## When you'd reach for each one

| Situation | Reach for |
|---|---|
| Agent is in a runaway iteration loop | **kill-switch** — `touch .harness/STOP` |
| You want to redirect a multi-step plan mid-run without restart | **steer** — write the redirect to `.harness/STEER.md` |
| You realize the agent made a wrong assumption you'd already corrected | **steer** — write the correction to `.harness/STEER.md` |
| You're about to step away; want a safety net for any in-flight work | **commit-on-stop** — fires automatically; no action needed |
| Claude Code crashed or you closed it mid-task | After restart: check `git branch -a | grep auto-save` for the safety branch (created by **commit-on-stop**) |

## Three worked scenarios

### Scenario 1 — Halt a runaway iteration loop

The agent is bouncing between two failing approaches and you want to break the loop without ending the session.

```bash
# In a separate terminal at the project root:
touch .harness/STOP
```

On the next `PreToolUse` event (any tool call), `kill-switch` checks for the file, sees it, exits 2 with the message:

```
kill-switch: .harness/STOP present — halting tool call. Remove the file (rm .harness/STOP) to resume.
```

Claude Code surfaces the stderr to the agent and blocks the tool call. The agent learns the session is halted; further calls will keep failing.

**To resume:**

```bash
rm .harness/STOP
```

Next tool call proceeds normally.

**Tip:** if you want to halt *and* redirect, write `.harness/STEER.md` first, then `touch .harness/STOP`, then later `rm .harness/STOP`. When you remove STOP, the next tool call: kill-switch passes → steer fires → contents injected → file renamed → agent reads the redirect.

### Scenario 2 — Redirect mid-run after spotting a wrong assumption

The agent is implementing a new helper but you realize there's an existing one in `src/utils.py` it should reuse.

```bash
# In a separate terminal at the project root:
cat > .harness/STEER.md <<'EOF'
There's already a helper for this at src/utils.py:format_record(). Please use it instead of writing a new one. If it needs a small tweak, edit it in place rather than duplicating.
EOF
```

On the next `PreToolUse` event:

1. `kill-switch` runs first (alphabetical install order): no STOP file → pass.
2. `steer` runs: STEER.md exists → prints contents to stdout (Claude Code captures and injects into the upcoming tool call's context) → renames the file to `.harness/STEER.consumed-20260514T070530Z.md` (UTC timestamp).

The agent sees the redirect in context, adjusts, and the audit-trail file remains for forensics.

**Multi-line guidance works the same way** — STEER.md is read in its entirety.

### Scenario 3 — Recover from a crashed (or closed-mid-task) session

You're working on a feature, Claude Code's session ends (crash, window-close, machine-reboot), and you re-open later. The tree has uncommitted work that you don't want to lose.

Because `commit-on-stop` fires on Claude Code's `Stop` event (end of each agent turn), each turn that left a dirty tree already created a safety branch:

```bash
# Find safety branches:
git branch -a | grep auto-save

# Example output:
#   auto-save/20260514T064430Z
#   auto-save/20260514T070530Z
#   auto-save/20260514T072315Z   <-- the most recent one

# Inspect the most recent
git log --oneline auto-save/20260514T072315Z -3
# Example commit:
#   abc1234 auto-save: stop at 20260514T072315Z on branch main

git diff main..auto-save/20260514T072315Z
```

**Recovery options:**

```bash
# Option A — switch to the safety branch and keep working there
git checkout auto-save/20260514T072315Z

# Option B — cherry-pick the saved commit onto your original branch
git checkout main
git cherry-pick auto-save/20260514T072315Z

# Option C — bring just the changes back as uncommitted edits
git checkout main
git checkout auto-save/20260514T072315Z -- .
# Now your working tree has the saved changes on top of main
```

The hook **never** modifies your current branch or pushes to remote — recovery is always your decision.

## Hook ordering within events (load-bearing invariant)

`kill-switch` and `steer` both fire on `PreToolUse`. Within a single event, hooks run in **registration order**. The toolkit installer registers hooks in **alphabetical** order from the toolkit's `hooks/` directory:

```
hooks/
├── commit-on-stop/   (Stop event — separate from PreToolUse)
├── kill-switch/      (PreToolUse, registered first)
└── steer/            (PreToolUse, registered second)
```

This means: **on any tool call, `kill-switch` runs before `steer`**. If `.harness/STOP` is present, the tool call is blocked **before** `steer` reads `.harness/STEER.md`. A halt always takes precedence over a steer.

If Claude Code ever changes hook event semantics from "registration order" to something else (e.g. concurrent firing), this invariant breaks. Re-audit on every Claude Code release. See [ADR 0003](0003-base-operator-hooks) for the full rationale.

## File conventions (locked v0.7.0)

| Convention | Location | Owner | Lifecycle |
|---|---|---|---|
| Halt signal | `<repo>/.harness/STOP` | Operator | Touch to halt; `rm` to resume |
| Steer instruction | `<repo>/.harness/STEER.md` | Operator (write); hook (rename after read) | Hook renames to `STEER.consumed-<iso-ts>.md` after consumption |
| Steer audit trail | `<repo>/.harness/STEER.consumed-*.md` | Hook (write); operator (clean up) | Hook never deletes; operator periodically `rm` or `git mv` |
| Safety branches | `auto-save/<iso-ts>` in `<repo>` | Hook (create + commit); operator (recover + clean up) | Hook never deletes; operator `git branch -D auto-save/<ts>` to remove |

Per-repo only — device-scope (`~/.harness/STOP` halting all sessions globally) is deferred to a future `dev-machine-setup` plan.

## Cleanup

**Steer audit trail:** files accumulate at `.harness/STEER.consumed-*.md`. They're small (the original STEER.md contents). Periodically:

```bash
# Remove all consumed-steer files older than 30 days
find .harness -name 'STEER.consumed-*.md' -mtime +30 -delete

# Or just nuke them all if you don't want the history
rm .harness/STEER.consumed-*.md
```

**Safety branches:** `auto-save/*` branches accumulate. Periodically:

```bash
# List safety branches with commit dates
git for-each-ref --format='%(refname:short) %(committerdate:iso8601)' refs/heads/auto-save/

# Delete a specific one
git branch -D auto-save/20260513T230400Z

# Nuke them all (if you're sure)
git branch | grep auto-save/ | xargs git branch -D
```

Auto-cleanup is **not** part of v0.7.0 — operators manage their own hygiene.

## Manual equivalents for other hosts

Antigravity and Gemini CLI have no first-class hook surface today (v0.7.0). The manual equivalents:

### Antigravity

Add an always-on rule (`.agent/rules/operator-control.md` or equivalent):

```markdown
Before each step, check the project root for these files:

1. `.harness/STOP` — if present, halt and tell the operator the session
   is halted; do not proceed until the operator removes it.
2. `.harness/STEER.md` — if present, read its contents as a redirect from
   the operator. Apply it to the next step. After reading, rename the
   file to `.harness/STEER.consumed-<iso-timestamp>.md` for the audit trail.

If both are present: halt wins. STEER.md remains untouched until STOP is removed.
```

Best-effort — the agent has to remember to check on every step. Doesn't have the precision of the Claude Code hook (which fires before every tool call without agent involvement).

### Gemini CLI

Include the same instruction in `AGENTS.md` or the operator prompt at session start. Same best-effort caveat.

### commit-on-stop equivalent

Both Antigravity and Gemini CLI lack a `Stop`-style event. Manual equivalent: include in the always-on rule / operator prompt:

```markdown
At the end of each task or significant change, if the working tree has
uncommitted changes, run:

  git stash push --include-untracked -m "auto-save-<iso-timestamp>"
  git branch auto-save/<iso-timestamp>
  git stash apply <stash-ref-from-previous-step>

So the operator can recover via `git checkout auto-save/<timestamp>`.
```

This requires the agent to remember + execute correctly, which is less reliable than the Claude Code hook. Use Claude Code for the strongest crash-recovery guarantee.

## Troubleshooting

### Hook didn't fire

1. Check that `crickets` is installed into the target: `ls .claude/hooks/` should show `kill-switch.sh`, `steer.sh`, `commit-on-stop.sh` (POSIX) or the `.ps1` variants on Windows.
2. Check `.claude/settings.json` has the event registrations: `cat .claude/settings.json | python3 -m json.tool` and look for `hooks.PreToolUse` (containing kill-switch + steer) and `hooks.Stop` (containing commit-on-stop).
3. Verify scripts are executable (POSIX): `ls -la .claude/hooks/*.sh` should show `-rwxr-xr-x`.
4. Re-install with `bash crickets/install.sh --update <project>` to refresh.

### STOP file ignored

1. `[[ -f .harness/STOP ]]` only matches **regular files**. If `.harness/STOP` is a directory or symlink, the hook treats it as absent. Use `touch`, not `mkdir`.
2. The hook checks `.harness/STOP` relative to the current working directory. Claude Code runs with cwd at the project root; confirm cwd matches your repo with `pwd` from inside the session.

### STEER.consumed file not appearing

1. The hook only renames on successful read. If the rename fails (filesystem permissions), the contents print to stdout but the file isn't renamed. Check filesystem ACLs.
2. The hook exits 0 even on rename failure — it doesn't surface the rename error to the agent. Check the Claude Code hook log if available.

### Auto-save branch not created

1. The hook exits 0 silently if (a) git unavailable, (b) not in a git work tree, (c) working tree is already clean. None of these are errors; they're correct no-ops.
2. If the working tree has changes but no branch was created: check `git status` shows the dirty tree, check `git branch -a` for the auto-save branch (it may have been created on a different turn), check Claude Code's hook log.

### Multiple `auto-save/<ts>` branches with identical timestamps

The timestamp is UTC-resolution-to-the-second. Two Stop events firing in the same second would collide on the branch name. Rare in practice (Stop events don't fire that fast). If it happens, the second attempt fails with `fatal: A branch named 'auto-save/<ts>' already exists.`; the first branch is preserved and the second turn's changes remain uncommitted. Recover manually with a stash.

### `.claude/settings.json` malformed

Hooks won't load. Validate with `python3 -m json.tool .claude/settings.json`. If it's broken, the toolkit installer's idempotent re-merge will fix it: `bash crickets/install.sh --update <project>`.

## Related

- [`kill-switch` hook spec](https://github.com/alexherrero/crickets/blob/main/hooks/kill-switch/hook.md)
- [`steer` hook spec](https://github.com/alexherrero/crickets/blob/main/hooks/steer/hook.md)
- [`commit-on-stop` hook spec](https://github.com/alexherrero/crickets/blob/main/hooks/commit-on-stop/hook.md)
- [ADR 0003 — base operator hooks](0003-base-operator-hooks) — design rationale.
- [Customization Types](Customization-Types) — what `kind: hook` means + v0.7.0 installer support.
- [Per-Host Paths](Per-Host-Paths) — where the hook scripts + settings fragments land.
- [agentm `/work` § long-running operator-control hooks](https://github.com/alexherrero/agentm/blob/main/harness/phases/03-work.md) — harness-side dispatch documentation.
