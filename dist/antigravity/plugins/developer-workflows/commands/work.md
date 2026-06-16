---
name: work
description: Work .harness/PLAN.md's task list autonomously; safety-gate each task, stop to ask only when one fails the check or needs a clarification.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: [optional — "--name <plan-name>" to target a named plan, and/or "task N" to pick a specific task]
---

You are running the **work** phase of the developer-workflows loop. Work through `.harness/PLAN.md`'s task list **autonomously** — one task at a time, in sequence, assuming the full list. Before each task, run a safety pre-check; **stop and ask the operator only when a task fails it or an important clarification is needed.** Otherwise run to the end of the plan, gates green before each `[x]`.

**Argument (if any):** $ARGUMENTS

> **Recommended model for this phase:** Opus 4.8 (`claude-opus-4-8`) — strong model for autonomous task execution. Override with `/model` if needed.

> The session works the **whole task list autonomously** — the unit is the plan, not a single task. What keeps that safe is the **per-task safety pre-check**: before each task, decide whether it can be done safely and autonomously, and stop to ask if it can't (or if a clarification is needed). Single-threaded execution is the load-bearing constraint — never fan out parallel implementers; the autonomy boundary is the safety check, not the task count.

<!-- BEGIN recoverability-gate · canonical · byte-identical across work.md · bugfix.md · release.md (scripts/ drift test enforces) -->
## Recoverability gate (autonomy doctrine)

Invoking this phase **is** the authorization to run it to completion. The stop-gate is **recoverability, not destructiveness or blast-radius**: a recoverable action proceeds (announced); only a genuinely unrecoverable one stops for confirmation.

