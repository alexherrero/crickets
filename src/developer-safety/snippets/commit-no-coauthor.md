---
name: commit-no-coauthor
description: Never append a Co-Authored-By trailer naming the agent or model to commit messages — the user is the sole author of intent.
kind: snippet
supported_hosts: [antigravity]
version: 0.1.0
install_scope: project
---

## Commit messages — no `Co-Authored-By` trailer

Do not append a `Co-Authored-By:` trailer naming the agent or model (`Co-Authored-By: Claude`, `Co-Authored-By: Gemini`, etc.) to git commit messages. The user is the sole author of intent — the agent is the tool, not a co-author. Plain commit message only, on every commit, unless the user explicitly opts in for a specific commit.

This holds regardless of which host you're running in. If your host injects the trailer automatically, strip it before finalizing the commit.
