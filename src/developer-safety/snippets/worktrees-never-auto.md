---
name: worktrees-never-auto
description: Never create git worktrees automatically — work directly on the current branch unless the user explicitly asks for a worktree.
kind: snippet
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

## Worktrees — never auto-create

Never create git worktrees automatically. Work directly on the current branch (typically `main`). Only enter a worktree session when the user explicitly asks for one.
