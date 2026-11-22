---
name: setup
description: "First-time project scaffold — write the repo's .harness/ tools, populate init.sh / AGENTS.md with real commands, and seed a plan only where agentm gives a path back. Run once per project."
---

You are running the **setup** phase of the developer-workflows loop. First-time initialization in a project: produce the repo's `.harness/` tools populated with **real, project-specific values — not templates**, and seed a plan where agentm says one goes. Run once per project (or after a major restructure).

> **Plans through agentm.** development-lifecycle keeps a project's plans where agentm puts them: numbered tasks in the project's vault home, or, for a repo with no vault, a repo-local `PLAN.md` in `.harness/`. `/setup` writes the repo's own tools (`init.sh`, `verify.sh`) in `.harness/` itself, and seeds a plan only at a path agentm gives back. Steps that depend on an optional layer are marked **graceful-skip** — do them if the layer is present, silently skip otherwise.

## Non-negotiable constraints

1. **Inventory before interviewing.** Read `README.md`, the package manifest (`package.json` / `go.mod` / `pyproject.toml` / `Cargo.toml` / …), `.github/workflows/`, any existing `AGENTS.md` / `CLAUDE.md`. Ask only what the inventory can't answer.
2. **Populate `init.sh` with real commands, not guesses.** If unsure, ask. A broken `init.sh` breaks every later phase silently.
3. **Verify `init.sh` boots cleanly** — run it and confirm exit 0 before finishing.
4. **Seed only what agentm names.** No plan where agentm gives no path; nothing invented to fill one.
5. **Merge, don't overwrite** an existing `AGENTS.md` / `CLAUDE.md` — they may hold project-specific content the operator wrote.
6. **No planning.** `/setup` is pure scaffolding. Planning is `/plan`.

## Process

### 1. Ask agentm where a plan goes, then write the scaffold

Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py"` bare, from the repo root, and act on its exit:

- **Exit 4** — the project keeps its plans in numbered tasks. **Seed no plan**: the first `/plan` names a task.
- **Exit 0** — a repo with no vault: agentm answered its repo-local singleton. **Seed `PLAN.md` and `progress.md` at the first two paths it printed**. The plan seed carries **no `**Status:**` line** — the plan's status lives in its tracker, which `/plan` opens.
- **Exit 1** — no agentm. **Seed no plan**, and say that development-lifecycle keeps its plans through agentm.
- **Any other exit** — surface its stderr, seed no plan, and carry on with the tools below.

Whatever the answer, write the repo's `.harness/init.sh` and `.harness/verify.sh`, creating `.harness/` if it's missing. **Skip any file that already exists — never clobber operator edits.** These are seeds; later steps fill them with real values.

**The plan seed** (exit 0 only)

```markdown
# Plan: <short title>

**Created:** <YYYY-MM-DD>
**Brief:** <1-3 sentence restatement of what we're building or changing>

## Goal

<What success looks like in 2-4 sentences. User-facing language.>

## Constraints

- <Non-obvious constraint — performance, compatibility, deadline, regulatory.>

## Out of scope

- <Explicit non-goal. At least one.>

## Steps

### 1. <Step title>
- **What:** <1-2 sentences describing the concrete change>
- **Verification:** <executable check — a test to add, a command to run, a flow to exercise>
- **Status:** [ ]

## Risks / open questions

- <What could go wrong, what we'll do if it does>

## Verification strategy

<Which deterministic gates apply — typecheck, lint, tests, build. Any project extras.>
```

**The progress seed** (exit 0 only)

```markdown
# Progress

Append-only log. Newest entries at the bottom. Format: `<YYYY-MM-DD HH:MM> /<phase> — <one-line summary>`.

---
```

**`.harness/init.sh`** (`chmod +x`)

```bash
#!/usr/bin/env bash
# init.sh — one-shot boot of the dev environment. Edit to match this project.
# Every /work session can run this to reach a known-good state.
set -euo pipefail
echo "==> install deps"
# npm install      # or pnpm / go mod download / pip install / cargo build …
echo "==> ready"
```

**`.harness/verify.sh`** (`chmod +x`, optional per-project fast check on each Write/Edit)

```bash
#!/usr/bin/env bash
# verify.sh — fast per-file check. Keep it <2s; full suites belong in the step's gates or CI.
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

### 5. Features

Nothing to seed: the plan's tracker records what is done.

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

### 8. Wiki (opt-in)

`/setup` writes no wiki pages. A project that wants a wiki runs `/wiki-init` to scaffold it and `wiki-author` to fill it.

### 9. Offer GitHub Project creation (optional)

If the repo has a `github.com` origin and `gh` is authed, **ask** whether to create a user-scoped Project for deferred-work tracking (`gh project create --owner @me --title "<repo> backlog"`), link it (`gh project link <N> --owner <owner> --repo <owner>/<repo>`), and write `.harness/project.json` (`{"github": {"owner", "number", "url", "repo"}}`). Default is **skip**. Never run `gh` without confirmation. Graceful-skip if `gh` is missing/unauthed or there's no GitHub origin.

### 10. Log and stop

On exit 0, append to the seeded `progress.md` (with no seeded plan there is no log to append to; the summary is the record):

```
<YYYY-MM-DD HH:MM> /setup — initialized harness for this project (stack: <X>, gates: <list>)
```

Then return a ≤5-bullet summary (what was seeded — the plan with its path, or why none was; stack; gates configured; `init.sh` boots clean; next `/plan <first brief>`), plus one standing, non-blocking doctrine reminder — not a hook, not a gate, just a line in the output: *"A worktree you're done with should be closed out (kept intentionally, or removed) rather than left dangling — the periodic shepherd reclaims what's provably safe to reclaim on its own schedule, but it isn't a substitute for you closing out work you know is finished."*

## Failure modes to avoid

- Filling `init.sh` with guesses — a broken boot breaks every later phase silently.
- Overwriting an existing `AGENTS.md` / `CLAUDE.md` — merge, don't replace.
- Skipping the boot verification — the first `/work` is the worst place to discover `init.sh` doesn't work.
- Starting to plan — `/setup` is pure scaffolding.
