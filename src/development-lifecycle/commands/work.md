---
name: work
description: Work .harness/PLAN.md's task list autonomously; safety-gate each task, stop to ask only when one fails the check or needs a clarification.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.1
install_scope: project
argument-hint: [optional — "--name <plan-name>" to target a named plan, and/or "task N" to pick a specific task]
opinions: [done]
---

You are running the **work** phase of the developer-workflows loop. Work through `.harness/PLAN.md`'s task list **autonomously** — one task at a time, in sequence, assuming the full list. Before each task, run a safety pre-check; **stop and ask the operator only when a task fails it or an important clarification is needed.** Otherwise run to the end of the plan, gates green before each `[x]`.

**Argument (if any):** $ARGUMENTS

> **Recommended model for this phase:** `opusplan` — Opus 4.8 plans, Sonnet 5 executes the long autonomous stretch. Override with `/model` if needed.

> **Workflow-step persona (advisory, graceful-skip).** `/work` wears the **Engineer** persona for this phase — the phase spec is the source of truth for this adoption (`agentm-persona-activation.md`'s workflow-step path; a persona's `triggers:` field feeds only sub-agent routing, never this lookup). Check: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_workflow_persona.py" work-phase`. **Exit 0** → read the printed persona's manifest (`<agentm-root>/personas/<name>.md`) and hold its stance + `opinions:` for this session. **Exit 1** (agentm absent, or no persona declared for this step) → proceed with this phase's own prose, unchanged — a clean graceful-skip. An operator who already put on a different persona this session keeps it — pass `--explicit <that-name>` so the resolved answer reflects the override (explicit invocation always wins over the workflow-step default).

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

