---
name: token-audit
description: Print a deterministic cost breakdown for a Claude Code session transcript — total cost, cache-read vs cache-write vs fresh-input split (% served from cache), 5h rolling window sums, floor breakdown, and per-message cost curve.
kind: command
supported_hosts: [claude-code]
version: 0.1.0
install_scope: project
argument-hint: "[--session <session-id>] [--by-phase]"
---

You are running `/token-audit` — a deterministic cost analyzer for Claude Code session transcripts. All numbers come from `message.usage` fields in the JSONL + a pinned pricing table. No LLM estimation.

**Arguments:** $ARGUMENTS

## What to do

1. **Resolve the session JSONL path.**

   - If `--session <id>` is given, look for the JSONL at `~/.claude/projects/<cwd-slug>/<id>.jsonl` where `<cwd-slug>` is the current working directory with `/` → `-` (same convention Claude Code uses for project storage).
   - Otherwise, check the `CLAUDE_SESSION_ID` environment variable.
   - If neither is present, scan `~/.claude/projects/<cwd-slug>/` for the most-recently modified `.jsonl` file and use it. Print a note: `Using most-recent session: <id>`.
   - If no JSONL is found, print: `No session transcript found. Pass --session <id> to specify one.` and stop.

2. **Run the analyzer.**

   Call `${CLAUDE_PLUGIN_ROOT}/scripts/analyzer.py` with the resolved path. Parse the returned `SessionReport`. Pass `--by-phase` through to enable phase attribution.

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/analyzer.py" <path> [--by-phase]
   ```

   The script prints structured output; parse and reformat for display.

3. **Print the report in this order:**

   ### Headline
   ```
   ── Token Audit ──────────────────────────────────
   Session:  <session-id or path>
   Total:    $X.XXXXXX
   Cached:   XX.X% served from cache
   ─────────────────────────────────────────────────
   ```

   ### Cache split
   ```
   Cache split (prompt tokens)
     Fresh input:   N,NNN tokens   $X.XXXXXX
     Cache write:   N,NNN tokens   $X.XXXXXX
     Cache read:    N,NNN tokens   $X.XXXXXX
     Output:        N,NNN tokens   $X.XXXXXX
   ```

   ### Per-message table
   ```
   # │ Timestamp            │ Model              │ Cost       │ In    │ CW   │ CR    │ Out
   ──┼──────────────────────┼────────────────────┼────────────┼───────┼──────┼───────┼────
   1 │ 2026-06-14T00:02:00Z │ claude-opus-4-8    │ $0.020000  │  1000 │ 2000 │     0 │ 100
   …
   ```
   Columns: `#`, `Timestamp` (ISO), `Model`, `Cost`, `In` (fresh input), `CW` (cache write), `CR` (cache read), `Out` (output).

   ### 5h window sums
   ```
   5h windows
     Window 1  started 2026-06-14T00:02:00Z  3 messages  $0.038000
     Window 2  started 2026-06-14T06:32:00Z  1 message   $0.000650
   ```

   ### Floor breakdown
   ```
   Floor (always-load surface — zero cache hits)
     N messages   $X.XXXXXX   (X.X% of total)
   ```

   ### Phase breakdown (only with `--by-phase`)
   ```
   By phase
     plan   2 messages   $0.029000
     work   2 messages   $0.009650
   ```

4. **Implementation note for the operator.**

   The analyzer logic lives in `${CLAUDE_PLUGIN_ROOT}/scripts/analyzer.py`; the pricing table in `${CLAUDE_PLUGIN_ROOT}/scripts/pricing.py`. Both are pure Python stdlib — no dependencies. Part C (status-line meter) reuses `pricing.py` directly.

   To update pricing: edit `src/token-audit/scripts/pricing.py` and regen `dist/` with `python3 scripts/generate.py build`.

## Recoverability gate

Before any operation, check recoverability:
- **All operations here are read-only** (transcript JSONL is never written). Announce the resolved session path and proceed — no confirmation needed.
- If the JSONL path cannot be resolved, report clearly and stop (no crash, no silent empty output).
