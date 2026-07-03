---
name: report-board-drift
description: Run one report-only board-drift cycle — detect vault==board drift and post a single summary comment on the Version issue (or log it if no Version issue resolves). The thin slash entry for driving the cycle on a loop (/loop or cron). Never corrects drift; correction stays operator-confirmed until the Planner (TPM) persona ships.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

Run **one** board-drift report cycle for the current repo's project board.

This command is the thin scheduling entrypoint — the thing you put in `/loop` or a cron line. It runs `check_project_sync`'s drift detector **unmodified** via `scripts/report_drift.py`, then posts the findings as a single summary comment on the vault's Version issue (or logs the report if no Version issue is materialized yet). One invocation = one idempotent cycle: a hidden marker keyed to the exact drift content means a re-run against unchanged drift is a no-op, not a duplicate comment.

## Usage

```bash
# One cycle, using .harness/project.json:
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/report_drift.py" --config .harness/project.json

# Preview without posting:
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/report_drift.py" --config .harness/project.json --dry-run

# Drive it on a loop:
/loop /report-board-drift

# Headless cron (Claude-first scheduling, same pattern as /wiki-watch):
#   */30 * * * *  cd /path/to/repo && claude -p "/report-board-drift"
```

## What it does — and does not do

Report-only. It **never creates, updates, or deletes a board item** — no `item-edit`, no `issue-edit`, no `item-add`; the only write it ever performs is the one summary comment, and only when drift is found and not already reported. Correction stays operator-confirmed until the Planner (TPM) persona's depth-maintainer/drift-corrector ships (AG Wave D) — this cycle is that persona's future eyes, not its hands.

## Graceful-skip

Prints a message and exits 0 when there's no `project.json` at the resolved path (not a board-synced repo) or `gh` isn't on `PATH` — zero behavior change, matching every other `github-projects` entrypoint.
