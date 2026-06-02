---
name: commit-on-stop
description: Non-disruptive safety snapshot at Stop. Fires on Claude Code's Stop event; if the working tree has uncommitted changes, records a full snapshot (tracked + untracked) as a commit object on the side ref `refs/auto-save/<iso-timestamp>` without switching branches, moving HEAD, or touching the working tree. Concurrency-safe; never pushes to remote.
kind: hook
supported_hosts: [claude-code]
version: 0.2.0
install_scope: project
---

# commit-on-stop — non-disruptive safety snapshot at Stop

A Stop-event hook that snapshots the agent's uncommitted work at the end of each turn so crashed or interrupted sessions stop losing in-flight work. Unlike the original design, it **never touches your working tree or current branch** — it records the snapshot on a hidden side ref and leaves everything exactly as the agent left it.

## How it works

- **Trigger:** Claude Code's `Stop` event (matcher `.*`) — fires at the end of each agent turn.
- **Check:** is the working tree dirty (uncommitted changes per `git status --porcelain`)?
- **If clean:** exit 0 (no-op). Nothing to save.
- **If dirty:**
  1. Capture UTC timestamp → ref `refs/auto-save/<YYYYMMDDTHHMMSSZ>`.
  2. Build a tree from the full working state in a **temporary index** (`GIT_INDEX_FILE`), seeded from HEAD then `git add -A` (tracked + untracked; `.gitignore` is honored, so build junk stays out). The real index is never touched.
  3. `git commit-tree` that tree (parented on HEAD) into a commit object.
  4. `git update-ref refs/auto-save/<ts>` to publish the snapshot atomically.
  5. Prune to the most recent 10 snapshots.
- **Exit 0** with a stderr line naming the ref + recovery command.

After the hook fires:

- HEAD, the current branch, the index, and the working tree are **all unchanged** — your in-flight edits are still right there.
- A full snapshot is preserved as a commit on `refs/auto-save/<ts>` (a hidden ref — it does **not** show up in `git branch`).

## Why the snapshot model (vs the old stash + branch design)

The previous version stashed the changes, created an `auto-save/<ts>` **branch**, checked out to it, committed, and checked back to the original branch — leaving the working tree *clean*. That had three problems this version fixes:

- **Surprise data movement.** It parked your uncommitted work off the current branch every turn, so multi-turn agent work kept "losing" its in-flight edits (they were recoverable, but it looked like a reset).
- **Branch switching.** `git checkout` changes the branch for the *whole* working tree — unsafe the moment two agents (or an orchestrator + sub-agents) share one tree.
- **Same-second collisions.** Creating a branch could fail if two Stop events fired in the same second, aborting the hook mid-checkout.

The snapshot model is **concurrency-safe**: it only ever writes a ref and never mutates the working tree, so independent Stop events (multiple agents, even in one tree) don't collide, and an agent's edits survive across turns.

## Operator usage — recovery

```bash
# List snapshots (newest first)
git for-each-ref --sort=-refname --format='%(refname) %(committerdate:iso8601)' refs/auto-save

# Inspect what a snapshot captured
git show refs/auto-save/20260530T154401Z

# Restore a snapshot's files into your working tree
git checkout refs/auto-save/20260530T154401Z -- .

# Or branch off it to work from there
git switch -c recovered refs/auto-save/20260530T154401Z
```

## Operator usage — cleanup

Snapshots are **auto-pruned to the most recent 10**, so they don't accumulate. To prune further or clear them all:

```bash
# Delete one
git update-ref -d refs/auto-save/20260530T154401Z

# Delete all of them
git for-each-ref --format='%(refname)' refs/auto-save | xargs -n1 git update-ref -d
```

> **Migration note (v0.2.0):** older installs created `auto-save/<ts>` **branches** (under `refs/heads/`). Those remain until you delete them — `git branch | grep auto-save/ | xargs git branch -D`. New snapshots live under `refs/auto-save/` (hidden refs) instead.

## What it never does

- **Never mutates the working tree or index.** Your uncommitted edits are left exactly in place.
- **Never switches branches or moves HEAD.** The snapshot goes on a side ref; the current branch points where it did.
- **Never pushes to remote.** Local-only safety net.
- **Never signs or prompts.** `commit-tree` (unlike `commit`) ignores `commit.gpgsign`, so a signing prompt can't hang the non-interactive hook.
- **Never runs in a non-git directory.** Exit 0 if `git rev-parse --is-inside-work-tree` fails.

## Commit identity

Snapshots are authored as `commit-on-stop hook <commit-on-stop@crickets.local>`, set via `GIT_AUTHOR_*` / `GIT_COMMITTER_*` env vars scoped to the hook process — they never pollute `git config`.

## Failure modes

- **git missing / not a git work tree:** silently exits 0 (no-op).
- **Unborn branch (no commits yet):** snapshots against an empty tree (no parent) — still captures untracked files.
- **commit-tree / update-ref fails:** the hook may not record a snapshot, but the working tree is **never** left in a bad state (it was never touched). Re-runs on the next Stop.
- **Prune failure:** best-effort and non-fatal — the snapshot is already saved.
- **`.claude/settings.json` malformed:** hooks won't load. Validate JSON.

## Triggers

- **Stop event only.** Fires at the end of each agent turn.

## See also

- [`kill-switch`](../kill-switch/hook.md) — companion emergency-halt hook.
- [`steer`](../steer/hook.md) — companion mid-run-redirect hook.
- [How to use the base hooks](../../wiki/how-to/Use-The-Base-Hooks.md) — practical scenarios for all three.
- [ADR 0003 — base operator hooks](../../wiki/explanation/decisions/0003-base-operator-hooks.md) — design rationale.
