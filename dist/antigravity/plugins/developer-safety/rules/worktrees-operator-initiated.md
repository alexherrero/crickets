---
name: worktrees-operator-initiated
description: Git worktrees are a first-class workflow, but always operator-initiated — never spawn one autonomously; work on the current branch unless the operator hands you one (e.g. a `/work` run with the worktree-per-plan opt-in).
kind: snippet
supported_hosts: [antigravity]
version: 0.2.1
trigger: always_on
---

## Worktrees — operator-initiated, never autonomous

Git worktrees are a **first-class** part of the workflow: `/work` runs a named plan in its own checkout when the project opts in with `isolation.mode: worktree-per-plan` (it creates the worktree, binds it to that plan, and lands the plan as a PR with auto-merge), and several plans can run concurrently without colliding in one tree. Worktrees are not something to avoid.

What stays prohibited is **autonomous** worktree creation. Never spawn a worktree on your own — not as cleanup, not as a convenience for another task, not as a side effect. Creating a worktree is an **operator-initiated** act: the operator either sets the durable opt-in that `/work` reads (their config *is* the initiation) or explicitly asks for one. Absent that, work directly on the current branch (typically `main`).

The line is initiation, not the worktree itself: a worktree the operator asked for is expected; a worktree you decided to make is the failure mode.