**Carve-outs — unchanged by this doctrine.** Worktree initiation requires operator authority — a durable `isolation.mode: worktree-per-plan` config opt-in (this command's own auto-spawn) or an explicit operator instruction to use a worktree; silent authority-free auto-spawn stays forbidden; integration lands via the plan's own PR + required-check gate, armed for auto-merge (`/spawn-worker` and `/integrate-worker` are retired — the auto-spawn-and-PR flow now covers both jobs end-to-end); the PII pre-push hook + `pii-scrubber` invocation stay mandatory; the no-`Co-Authored-By` commit rule is untouched.
<!-- END recoverability-gate -->

## Non-negotiable constraints

1. **Assume the full task list; safety-gate each task.** Work the plan's tasks autonomously, in sequence — no per-task approval. Before each task, run a safety pre-check; **stop and ask only when a task fails it (genuinely-unrecoverable / ambiguous / scope-drifting / unverifiable — per the recoverability gate above) or needs a clarification** — otherwise continue to the end of the plan. Single-threaded always; never fan out parallel implementers.
2. **Gates must be green before the task is marked `[x]`.** No "I'll fix this next session" on failed gates.
3. **Never edit or delete a failing test to make it pass.** If a test is wrong, surface it and stop.
4. **Feed full error output back** on gate failures — do not summarize. The exact error is the signal.
5. **The escalation tripwire fires at 3 consecutive failures on the same gate for the same task** (`escalation_tripwire.py`, capability-gated on token-audit — see step 6). This supersedes the old flat 5-iteration cap: no session reaches a 4th attempt on an unresolved gate. If token-audit is absent, the tripwire still fires (degraded: loud stop, no handoff pack) — the cap is never silently longer just because the capability is missing.
6. **Do not silently expand task scope.** If it turns out bigger than planned, stop and ask.
7. **Do not touch `wiki/` during implementation.** Documentation updates are phase-boundary-only.
8. **After gates are green (before committing), dispatch the `documenter` sub-agent** with the task spec + the diff (via the `wiki-maintenance` capability probe — exit 0 dispatch, exit 1 skip). It flips matching `pending → implemented` pages and adds operational pages if the task introduced one. Resolve `OPEN QUESTIONS` before committing.
9. **End by updating the resolved `PLAN.md` (mark `[x]`), the resolved `progress.md` (append line), and committing.**
10. **Sync the task to the GitHub Project board** (optional, graceful-skip). When `github-projects` is installed (capability probe) + `.harness/project.json` present + `gh` authed, emit a **Task progress** update for the just-completed task via the github-projects plugin's `project_sync.py post --type task-progress`; capture any out-of-task-scope findings (adjacent bug, refactor, stale doc elsewhere — not follow-ups to the current task) into `board-items.json` as board-backed `Backlog-item`s (**never** raw `gh project item-create` — an unbacked board issue is an orphan the `vault==board` gate flags as drift). Deterministic + idempotent → announce + proceed. Silent-skip (zero behavior change) if the plugin, `project.json`, or `gh` is absent. Then stop.
11. **Design-divergence is a NOTE, never a halt (Hook 4, design-doc §6).** If the implementation appears to diverge from the plan's `parent_design_doc:` governing design, record it as a `NOTE:` line in `progress.md` — a surfaced observation, **not** a safety-stop trigger and **not** a gate. Conformance is an un-mechanizable judgment; its adjudication is `/review`'s fresh-context design-conformance dimension (Hook 1), never the worker's self-interested call (routing it into the autonomy gate would over- or under-stop).
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

1. **Status: done** — if the plan's `**Status:**` line is `done`, check `progress.md` for a final task completion line (e.g. `completed task N`). If found, stop immediately: *"DUPLICATE GUARD: plan is `Status: done` and close-out is complete — it was completed by another session. If the previous output is wrong, reset the Status field manually and re-invoke."* If no task completion line exists in `progress.md`, treat it as an interrupted close-out: proceed with a warning *"Plan is Status: done but close-out appears incomplete — resuming close-out steps only (no re-implementation)."* and jump directly to step 7 (update PLAN.md / progress.md) then steps 9–12.
2. **Live-worker branch (named plans only)** — if a plan slug is available (from `--name` or the worktree-local `.harness/active-plan` marker), run `git ls-remote --heads origin "worker/<slug>"`. If it returns a non-empty line, stop: *"DUPLICATE GUARD: branch `worker/<slug>` already exists on origin — another worker session is likely active on this plan. If that session was interrupted, run `git push origin --delete worker/<slug>` then re-invoke."*

Both checks are read-only. A clean plan (not done, no live branch) passes both silently.

### 1.5. Check isolation mode + auto-spawn (first run only, skip on resume)

**Skip this step if resuming a plan already in progress** (first task is `[x]`).

Run the isolation check — **operator authority required**: this step fires only when the operator enabled `isolation.mode: worktree-per-plan` in `.harness/project.json` (a durable config opt-in), or passed `--isolate` explicitly. It never runs silently without that authority.

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/isolation_config.py" check [--no-isolate if $ARGUMENTS contains --no-isolate] [--project-root <root>]
```

- **Exit 0** (should auto-spawn): call the **host's own worktree primitive** — Claude Code: `EnterWorktree` with `name` set to the plan's slug; Antigravity: New-Worktree-Mode / `invoke_subagent` (best-effort, per Antigravity-Limitations). Do not invent a worktree path or branch name — read back whatever the primitive actually returns (Claude Code: `.claude/worktrees/<name>` on branch `worktree-<name>`, not the retired `<repo>.worktrees/<slug>` / `worker/<slug>` convention). Then bind it: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/worktree_marker.py" write <worktree-path> <slug> <plan-path> --project-root <original-root>` (the `<plan-path>` is the resolved path from step 1 — never re-resolved here).
  - **Exit 0**: **announce the spawn** ("Auto-spawning worktree at `<path>` — operator config-gated"), then proceed from inside the new worktree for all subsequent steps.
  - **Exit 3** (LC-6 already-shipped no-op): the plan shipped before this session got here — exit the worktree (`ExitWorktree` `remove`, or the Antigravity equivalent; nothing was written to it) and report the `already shipped` message. Stop; do not proceed to step 2.
  - **Exit 2**: surface stderr, exit/remove the now-orphaned worktree, and stop. Do not retry.
- **Exit 1** (no auto-spawn): proceed directly — no worktree needed (mode is `direct`, no config, or single-owner guard fired because we're already inside a worktree).

**Note:** `--no-isolate` in `$ARGUMENTS` is the command-arg override that wins over any config setting.

**`worktree-per-task` mode does NOT trigger a per-plan auto-spawn here.** When `isolation.mode` is `worktree-per-task`, this check returns exit 1 (no plan-level worktree). Per-task worktrees are spawned mid-loop in step 2.5, one per operator-declared-isolated task.

### 2. Safety pre-check (before each task)

The session assumes the **full task list** — it does not ask permission per task. Before starting each task, run a go/no-go safety pre-check: **proceed autonomously if the task is safe; stop and ask only when it isn't, or when an important clarification is needed.** Triggers to stop — the task performs a genuinely **unrecoverable** action (per the recoverability gate above: recoverable actions proceed announced; only force-push rewriting published shared history, sole-ref delete of unmerged work, published-tag overwrite, or an immutable deploy/migration stops); needs a decision that isn't locked (an **unresolved decision** — stop, ask, and log it as a design/plan gap); turns out bigger or different than the plan said (scope drift); has a verification that can't be made executable or an unmet prerequisite; or surfaces a failing test that invalidates its premise. State the trigger plainly and wait — even mid-plan. Otherwise proceed to step 3.

### Common Rationalizations

| Excuse | Why it's wrong |
|---|---|
| "This task is small enough to skip the pre-check" | The pre-check exists precisely for tasks you're confident about — confidence is when blind spots hide. |
| "I'll run verification after the whole plan is done" | Verification gates are per-task; batch verification misses regressions introduced mid-plan. |
| "The test is wrong, not the code" | First reproduce the test's intent independently; delete only if the intent is wrong, never because it makes the code fail. |

### 2.5. Per-task isolation check (worktree-per-task mode only)

**Only when** `isolation.mode` is `worktree-per-task` AND the safety pre-check passed. Skip for all other modes.

Read the isolation mode:
```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/isolation_config.py" read [--project-root <root>]
```

If `mode` is `worktree-per-task`, run the task isolation check before starting this task:
```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/task_isolation.py" check <plan_path> <task_num>
```

- **Exit 0** (task is isolated): spawn a per-task worktree for this task via the host's own primitive — `EnterWorktree` with `name` set to `<plan-slug>-task-<N>` (Antigravity: New-Worktree-Mode / `invoke_subagent`, best-effort) — then bind it with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/worktree_marker.py" write <worktree-path> <plan-slug> <plan-path> --project-root <original-root>` (the marker binds to the *plan* slug, not the task-scoped worktree name — a per-task worktree still resolves the same plan). Announce: *"Spawning per-task worktree for task N — operator-declared isolated (N× CI cost)."* Proceed with steps 3–9 from inside the task worktree. After step 9 (commit): merge the task branch back with `git merge --no-ff <task-branch>` (the branch name the primitive returned) from the plan's main context, then prune with `ExitWorktree` `remove` (or the Antigravity equivalent). Resume the task loop in the plan's main context.
- **Exit 1** (task is not isolated): proceed directly in the current context — no worktree spawned.
- **Exit 2** or any error from `task_isolation.py`: surface stderr and stop.

**Cost note:** per-task worktrees multiply CI minutes by the number of isolated tasks (N× CI). This is the documented tradeoff — execution isolation + rollback granularity vs. pipeline minutes. The per-task override rate is the re-audit trigger: if it stays near zero, the feature isn't earning its cost.

**Knob separation:** per-task execution isolation is independent of merge granularity. Task worktrees merge back into the plan's main branch; the plan-level `integration` setting (step 12) still controls whether the finished plan lands as one PR or a direct push. Running tasks in separate worktrees does not force per-task PRs.

### 3. Gather context (optional)

If the task touches unfamiliar code, dispatch the `explorer` sub-agent for read-only fan-out ("Where is X handled? What tests exist for Y? Return file:line references."). Fan out only for multiple independent questions — for one question, just read.

**Routed dispatch (graceful-skip).** Check availability: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_capability.py" token-audit`. On **exit 0**, resolve `classify_work_type('explorer')` then `agent_tool_alias(...)` (both in token-audit's `scripts/classify_work_type.py`) and pass the result as the Agent tool's `model` param. On **exit 1** (unavailable) dispatch exactly as above with no `model` override — today's behavior, unchanged.

**Mandatory fan-out announcement (unconditional, not gated on the probe above).** Before dispatching, print one line via `fanout_announcement.py`'s `render_announcement()` — role · agent count · model · tier source (`table row` / `agent frontmatter` / `UNCLASSIFIED-DEFAULT` / `INHERITED` — `INHERITED` when no `model` param and no agent-def frontmatter resolved anything at all). If the source is `INHERITED` and the current session's own tier is frontier (T3/T4 — see `find_capability.py token-audit` + your own launch-time model), call `needs_inheritance_pause()`; if it returns true, print `inheritance_warning()`'s text and **stop for confirmation** — never proceed silently. This prints regardless of whether the routed-dispatch probe above succeeded.

### 4. Implement

- Write code that satisfies the task's **What**. Write the tests that satisfy its **Verification** in the **same session** — tests-after is an anti-pattern; verification lands with the implementation.
- Follow project conventions (formatters, naming, layout). If the task implies a deviation, flag it and ask.
- **Do not touch `wiki/`** — documentation is the step-8 phase boundary, not inline.
- If mid-implementation the task turns out bigger than planned, **stop**: *"Task N is bigger than planned because [reason]. Options: (a) finish narrow, (b) expand + re-plan, (c) split. Your call."* Then wait.

### 5. Run deterministic gates

Run in order, short-circuit on failure: **typecheck → lint → tests → build** (build only if the task affects build output). Commands come from `.harness/init.sh` / package scripts / Makefile. If a gate isn't configured, note it and skip — don't invent one.

**Evidence-tracking + operator-control hooks (graceful-skip).** If a safety/review plugin (e.g. crickets `developer-safety` / `code-review`) is installed, its hooks engage automatically — a default-FAIL evidence contract before a `[ ]`→`[x]` flip, plus `kill-switch` / `steer` / `commit-on-stop`. Absent those plugins, `/work` runs exactly as written here with no behavior change.

### 6. Iterate on failures

Feed the **full error output** into the next pass (don't summarize). If a test is itself wrong, **stop** — do not edit or delete it to go green; surface the defect and ask.

**Escalation tripwire.** Track consecutive failures on this task's current gate with `escalation_tripwire.py`'s `FailureCounter` (reset on a green pass, `record_failure()` on each red one). After each failure, call `check_and_maybe_fire()` — on the 3rd consecutive failure it writes a `/handoff-pack`-shaped escalation entry (packed context + a tier-labeled prompt, same machine-readable label format that command emits) to a vault escalation directory and returns a loud `ESCALATION:` announcement. Print it and **stop the session** — never attempt a 4th pass, and never change the session's own model to try to push through (the tripwire hands off; it does not self-escalate).

### 7. Update state

Once all gates are green: edit the **resolved `PLAN.md`** to mark the task `[x]` (`planning → in-progress` on the first task; `→ done` if it was the last). Do **not** set `features.json` `passes: true` — that's `/review`'s job. Append to the **resolved `progress.md`** (the scoped `progress-<slug>.md` when a named plan is active, never the singleton):

```
<YYYY-MM-DD HH:MM> /work — completed task N: "<title>" (<filesChanged> files, <testsAdded> tests)
```

### 8. Update the wiki (post-gates, graceful-skip)

Check availability: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_capability.py" wiki-maintenance`. On **exit 0** dispatch its `documenter` with the task's title + What + Verification and the diff — it flips `pending → implemented` **only if the diff proves it** (speculative flips are worse than missed ones), fills `## Implementation` with real `file:line` refs, and adds how-to pages for new operational concerns. Resolve `OPEN QUESTIONS` before committing; `NO CHANGES` is fine. On **exit 1** (unavailable, or no `CLAUDE_PLUGIN_ROOT`) skip silently. Not invoked during step 4. **Routed dispatch (separate graceful-skip):** additionally check `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_capability.py" token-audit`; on exit 0, resolve `classify_work_type('documenter')` + `agent_tool_alias(...)` and pass as the dispatch's `model` param; on exit 1, no `model` override — unchanged. **Mandatory fan-out announcement (unconditional):** print `fanout_announcement.py`'s `render_announcement()` line before dispatching regardless of the probe's result; an `INHERITED` source at a frontier-tier (T3/T4) session triggers `needs_inheritance_pause()` — stop for confirmation, never proceed silently.

### 9. Commit

One task, one commit, referencing the task. Follow project trailer conventions (check recent `git log`). **Do not add a `Co-Authored-By:` trailer** — the user is the sole author of intent, the agent is the tool. Don't use `--no-verify`; let pre-commit hooks run.

### 9.5. Reset evidence-tracker state (graceful-skip)

If `code-review`'s evidence-tracker is installed (`${CLAUDE_PLUGIN_ROOT}/../code-review/hooks/evidence-tracker/evidence_tracker.py` exists — check by path, no dedicated capability is declared for this), reset its per-session read state now that this task boundary is closed: `python3 "${CLAUDE_PLUGIN_ROOT}/../code-review/hooks/evidence-tracker/evidence_tracker.py" --mode reset`. This clears the read-before-flip state so the **next** task's evidence requirement is never silently satisfied by reads recorded for the task that just finished (cricketsPluginsA#3's reset gap). Silent no-op if the file doesn't exist (code-review not installed) or `CLAUDE_PLUGIN_ROOT` is unset.

### 10. Sync the task to the GitHub Project board (graceful-skip)

Check availability: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_capability.py" board-sync`. On **exit 1** (unavailable, or no `CLAUDE_PLUGIN_ROOT`) skip silently — zero behavior change. On **exit 0** with `.harness/project.json` present and `gh` authed, after the commit:

- **Task progress** — emit the just-completed task's progress line to its board item: `python3 "${CLAUDE_PLUGIN_ROOT}/../github-projects/scripts/project_sync.py" post --config <project.json> --type task-progress --id <task-id> --commit <SHA> --summary "<one human sentence>"`. The `--type task-progress` shortcut folds the `②Progress` line into `board-items.json` and re-renders; the renderer owns the date/SHA→link, you supply only the sentence. Per **DC-1** Tasks materialize only under the active plan.
- **Out-of-scope findings** — anything surfaced this session that's *not* a follow-up to the current task (an adjacent bug, a refactor, missing coverage elsewhere, a stale doc) → record in `board-items.json` as a `Backlog-item` so the next sync materializes it; **never** raw `gh project item-create` (an unbacked board issue is an orphan the `vault==board` gate flags as drift).
- **Planner maintenance cycle** — at the same gate, also run `python3 "${CLAUDE_PLUGIN_ROOT}/../github-projects/scripts/planner_maintain.py" --config <project.json>`: materializes a collapsed Feature→Plan/Plan→Task depth gap where the match is unambiguous, and corrects any `update` drift the same idempotent way a manual `post` would. Never auto-closes an orphan — a non-zero exit here is informational (something was flagged for operator judgment), not a task failure.

The write path is deterministic, one-way, idempotent-by-stable-id → recoverable; **announce + proceed** (preview with `--dry-run`). Silent-skip if `project.json` or `gh` is absent.

### 11. Loop or stop

After the commit, **loop back to step 2** for the next unchecked task — same session, same context — running the plan autonomously. Stop only when the plan is done (no `[ ]` left) or a safety pre-check fires / a clarification is needed (stop mid-plan and ask). Run an inline `/review` first when a just-finished task was high-risk. Return a ≤5-bullet summary: tasks completed this session; why it stopped (plan done / safety stop); files changed; gates (green per task, or N iterations + why); next.

When to `/review` rather than straight to the next `/work`: the task touched security/auth/payments/persistence; it was the last task in the plan; the plan's Risks flagged this area; or the change feels brittle. Skip review for routine changes (new tests, pure refactors, docs, scaffolding) — the next `/work` runs gates anyway.

### 12. Finalize the unit (when plan is done, isolation mode only)

**Only when:** the last task is now `[x]` AND step 1.5 auto-spawned a worktree (i.e. isolation mode is active). Skip entirely for direct mode (the tasks already committed on main).

Run the finalization helper — **recoverable, announce + proceed**:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/finalize_unit.py" <slug> --branch <worktree-branch> [--project-root <root>] [--title "<plan title>: plan complete — <close-out summary first line>"] [--body "<full close-out summary, the same content progress.md's close-out entry gets>"] [--no-pr if $ARGUMENTS contains --no-pr]
```

`<worktree-branch>` is the branch step 1.5's `EnterWorktree` call actually returned — never assume `worker/<slug>` (that convention retired with `spawn_worker.py`). The helper reads `isolation.integration` from `.harness/project.json` and acts accordingly:
- **`pull-request` (default):** PII guard → push `<worktree-branch>` → `gh pr create` with the close-out summary as its body → **arm auto-merge** (`gh pr merge --auto --squash`, immediately after PR creation). **`gh pr create` and `gh pr merge --auto` are both recoverable** (closeable / revertable) → announce + proceed. A PR that opens but fails to arm (e.g. "Allow auto-merge" isn't enabled on the repo yet — task 4's one-time setting) still counts as success; the helper surfaces the arm failure in its reason, not as a hard stop — merge it by hand and go fix the repo setting.
- **`direct-push`:** PII guard → push on current branch (no PR).
- **`gh` unavailable / unauthenticated / no remote:** fall back to direct push + announce the downgrade. A completed unit of work is **never hard-stopped** by a missing `gh` — the push always goes through.

After the helper returns, `ExitWorktree` `keep` (never `remove` — the branch has an open PR against it; the shepherd in task 5 or the PR's own merge is what eventually cleans it up).

Announce what's about to happen before running. A non-zero exit from the helper is a hard stop — surface the full error output.

## Failure modes to avoid

- **Pushing past a failed safety pre-check.** Being in an approved run isn't a license — if a task performs a genuinely *unrecoverable* action, is ambiguous, is scope-drifting, or needs a clarification, stop and ask, even mid-plan. (A recoverable-but-destructive action is not a stop trigger — announce it and proceed.)
- **Editing tests to make them pass.** Banned — if a test is wrong, say so and stop.
- **Skipping failed gates** ("I'll fix it next session"). Green before `[x]`.
- **Silently expanding scope.** Surface it; don't quietly do more than the plan says.
- **Summarizing errors** instead of passing them through on failure.
- **Committing without running gates.** Gates first, commit second.
- **Forgetting `PLAN.md` + `progress.md`.** The next session is blind without them.
