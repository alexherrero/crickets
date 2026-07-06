---
name: harness-context-session-start
description: On SessionStart, inject the project's .harness/PLAN.md + progress.md paths into session context so the agent reads the plan before plan-status questions or phase commands. Silent no-op when no .harness/ state is present.
kind: hook
supported_hosts: [claude-code]
version: 0.1.0
install_scope: project
---

# harness-context-session-start — surface the harness state at session boot

A `SessionStart` hook that tells the agent **where this project's phase-gated state lives** on every session boot, so it reads `PLAN.md` before answering plan-status questions or running `/work`, `/review`, `/release`.

## How it works

- **Trigger:** Claude Code's `SessionStart` event (matcher `.*`).
- **Reads** the event JSON from stdin and extracts `cwd` (the event cwd, not `$PWD`); falls back to `pwd`.
- **Checks** for `<cwd>/.harness/PLAN.md` **and** `<cwd>/.harness/progress.md`.
- **If both exist:** emits a short context block naming the two paths + the "read PLAN.md first" instruction (stdout becomes session context on `SessionStart`). A transparency line goes to stderr.
- **If not:** silent no-op (stderr note only). Never blocks boot.

## Standalone + storage-agnostic

This checks plain `.harness/` state in the repo — the standalone default. If a memory/storage layer (e.g. agentm's MemoryVault) is hosting the loop, that layer ships its **own** context hook that redirects to wherever it keeps state; the two are independent (parallel-run until the V5 kernel split removes the duplicate).

## Host support

**Claude-only.** `SessionStart` has no Antigravity equivalent, so this hook is declared `supported_hosts: [claude-code]` — the Antigravity plugin does not carry it. (This mirrors the documented SessionStart gap: hooks bound to events Antigravity lacks don't ship to that host.)

## Failure modes

- **python3 unavailable / malformed event JSON:** falls back to `pwd`; still works if invoked from the project root.
- **No `.harness/` state:** silent no-op — exactly the case for a fresh repo or a non-harness project.
- **Always exits 0** — a SessionStart hook must never block session boot.

## Triggers

- **SessionStart event only.** Fires once per session boot.
