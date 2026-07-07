---
name: planner-maintain
description: Run one Planner (TPM) depth-maintenance + drift-correction cycle — materialize a collapsed Feature->Plan or Plan->Task gap where it can be inferred safely, correct update drift via the existing project_sync.py post path, and surface orphan drift + un-inferrable depth gaps for operator judgment. Never auto-closes an orphan.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

Run **one** Planner (TPM) persona maintenance cycle for the current repo's project board.

This command is the explicit-invocation entry point for the Planner's depth-maintainer (`depth_maintain.py`) and drift-corrector (`drift_correct.py`), composed end to end via `planner_maintain.py`. It fills in the depth floor where a signal is unambiguous, corrects `update` drift the same way a manual `project_sync.py post` already would, and surfaces anything it can't safely resolve on its own — never silently.

## Usage

```bash
# One cycle, using .harness/project.json:
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/planner_maintain.py" --config .harness/project.json

# Preview without writing or posting anything:
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/planner_maintain.py" --config .harness/project.json --dry-run

# Explicit invocation (the Planner persona's `triggers:` surface):
/planner-maintain
```

## What it does

1. **Depth-maintenance** (`depth_maintain.py`) — scans `board-items.json` for a Feature/Sub-feature with zero materialized Plan children, or a materialized Plan with zero Task children, while real underlying work exists (an active `PLAN-<slug>.md` naming the Feature, or that Plan's own task checklist). Materializes the missing level when the match is explicit (slug-equals-feature-id, or a stated `fields.plan_slug`) — never via fuzzy title guessing. Flags anything it can't confidently attribute for operator judgment instead.
2. **Drift-correction** (`drift_correct.py`) — re-classifies `update`/`orphan` drift independently of `check_project_sync.py` (that gate stays the unmodified oracle) and acts: `update` drift gets the same idempotent `project_sync.py post` body-sync a manual re-run would do; `orphan` drift is **never auto-closed or edited** — surfaced as a clear flag, since an orphan might be a legitimately hand-created issue.

Both passes run over the same in-memory graph — a Plan/Task the depth pass just materialized is persisted before the drift pass runs, so it's visible to that pass's own disk read.

## What it does not do

- Never invents a Plan's `goal`/`done_when` or guesses a Feature-to-plan-file match by title similarity.
- Never auto-closes, auto-edits, or auto-links an orphan board issue.
- Never modifies `check_project_sync.py`'s or `report_drift.py`'s own behavior — both remain independently callable, unmodified, report-only paths.
- Does not build an automated net-new-Feature-creation entrypoint (a separate, still-open gap named in the design doc) — it only fills in a missing *intermediate* level under an already-materialized Feature/Plan.

## Workflow-step binding

`/work` (step 10) and `/release` (step 7/8) already call `project_sync.py post` at a graceful-skip board-sync gate after a task/release lands. Both now also invoke this cycle at the same gate — same availability probe, same silent-skip when the plugin, `project.json`, or `gh` is absent, so a repo that never opted into board-sync sees zero behavior change.

## Graceful-skip

Prints a message and exits 0 when there's no `project.json` at the resolved path (not a board-synced repo) or `gh` isn't on `PATH` — matching every other `github-projects` entrypoint. Exits 1 (informational, not a hard failure) when something was flagged for operator judgment; exits 2 only on a genuine operational error (a `gh` call failing outright).
