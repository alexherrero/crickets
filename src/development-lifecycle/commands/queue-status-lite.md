---
name: queue-status-lite
description: Read-only coordinator's glance — list every active task of a project with its tracker status and most-recent progress line. Surfaces, never mutates.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.2.0
argument-hint: (none — the project is the one the cwd is bound to)
---

You are running **queue-status-lite** — the coordinator's read-only glance at the plan queue. It lists every active task of the project the cwd is bound to — for each, its name, its status from its tracker, and the most-recent line of its progress log — and prints that dashboard. In a repo with no vault, the rows are its repo-local plans, the ones agentm keeps in `.harness/`. It is **not a gate** and it **mutates no state**: it reads and prints, nothing else.

**Arguments:** $ARGUMENTS — none. The project is the one the cwd is bound to; agentm resolves it.

> **Read-only by contract** (the V5-10 design call). There is no claim, no lease, no arbitration — the human is the arbiter of who works which plan. This command exists so a coordinator can *see* the queue before deciding; it never decides, never assigns, never records anything.

## Non-negotiable constraints

1. **Read-only — mutates no state.** This command never flips a status, never records progress, never binds or assigns a plan, never writes any file. If you find yourself about to write, you are out of scope — stop. It is the glance, not the gate.
2. **Surface the bridge's output verbatim.** Run the bridge and present its dashboard to the operator **verbatim** — do not parse, re-rank, summarize, or editorialize the rows. agentm's reader owns the format; your job is to show it.
3. **agentm owns the list.** The bridge runs agentm's `queue_status_lite.py`, which knows where a project keeps its plans and reads each one's tracker. crickets enumerates nothing itself. With no agentm, the bridge prints one line saying so and exits 0 — a clean **graceful-skip, never an error**.

## Process

1. **Run the bridge.** Invoke `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/queue_status.py"` from the project's repo. It is a status read and exits 0 in normal use.
2. **Present the dashboard verbatim** (constraint 2). Show the operator the block as-is: one entry per active task — name, status, and last progress line.
3. **Stop.** Add nothing beyond an optional one-line framing ("N active tasks"). Do not recommend, assign, or act — queue-status-lite only shows. Any follow-on — picking a task to `/work`, a `/review`, a release — is the operator's call.

## When there is no agentm

The bridge prints `No plan list: …` and exits 0. development-lifecycle keeps its plans through agentm, so with no agentm there is no queue to show; this is expected, not a failure.
