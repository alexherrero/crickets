---
name: session-cost-capture
description: "Stop-hook capture of a closing session's token cost. Runs analyzer.py over the session transcript and appends one `session-cost` telemetry event per model observed ({model, tokens_by_kind, cost_usd, tags}) to the device-local event log. Capture-half only — graceful no-op when the event log is unwritable; never blocks session close."
kind: hook
supported_hosts: [claude-code, antigravity]
version: 0.2.0
install_scope: project
---

# session-cost-capture — the capture half of the session-cost Stop hook

Absorbed from the never-staged `PLAN-session-cost-capture` micro-plan (2026-07-05 ROADMAP-SESSION decision record: BUILD-NOW, capture-half only). This hook is the empirical-data source the fan-out cost gate (`fanout_cost_gate.py`'s `observed_records` param) was built to consume — before this hook exists, the gate's per-agent estimate always falls back to `pricing.cost_usd` over a fixed usage profile; after it accumulates real sessions, the gate can average real `cost_usd` observations per model instead.

**Retargeted off the vault (PLAN-observability-ledger, `wiki/designs/agentm-autonomy.md`).** This hook used to write markdown into the Obsidian vault via agentm's `save_entry()` bridge; it now appends JSON lines to a device-local event log instead — no agentm dependency, no vault write.

## How it works

- **Trigger:** Claude Code's `Stop` event (matcher `.*`) — fires at the end of each agent turn/session.
- **Parse:** reads the Stop payload's `session_id` + `cwd` from stdin (same fields + transcript-path formula as agentm's `memory-reflect-stop` hook: `~/.claude/projects/<cwd-slug>/<session_id>.jsonl`).
- **Analyze:** invokes `session_cost_writer.py <transcript> --session-id <sid>`, which:
  1. Runs `analyzer.analyze_session()` over the transcript, groups per-message records by `model`.
  2. Resolves attribution tags (`{plan, task, arc, grade}`) from the worktree-local `.harness/active-plan` marker.
  3. Appends one `session-cost` event per model to `~/.agentm/telemetry/events-YYYYMM.jsonl` (`$AGENTM_TELEMETRY_DIR`-overridable), carrying `{model, tokens_by_kind, cost_usd, tags}`.
- **Exit 0** always — a capture failure (malformed/missing transcript, an unwritable telemetry path) is caught and logged to stderr, never raised.

## What it does NOT do

- **No dreaming-pass trend analysis.** Longitudinal cost-creep review across accumulated events is a separate, explicitly-gated stub (`dreaming_trend_stub.py`) pending Wave-E's dreaming-pass infrastructure. This hook only captures; it never reads its own history back.
- **No blocking.** Every failure mode degrades to a silent (or stderr-noted) no-op — an unwritable event log must never prevent a session from closing.

## Failure modes

- **No stdin payload / no `session_id` / no python3:** exit 0, no-op.
- **Transcript not found at the computed path:** exit 0, no-op.
- **Event log unwritable (permissions, missing parent):** `session_cost_writer.py` writes nothing; exits 0.

## See also

- [`fanout_cost_gate.py`](../../scripts/fanout_cost_gate.py) — the consumer this hook feeds real data to.
- [`dreaming_trend_stub.py`](../../scripts/dreaming_trend_stub.py) — the correctly-gated-dark sibling hook (task 3).
- `commit-on-stop` (developer-safety plugin) — sibling Stop hook this one's workspace-resolution conventions are modeled on.
