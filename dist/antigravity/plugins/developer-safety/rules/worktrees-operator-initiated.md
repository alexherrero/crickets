---
name: worktrees-operator-initiated
description: Git worktrees are a first-class workflow, but always operator-initiated — never spawn one autonomously; work on the current branch unless the operator hands you a worktree (e.g. via /spawn-worker).
kind: snippet
supported_hosts: [antigravity]
version: 0.2.0
install_scope: project
---

## Worktrees — operator-initiated, never autonomous

Git worktrees are a **first-class** part of the workflow: the coordinator flow hands a named plan to a worker in its own checkout (`/spawn-worker` creates a `worker/<name>` worktree pre-bound to that plan), and several workers can run concurrently without colliding in one tree. Worktrees are not something to avoid.

What stays prohibited is **autonomous** worktree creation. Never spawn a worktree on your own — not as cleanup, not as a convenience for another task, not as a side effect. Creating a worktree is an **operator-initiated** act: the operator either runs the sanctioned command (`/spawn-worker`, where their invocation *is* the initiation) or explicitly asks for one. Absent that, work directly on the current branch (typically `main`).

The line is initiation, not the worktree itself: a worktree the operator asked for is expected; a worktree you decided to make is the failure mode.
