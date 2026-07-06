---
name: queue-status-lite
description: Read-only coordinator's glance — list every active plan in _harness/ with its Status and most-recent progress line. Surfaces, never mutates.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: [optional — "--harness-dir <path>" to enumerate a specific _harness/ directory; default resolves from the cwd]
---

You are running **queue-status-lite** — the coordinator's read-only glance at the plan queue. It lists every active plan in the (vault-backed) `_harness/` — for each, its name, its `Status:` line, and the most-recent entry of the matching `progress*.md` — and prints that dashboard. It is **not a gate** and it **mutates no state**: it reads and prints, nothing else.

**Arguments:** $ARGUMENTS — optionally `--harness-dir <path>` to enumerate a specific directory; with none, the directory is resolved from the cwd (vault-backed, or `<repo>/.harness/` locally).

> **Read-only by contract** (the V5-10 design call). There is no claim, no lease, no arbitration — the human is the arbiter of who works which plan. This command exists so a coordinator can *see* the queue before deciding; it never decides, never assigns, never records anything. The behavioral writers (the active-plan binding, role agent-defs, the integration/merge command) are separate, deferred work — not this command.

## Non-negotiable constraints

1. **Read-only — mutates no state.** This command never flips task status, never records progress, never binds or assigns a plan, never writes any file. If you find yourself about to write, you are out of scope — stop. It is the glance, not the gate.
2. **Surface the bridge's output verbatim.** Run the bridge and present its dashboard to the operator **verbatim** — do not parse, re-rank, summarize, or editorialize the rows. The bridge owns the format (so the local and agentm-backed renders agree); your job is to show it.
3. **Two backends, one contract — handled by the bridge, not you.** When an agentm source clone is installed the bridge delegates to agentm's shipped `queue_status_lite.py` reader; with no clone it renders a minimal local `.harness/` dashboard mirroring that format. Either way you invoke the *same* bridge and surface the *same* shape — a clean **graceful-skip, never an error**.

## Process

1. **Run the bridge.** Invoke `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/queue_status.py"` (append `--harness-dir <path>` only if the operator passed one in `$ARGUMENTS`). It is a status read — it exits 0 in normal use, and prints a clean notice (still exit 0) when there is no `_harness/` to read.
2. **Present the dashboard verbatim** (constraint 2). Show the operator the block as-is: one entry per active plan — name, `Status:`, and last `progress*.md` line.
3. **Stop.** Add nothing beyond an optional one-line framing ("N active plans"). Do not recommend, assign, or act — queue-status-lite only shows. Any follow-on — picking a plan to `/work`, a `/review`, an integration — is the operator's call.

## When there is no agentm clone

The bridge still works — it renders a minimal local `.harness/` dashboard mirroring the agentm reader's format, so the glance degrades gracefully rather than vanishing. This is the expected standalone behavior, not a failure.
