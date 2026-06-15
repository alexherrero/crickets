---
name: compact-nudge-resume
description: On every user prompt, nudge toward /clear over /compact when the session context is large. Silent no-op below threshold or on a brand-new session.
kind: hook
supported_hosts: [claude-code]
version: 0.1.0
install_scope: project
---

# compact-nudge-resume — /clear-not-/compact nudge on large context

A `UserPromptSubmit` hook that fires on every user prompt. When the session
context is large (≥ 60 % or > 400 assistant turns in the session JSONL), it
injects an `additionalContext` nudge reminding the operator that `/clear` is
cheaper than `/compact`. Below the threshold or on a brand-new session:
**silent no-op**.

## How it works

- **Trigger:** `UserPromptSubmit` (matcher `.*`).
- **Context size check — two paths (priority order):**
  1. `CLAUDE_CONTEXT_USAGE_PERCENTAGE` environment variable (direct signal from
     CC, or operator override) — used when present.
  2. Count of `type=assistant` lines in the session JSONL
     (`~/.claude/projects/<cwd-slug>/<CLAUDE_SESSION_ID>.jsonl`) as a proxy
     when the env var is absent. Threshold: > 400 assistant turns.
- **Resumed-session gate:** Only fires when the JSONL has at least one prior
  assistant line (session is not brand-new). A fresh session with zero assistant
  lines is always a silent no-op, regardless of the context-pct path.
- **Nudge payload:** A JSON object with `additionalContext` explaining the
  `/clear` vs `/compact` trade-off. If Part B's `pricing.py` is installed, the
  nudge includes a rough session cost estimate.
- **Test override:** Set `COMPACT_NUDGE_JSONL_PATH` to bypass the JSONL
  path derivation and point directly at a fixture file (tests only).

## Thresholds

| Signal | Threshold | Notes |
|---|---|---|
| `CLAUDE_CONTEXT_USAGE_PERCENTAGE` | ≥ 60 % | Override via env var |
| JSONL `type=assistant` count | > 400 lines | Proxy; may need tuning |

Re-audit trigger: if CC ships `CLAUDE_CONTEXT_USAGE_PERCENTAGE` or a native
hook input field for context size, tune the proxy threshold or remove the
JSONL fallback (DC-E from Part D locked design calls).

## Nudge-only ceiling

**Hooks cannot trigger `/compact` or `/clear`** — they can only surface text
via `additionalContext`. This is a permanent ceiling until the host exposes
actuation (re-audit trigger: CC ships a hook compaction/clear trigger). The
real enforcement signal is the status-line meter (Part C).

## Host support

**Claude Code only.** `UserPromptSubmit` has no Antigravity equivalent.

## Always exits 0

This hook must never block the user prompt. All errors are swallowed silently.