| Class | Examples | Behavior |
|---|---|---|
| **Recoverable** | `git push` / `-u` / `HEAD:`; create + push a tag; `gh release create` (deletable); `gh pr create` (closeable); `gh pr merge` (revertable); `gh issue create` / `close`; force-push to your **own un-shared** worker branch; delete a branch whose tip is still reachable | **Announce + proceed** — no confirmation wait. |
| **Unrecoverable** | force-push rewriting **published shared** history; sole-ref delete of unmerged work; **published-tag** overwrite; immutable publish / deploy / migration | **Stop + confirm** — pre-announce (state, don't ask), then wait. |
| **Unresolved decision** | a genuine question the design/plan never settled | **Stop + ask** — and log it as a design/plan gap (an upstream phase missed it). |

**When uncertain, treat as unrecoverable** (conservative default). Pre-announcing a recoverable-but-destructive action — state what is about to happen; do not ask permission — carries over verbatim. Any summary this phase produces is a **record of what the autonomous run did**, not a stop-and-wait barrier.

**Close-out autonomy.** Archiving a completed plan (`PLAN.md` → `PLAN.archive.YYYYMMDD-<slug>.md`) and the rest of close-out bookkeeping (append `progress.md`, move the ROADMAP item to Completed/SHIPPED, update staging notes) is **recoverable → autonomous** — never stop to ask approval to archive or to do close-out bookkeeping.

**Carve-outs — unchanged by this doctrine.** Worker-tree initiation requires operator authority — either an explicit `/spawn-worker` command or a durable `isolation.mode: worktree-per-plan` config opt-in; silent authority-free auto-spawn stays forbidden; `/integrate-worker` stays operator-initiated; the PII pre-push hook + `pii-scrubber` invocation stay mandatory; the no-`Co-Authored-By` commit rule is untouched.
<!-- END recoverability-gate -->

## Non-negotiable constraints

1. **Assume the full task list; safety-gate each task.** Work the plan's tasks autonomously, in sequence — no per-task approval. Before each task, run a safety pre-check; **stop and ask only when a task fails it (genuinely-unrecoverable / ambiguous / scope-drifting / unverifiable — per the recoverability gate above) or needs a clarification** — otherwise continue to the end of the plan. Single-threaded always; never fan out parallel implementers.
2. **Gates must be green before the task is marked `[x]`.** No "I'll fix this next session" on failed gates.
3. **Never edit or delete a failing test to make it pass.** If a test is wrong, surface it and stop.
4. **Feed full error output back** on gate failures — do not summarize. The exact error is the signal.
5. **Cap iterations at 5 per gate.** If not green after 5, stop and report.
6. **Do not silently expand task scope.** If it turns out bigger than planned, stop and ask.
7. **Do not touch `wiki/` during implementation.** Documentation updates are phase-boundary-only.
8. **After gates are green (before committing), dispatch the `documenter` sub-agent** with the task spec + the diff (via the `wiki-maintenance` capability probe — exit 0 dispatch, exit 1 skip). It flips matching `pending → implemented` pages and adds operational pages if the task introduced one. Resolve `OPEN QUESTIONS` before committing.
9. **End by updating the resolved `PLAN.md` (mark `[x]`), the resolved `progress.md` (append line), and committing.**
10. **Sync the task to the GitHub Project board** (optional, graceful-skip). When `github-projects` is installed (capability probe) + `.harness/project.json` present + `gh` authed, emit a **Task progress** update for the just-completed task via the github-projects plugin's `project_sync.py post --type task-progress`; capture any out-of-task-scope findings (adjacent bug, refactor, stale doc elsewhere — not follow-ups to the current task) into `board-items.json` as board-backed `Backlog-item`s (**never** raw `gh project item-create` — an unbacked board issue is an orphan the `vault==board` gate flags as drift). Deterministic + idempotent → announce + proceed. Silent-skip (zero behavior change) if the plugin, `project.json`, or `gh` is absent. Then stop.
11. **Do not create tags.** Tag creation is reserved for `/release` — the sole tag writer that tags `main` HEAD after CI-green. Creating a tag during `/work` would point to a branch tip, not a main commit, violating the tag-reachability guarantee and the concurrent-release serialization model.

## Process

### 1. Read state

**Resolve the active plan pair first.** A `/work` invocation may target a named plan with **`--name <slug>`** anywhere in `$ARGUMENTS`; the `task N` selector keeps its meaning, so `/work --name <slug> task N` carries both. Absent `--name`, the singleton is used. Resolve the on-disk pair by **consuming** the agentm reader — never re-deriving the paths here (pass the `--name` value as `<slug>`; omit it for the singleton):

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" [<slug>]
```

It emits one tab-separated line, `<plan_path>\t<progress_path>` — the **resolved pair** every later step reads and writes. Bare (no `--name`) resolves to the singleton `.harness/PLAN.md` / `.harness/progress.md`, **byte-identical** to the historic behavior. A **non-zero exit is a hard stop** — surface its stderr and stop; never fall back to the singleton on a dangling binding (that would silently bind the worker to the wrong plan). If `CLAUDE_PLUGIN_ROOT` is unset, treat the pair as the singleton.

Then read the **resolved `PLAN.md`** (find the first unchecked `[ ]` task, or honor the `task N` selector); the **resolved `progress.md`** (was a prior session interrupted — resume or restart?); `AGENTS.md` / `CLAUDE.md` (commit style, test runner, conventions).

**Duplicate guard (run before anything else).** After reading PLAN.md, check two conditions and stop on either:

1. **Status: done** — if the plan's `**Status:**` line is `done`, stop immediately: *"DUPLICATE GUARD: plan is already `Status: done` — it was completed by another session. Refuse to re-run. If the previous output is wrong, reset the Status field manually and re-invoke."*
2. **Live-worker branch (named plans only)** — if a plan slug is available (from `--name` or the worktree-local `.harness/active-plan` marker), run `git ls-remote --heads origin "worker/<slug>"`. If it returns a non-empty line, stop: *"DUPLICATE GUARD: branch `worker/<slug>` already exists on origin — another worker session is likely active on this plan. If that session was interrupted, run `git push origin --delete worker/<slug>` then re-invoke."*

Both checks are read-only. A clean plan (not done, no live branch) passes both silently.

### 1.5. Check isolation mode + auto-spawn (first run only, skip on resume)

**Skip this step if resuming a plan already in progress** (first task is `[x]`).

Run the isolation check — **operator authority required**: this step fires only when the operator enabled `isolation.mode: worktree-per-plan` in `.harness/project.json` (a durable config opt-in), or passed `--isolate` explicitly. It never runs silently without that authority.

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/isolation_config.py" check [--no-isolate if $ARGUMENTS contains --no-isolate] [--project-root <root>]
```

- **Exit 0** (should auto-spawn): run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spawn_worker.py" <slug>` (the plan's slug). On success the helper prints the new worktree path; **announce the spawn** ("Auto-spawning worktree at `<path>` — operator config-gated"), then proceed from inside the new worktree for all subsequent steps.
- **Exit 1** (no auto-spawn): proceed directly — no worktree needed (mode is `direct`, no config, or single-owner guard fired because we're already inside a worktree).
- Any non-zero from `spawn_worker.py` → surface stderr and stop. Do not retry.

**Note:** `--no-isolate` in `$ARGUMENTS` is the command-arg override that wins over any config setting.

### 2. Safety pre-check (before each task)

The session assumes the **full task list** — it does not ask permission per task. Before starting each task, run a go/no-go safety pre-check: **proceed autonomously if the task is safe; stop and ask only when it isn't, or when an important clarification is needed.** Triggers to stop — the task performs a genuinely **unrecoverable** action (per the recoverability gate above: recoverable actions proceed announced; only force-push rewriting published shared history, sole-ref delete of unmerged work, published-tag overwrite, or an immutable deploy/migration stops); needs a decision that isn't locked (an **unresolved decision** — stop, ask, and log it as a design/plan gap); turns out bigger or different than the plan said (scope drift); has a verification that can't be made executable or an unmet prerequisite; or surfaces a failing test that invalidates its premise. State the trigger plainly and wait — even mid-plan. Otherwise proceed to step 3.

## Common Rationalizations

| Excuse | Why it's wrong |
|---|---|
| "This task is small enough to skip the pre-check" | The pre-check exists precisely for tasks you're confident about — confidence is when blind spots hide. |
| "I'll run verification after the whole plan is done" | Verification gates are per-task; batch verification misses regressions introduced mid-plan. |
| "The test is wrong, not the code" | First reproduce the test's intent independently; delete only if the intent is wrong, never because it makes the code fail. |

### 3. Gather context (optional)

If the task touches unfamiliar code, dispatch the `explorer` sub-agent for read-only fan-out ("Where is X handled? What tests exist for Y? Return file:line references."). Fan out only for multiple independent questions — for one question, just read.

### 4. Implement

- Write code that satisfies the task's **What**. Write the tests that satisfy its **Verification** in the **same session** — tests-after is an anti-pattern; verification lands with the implementation.
- Follow project conventions (formatters, naming, layout). If the task implies a deviation, flag it and ask.
- **Do not touch `wiki/`** — documentation is the step-8 phase boundary, not inline.
- If mid-implementation the task turns out bigger than planned, **stop**: *"Task N is bigger than planned because [reason]. Options: (a) finish narrow, (b) expand + re-plan, (c) split. Your call."* Then wait.

### 5. Run deterministic gates

Run in order, short-circuit on failure: **typecheck → lint → tests → build** (build only if the task affects build output). Commands come from `.harness/init.sh` / package scripts / Makefile. If a gate isn't configured, note it and skip — don't invent one.

**Evidence-tracking + operator-control hooks (graceful-skip).** If a safety/review plugin (e.g. crickets `developer-safety` / `code-review`) is installed, its hooks engage automatically — a default-FAIL evidence contract before a `[ ]`→`[x]` flip, plus `kill-switch` / `steer` / `commit-on-stop`. Absent those plugins, `/work` runs exactly as written here with no behavior change.

### 6. Iterate on failures

Feed the **full error output** into the next pass (don't summarize). Cap at **5 iterations** per gate — loops of 20+ mean a misunderstanding, not a fixable bug. If a test is itself wrong, **stop** — do not edit or delete it to go green; surface the defect and ask.

### 7. Update state

Once all gates are green: edit the **resolved `PLAN.md`** to mark the task `[x]` (`planning → in-progress` on the first task; `→ done` if it was the last). Do **not** set `features.json` `passes: true` — that's `/review`'s job. Append to the **resolved `progress.md`** (the scoped `progress-<slug>.md` when a named plan is active, never the singleton):

```
<YYYY-MM-DD HH:MM> /work — completed task N: "<title>" (<filesChanged> files, <testsAdded> tests)
```

### 8. Update the wiki (post-gates, graceful-skip)

Probe with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/capability_probe.py" wiki-maintenance`. On **exit 0** dispatch its `documenter` with the task's title + What + Verification and the diff — it flips `pending → implemented` **only if the diff proves it** (speculative flips are worse than missed ones), fills `## Implementation` with real `file:line` refs, and adds how-to pages for new operational concerns. Resolve `OPEN QUESTIONS` before committing; `NO CHANGES` is fine. On **exit 1** (absent, or no `CLAUDE_PLUGIN_ROOT`) skip silently. Not invoked during step 4.

### 9. Commit

One task, one commit, referencing the task. Follow project trailer conventions (check recent `git log`). **Do not add a `Co-Authored-By:` trailer** — the user is the sole author of intent, the agent is the tool. Don't use `--no-verify`; let pre-commit hooks run.

### 10. Sync the task to the GitHub Project board (graceful-skip)

Probe with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/capability_probe.py" github-projects`. On **exit 1** (plugin absent, or no `CLAUDE_PLUGIN_ROOT`) skip silently — zero behavior change. On **exit 0** with `.harness/project.json` present and `gh` authed, after the commit:

- **Task progress** — emit the just-completed task's progress line to its board item: `python3 "${CLAUDE_PLUGIN_ROOT}/../github-projects/scripts/project_sync.py" post --config <project.json> --type task-progress --id <task-id> --commit <SHA> --summary "<one human sentence>"`. The `--type task-progress` shortcut folds the `②Progress` line into `board-items.json` and re-renders; the renderer owns the date/SHA→link, you supply only the sentence. Per **DC-1** Tasks materialize only under the active plan.
- **Out-of-scope findings** — anything surfaced this session that's *not* a follow-up to the current task (an adjacent bug, a refactor, missing coverage elsewhere, a stale doc) → record in `board-items.json` as a `Backlog-item` so the next sync materializes it; **never** raw `gh project item-create` (an unbacked board issue is an orphan the `vault==board` gate flags as drift).

The write path is deterministic, one-way, idempotent-by-stable-id → recoverable; **announce + proceed** (preview with `--dry-run`). Silent-skip if `project.json` or `gh` is absent.

### 11. Loop or stop

After the commit, **loop back to step 2** for the next unchecked task — same session, same context — running the plan autonomously. Stop only when the plan is done (no `[ ]` left) or a safety pre-check fires / a clarification is needed (stop mid-plan and ask). Run an inline `/review` first when a just-finished task was high-risk. Return a ≤5-bullet summary: tasks completed this session; why it stopped (plan done / safety stop); files changed; gates (green per task, or N iterations + why); next.

When to `/review` rather than straight to the next `/work`: the task touched security/auth/payments/persistence; it was the last task in the plan; the plan's Risks flagged this area; or the change feels brittle. Skip review for routine changes (new tests, pure refactors, docs, scaffolding) — the next `/work` runs gates anyway.

### 12. Finalize the unit (when plan is done, isolation mode only)

**Only when:** the last task is now `[x]` AND step 1.5 auto-spawned a worktree (i.e. isolation mode is active). Skip entirely for direct mode (the tasks already committed on main).

Run the finalization helper — **recoverable, announce + proceed**:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/finalize_unit.py" <slug> [--project-root <root>] [--title "<plan title>"] [--no-pr if $ARGUMENTS contains --no-pr]
```

The helper reads `isolation.integration` from `.harness/project.json` and acts accordingly:
- **`pull-request` (default):** PII guard → push `worker/<slug>` → `gh pr create`. **`gh pr create` is recoverable** (the PR can be closed/reverted) → announce + proceed.
- **`direct-push`:** PII guard → push on current branch (no PR).
- **`gh` unavailable / unauthenticated / no remote:** fall back to direct push + announce the downgrade. A completed unit of work is **never hard-stopped** by a missing `gh` — the push always goes through.

Announce what's about to happen before running. A non-zero exit from the helper is a hard stop — surface the full error output.

## Failure modes to avoid

- **Pushing past a failed safety pre-check.** Being in an approved run isn't a license — if a task performs a genuinely *unrecoverable* action, is ambiguous, is scope-drifting, or needs a clarification, stop and ask, even mid-plan. (A recoverable-but-destructive action is not a stop trigger — announce it and proceed.)
- **Editing tests to make them pass.** Banned — if a test is wrong, say so and stop.
- **Skipping failed gates** ("I'll fix it next session"). Green before `[x]`.
- **Silently expanding scope.** Surface it; don't quietly do more than the plan says.
- **Summarizing errors** instead of passing them through on failure.
- **Committing without running gates.** Gates first, commit second.
- **Forgetting `PLAN.md` + `progress.md`.** The next session is blind without them.
