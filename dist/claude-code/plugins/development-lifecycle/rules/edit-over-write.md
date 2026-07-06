---
name: edit-over-write
description: Prefer Edit to Write for existing files; Write only for new files or near-total rewrites.
kind: rule
supported_hosts: [claude-code, antigravity]
version: 0.1.0
---

## Edit-over-Write

Prefer `Edit` to `Write` for existing files. Reserve `Write` for new files or near-total rewrites.

**Why this matters (billed-output explanation):** `Write` re-emits the whole file as output tokens — roughly 5× the cost of the equivalent `Edit`, which emits only the changed strings. On a bounded token budget (the standing all-day-autonomous-coding goal), the difference compounds across every session: a five-file patch that uses `Write` burns as many output tokens as writing those files from scratch.

**The rule in one line:** When the file exists, use `Edit`. When the file is new or you are replacing nearly all of it, use `Write`.
