---
name: setup
description: First-time project scaffold — write the .harness/ files and populate init.sh / AGENTS.md with real commands. Run once per project.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

You are running the **setup** phase of the developer-workflows loop. First-time initialization in a project: produce the `.harness/` state artifacts populated with **real, project-specific values — not templates**. Run once per project (or after a major restructure).

> **Standalone + storage-agnostic.** This plugin carries the phase workflow and writes plain `.harness/<file>` state in the repo. If a memory/storage layer is hosting it (e.g. agentm's MemoryVault), that layer transparently redirects state and adds recall; absent one, everything below works against `.harness/`. Steps that depend on an optional layer are marked **graceful-skip** — do them if the layer is present, silently skip otherwise.

## Non-negotiable constraints

1. **Inventory before interviewing.** Read `README.md`, the package manifest (`package.json` / `go.mod` / `pyproject.toml` / `Cargo.toml` / …), `.github/workflows/`, any existing `AGENTS.md` / `CLAUDE.md`. Ask only what the inventory can't answer.
2. **Populate `init.sh` with real commands, not guesses.** If unsure, ask. A broken `init.sh` breaks every later phase silently.
3. **Verify `init.sh` boots cleanly** — run it and confirm exit 0 before finishing.
4. **Do not invent features** for `features.json`. Empty is honest; fabricated entries are noise.
5. **Merge, don't overwrite** an existing `AGENTS.md` / `CLAUDE.md` — they may hold project-specific content the operator wrote.
6. **No planning.** `/setup` is pure scaffolding. Planning is `/plan`.

## Process

### 1. Write the `.harness/` scaffold

If `.harness/` doesn't exist, create it and write the files below. **Skip any file that already exists — never clobber operator edits.** These are seeds; later steps fill them with real values.

**`.harness/PLAN.md`**

```markdown
# Plan: <short title>

**Status:** planning
**Created:** <YYYY-MM-DD>
**Brief:** <1-3 sentence restatement of what we're building or changing>

## Goal

<What success looks like in 2-4 sentences. User-facing language.>

## Constraints

- <Non-obvious constraint — performance, compatibility, deadline, regulatory.>

## Out of scope

- <Explicit non-goal. At least one.>

## Tasks

### 1. <Task title>
- **What:** <1-2 sentences describing the concrete change>
- **Verification:** <executable check — a test to add, a command to run, a flow to exercise>
- **Status:** [ ]

## Risks / open questions

- <What could go wrong, what we'll do if it does>

## Verification strategy

<Which deterministic gates apply — typecheck, lint, tests, build. Any project extras.>
```

**`.harness/progress.md`**

```markdown
# Progress

Append-only log. Newest entries at the bottom. Format: `<YYYY-MM-DD HH:MM> /<phase> — <one-line summary>`.

---
```

**`.harness/features.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "features": []
}
```

**`.harness/init.sh`** (`chmod +x`)

```bash
#!/usr/bin/env bash
# init.sh — one-shot boot of the dev environment. Edit to match this project.
# Every /work and /review session can run this to reach a known-good state.
set -euo pipefail
echo "==> install deps"
# npm install      # or pnpm / go mod download / pip install / cargo build …
echo "==> ready"
```

**`.harness/verify.sh`** (`chmod +x`, optional per-project fast check on each Write/Edit)

```bash
#!/usr/bin/env bash
# verify.sh — fast per-file check. Keep it <2s; full suites belong in /review or CI.
# Exit 0 silent on success, non-zero on failure. $1 is the file just written.
set -uo pipefail
FILE="${1:-}"; [[ -z "$FILE" || ! -f "$FILE" ]] && exit 0
case "$FILE" in
  # *.ts|*.tsx) npx tsc --noEmit "$FILE" 2>&1 || exit 1 ;;
  # *.py)       ruff check "$FILE" 2>&1 || exit 1 ;;
  # *.go)       go vet "./$(dirname "$FILE")/..." 2>&1 || exit 1 ;;
esac
exit 0
```

### 2. Inventory what's there

Read `README.md` (what is this?), the package manifest (run/test/build commands), `.github/workflows/` (what "gates green" means here), and any existing `AGENTS.md` / `CLAUDE.md` / `.cursorrules` (conventions already documented).

### 3. Interview, briefly

Confirm or fill in what the inventory didn't settle — **batched, default to not asking** if already answered:
- What does this project do? (one sentence for `AGENTS.md`)
- How do you boot the dev env? (the commands for `init.sh`)
- How do you run tests? (full suite + single-file if they differ)
- How do you typecheck / lint? (skip if N/A)
- Any commands the harness should avoid? (destructive migrations, deploys)
- Commit convention? (conventional commits / free-form / specific trailer)

### 4. Populate `init.sh` with real commands

Replace the placeholders with what this project actually runs. It should run top-to-bottom and leave the repo in a state where `/work` can proceed. Keep heavy/destructive commands commented with a note.

### 5. Seed `features.json` (optional)

If a known feature list already exists (PRD, backlog, README features section), seed entries with `passes: false`. Otherwise leave it empty — `/plan` adds features as they get specified. **Do not invent features.**

### 6. Make `AGENTS.md` right for this project

If it exists and mentions the workflow, good. If it exists but doesn't, merge a pointer section. Add a `## This project` block:

```markdown
## This project

<One-sentence description.>

**Stack:** <languages, frameworks, DB>
**Run:** `bash .harness/init.sh`
**Test:** <command>   **Typecheck:** <command>   **Lint:** <command>   **Build:** <command, if any>

**Conventions:**
- <commit convention>
- <project-specific style rules later phases should respect>
```

This is the block later phases read to know how to operate.

### 7. Verify the harness boots

Run `bash .harness/init.sh`. Confirm it exits 0. If not, fix it now — every later phase depends on it.

### 8. Populate the wiki scaffold (graceful-skip)

Check availability: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agentm_bridge.py" capability wiki-maintenance`. On **exit 0** (the crickets `wiki-maintenance` plugin — which ships the `documenter` — is installed + enabled) dispatch its `documenter` to fill any `wiki/` seed pages (Getting-Started, Runbook, Product-Intent, Overview, Home, _Sidebar) from the inventory + interview, and resolve any `OPEN QUESTIONS`. On **exit 1** (unavailable, or graceful-skip when agentm is absent or `CLAUDE_PLUGIN_ROOT` unset) skip silently. **Routed dispatch (separate graceful-skip):** additionally check `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agentm_bridge.py" capability token-audit`; on exit 0, resolve `classify_work_type('documenter')` + `agent_tool_alias(...)` and pass as the dispatch's `model` param; on exit 1, no `model` override — unchanged. **Mandatory fan-out announcement (unconditional):** print `fanout_announcement.py`'s `render_announcement()` line before dispatching regardless of the probe's result; an `INHERITED` source at a frontier-tier (T3/T4) session triggers `needs_inheritance_pause()` — stop for confirmation, never proceed silently. At `agent_count >= 4`, `announce_dispatch()` also runs the fleet cost gate (`token-audit`'s `fanout_cost_gate.py`, capability-gated) — a blocked result raises the same `pause_required` flag, stop for confirmation the same way.

### 9. Offer GitHub Project creation (optional)

If the repo has a `github.com` origin and `gh` is authed, **ask** whether to create a user-scoped Project for deferred-work tracking (`gh project create --owner @me --title "<repo> backlog"`), link it (`gh project link <N> --owner <owner> --repo <owner>/<repo>`), and write `.harness/project.json` (`{"github": {"owner", "number", "url", "repo"}}`). Default is **skip**. Never run `gh` without confirmation. Graceful-skip if `gh` is missing/unauthed or there's no GitHub origin.

### 10. Log and stop

Append to `.harness/progress.md`:

```
<YYYY-MM-DD HH:MM> /setup — initialized harness for this project (stack: <X>, gates: <list>)
```

Then return a ≤5-bullet summary (harness at `.harness/`; stack; gates configured; `init.sh` boots clean; next `/plan <first brief>`), plus one standing, non-blocking doctrine reminder — not a hook, not a gate, just a line in the output: *"A worktree you're done with should be closed out (kept intentionally, or removed) rather than left dangling — the periodic shepherd reclaims what's provably safe to reclaim on its own schedule, but it isn't a substitute for you closing out work you know is finished."*

## Failure modes to avoid

- Filling `init.sh` with guesses — a broken boot breaks every later phase silently.
- Inventing features — empty `features.json` is fine; fabricated entries are worse than none.
- Overwriting an existing `AGENTS.md` / `CLAUDE.md` — merge, don't replace.
- Skipping the boot verification — the first `/work` is the worst place to discover `init.sh` doesn't work.
- Starting to plan — `/setup` is pure scaffolding.
