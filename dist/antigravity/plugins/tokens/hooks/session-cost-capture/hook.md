---
name: session-cost-capture
description: "Stop-hook capture of a closing session's token cost. Runs analyzer.py over the session transcript and writes one `kind: session-cost` memory entry per model observed ({model, tokens_by_kind, cost_usd, timestamp}) via agentm's memory-write path. Capture-half only — graceful no-op when no memory backend is configured; never blocks session close."
kind: hook
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

# session-cost-capture — the capture half of the session-cost Stop hook

Absorbed from the never-staged `PLAN-session-cost-capture` micro-plan (2026-07-05 ROADMAP-SESSION decision record: BUILD-NOW, capture-half only). This hook is the empirical-data source the fan-out cost gate (`fanout_cost_gate.py`'s `observed_records` param) was built to consume — before this hook exists, the gate's per-agent estimate always falls back to `pricing.cost_usd` over a fixed usage profile; after it accumulates real sessions, the gate can average real `cost_usd` observations per model instead.

## How it works

- **Trigger:** Claude Code's `Stop` event (matcher `.*`) — fires at the end of each agent turn/session.
- **Parse:** reads the Stop payload's `session_id` + `cwd` from stdin (same fields + transcript-path formula as agentm's `memory-reflect-stop` hook: `~/.claude/projects/<cwd-slug>/<session_id>.jsonl`).
- **Analyze:** invokes `session_cost_writer.py <transcript> --project <slug>`, which:
  1. Resolves the vault path (`MEMORY_VAULT_PATH` env → `.agentm-config.json::vault_path` → none).
  2. Loads agentm's `save.py` bridge (graceful-skip if agentm is unresolvable).
  3. Runs `analyzer.analyze_session()` over the transcript, groups per-message records by `model`.
  4. Writes one `kind: session-cost` entry per model via `save_entry()`, body carrying `{model, tokens_by_kind, cost_usd, timestamp}`.
- **Exit 0** always — a capture failure (missing vault, missing agentm, malformed transcript, a same-second slug collision) is caught and logged to stderr, never raised.

## What it does NOT do

- **No dreaming-pass trend analysis.** Longitudinal cost-creep review across accumulated `session-cost` records is a separate, explicitly-gated stub (`dreaming_trend_stub.py`) pending Wave-E's dreaming-pass infrastructure. This hook only captures; it never reads its own history back.
- **No blocking.** Every failure mode degrades to a silent (or stderr-noted) no-op — a missing memory backend must never prevent a session from closing.

## Failure modes

- **No stdin payload / no `session_id` / no python3:** exit 0, no-op.
- **Transcript not found at the computed path:** exit 0, no-op.
- **No vault resolved, or agentm unresolvable:** `session_cost_writer.py` writes nothing; exits 0.
- **Slug collision (same model + same-second timestamp) or invalid project slug:** that one model's write is skipped; other models in the same session still get written.

## See also

- [`fanout_cost_gate.py`](../../scripts/fanout_cost_gate.py) — the consumer this hook feeds real data to.
- [`dreaming_trend_stub.py`](../../scripts/dreaming_trend_stub.py) — the correctly-gated-dark sibling hook (task 3).
- `commit-on-stop` (developer-safety plugin) — sibling Stop hook this one's workspace-resolution conventions are modeled on.
