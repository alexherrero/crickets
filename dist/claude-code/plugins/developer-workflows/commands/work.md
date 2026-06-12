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

> The session works the **whole task list autonomously** — the unit is the plan, not a single task. What keeps that safe is the **per-task safety pre-check**: before each task, decide whether it can be done safely and autonomously, and stop to ask if it can't (or if a clarification is needed). Single-threaded execution is the load-bearing constraint — never fan out parallel implementers; the autonomy boundary is the safety check, not the task count.

## Non-negotiable constraints

1. **Assume the full task list; safety-gate each task.** Work the plan's tasks autonomously, in sequence — no per-task approval. Before each task, run a safety pre-check; **stop and ask only when a task fails it (hard-to-reverse / ambiguous / scope-drifting / unverifiable) or needs a clarification** — otherwise continue to the end of the plan. Single-threaded always; never fan out parallel implementers.
2. **Gates must be green before the task is marked `[x]`.** No "I'll fix this next session" on failed gates.
3. **Never edit or delete a failing test to make it pass.** If a test is wrong, surface it and stop.
4. **Feed full error output back** on gate failures — do not summarize. The exact error is the signal.
5. **Cap iterations at 5 per gate.** If not green after 5, stop and report.
6. **Do not silently expand task scope.** If it turns out bigger than planned, stop and ask.
7. **Do not touch `wiki/` during implementation.** Documentation updates are phase-boundary-only.
8. **After gates are green (before committing), dispatch the `documenter` sub-agent** with the task spec + the diff (via the `wiki-maintenance` capability probe — exit 0 dispatch, exit 1 skip). It flips matching `pending → implemented` pages and adds operational pages if the task introduced one. Resolve `OPEN QUESTIONS` before committing.
9. **End by updating the resolved `PLAN.md` (mark `[x]`), the resolved `progress.md` (append line), and committing.**
10. **Offer deferred items to the GitHub Project** (optional). If this session surfaced anything *out of task scope* (adjacent bug, refactor opportunity, stale doc elsewhere — not follow-ups to the current task), propose one item per finding via `gh project item-create`, batched into a single preview at phase end. Silent-skip if `.harness/project.json` absent or `gh` unavailable. **No `gh` without confirmation.** Then stop.

## Process

### 1. Read state

**Resolve the active plan pair first.** A `/work` invocation may target a named plan with **`--name <slug>`** anywhere in `$ARGUMENTS`; the `task N` selector keeps its meaning, so `/work --name <slug> task N` carries both. Absent `--name`, the singleton is used. Resolve the on-disk pair by **consuming** the agentm reader — never re-deriving the paths here (pass the `--name` value as `<slug>`; omit it for the singleton):

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" [<slug>]
```

It emits one tab-separated line, `<plan_path>\t<progress_path>` — the **resolved pair** every later step reads and writes. Bare (no `--name`) resolves to the singleton `.harness/PLAN.md` / `.harness/progress.md`, **byte-identical** to the historic behavior. A **non-zero exit is a hard stop** — surface its stderr and stop; never fall back to the singleton on a dangling binding (that would silently bind the worker to the wrong plan). If `CLAUDE_PLUGIN_ROOT` is unset, treat the pair as the singleton.

Then read the **resolved `PLAN.md`** (find the first unchecked `[ ]` task, or honor the `task N` selector); the **resolved `progress.md`** (was a prior session interrupted — resume or restart?); `AGENTS.md` / `CLAUDE.md` (commit style, test runner, conventions).

### 2. Safety pre-check (before each task)

The session assumes the **full task list** — it does not ask permission per task. Before starting each task, run a go/no-go safety pre-check: **proceed autonomously if the task is safe; stop and ask only when it isn't, or when an important clarification is needed.** Triggers to stop — the task is hard to reverse or touches something destructive / external / published / security-sensitive; needs a decision that isn't locked; turns out bigger or different than the plan said (scope drift); has a verification that can't be made executable or an unmet prerequisite; or surfaces a failing test that invalidates its premise. State the trigger plainly and wait — even mid-plan. Otherwise proceed to step 3.

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

### 10. Offer deferred items to the GitHub Project (optional)

If `.harness/project.json` exists and `gh` is authed, consider whether this session surfaced anything **out of task scope** (an adjacent bug, a refactor, missing coverage elsewhere, a stale doc) — *not* follow-ups to the current task. Batch one item per finding into a single preview after the commit. Preview-and-ask is non-negotiable. Silent-skip if absent / nothing surfaced.

### 11. Loop or stop

After the commit, **loop back to step 2** for the next unchecked task — same session, same context — running the plan autonomously. Stop only when the plan is done (no `[ ]` left) or a safety pre-check fires / a clarification is needed (stop mid-plan and ask). Run an inline `/review` first when a just-finished task was high-risk. Return a ≤5-bullet summary: tasks completed this session; why it stopped (plan done / safety stop); files changed; gates (green per task, or N iterations + why); next.

When to `/review` rather than straight to the next `/work`: the task touched security/auth/payments/persistence; it was the last task in the plan; the plan's Risks flagged this area; or the change feels brittle. Skip review for routine changes (new tests, pure refactors, docs, scaffolding) — the next `/work` runs gates anyway.

## Failure modes to avoid

- **Pushing past a failed safety pre-check.** Being in an approved run isn't a license — if a task is hard-to-reverse, ambiguous, scope-drifting, or needs a clarification, stop and ask, even mid-plan.
- **Editing tests to make them pass.** Banned — if a test is wrong, say so and stop.
- **Skipping failed gates** ("I'll fix it next session"). Green before `[x]`.
- **Silently expanding scope.** Surface it; don't quietly do more than the plan says.
- **Summarizing errors** instead of passing them through on failure.
- **Committing without running gates.** Gates first, commit second.
- **Forgetting `PLAN.md` + `progress.md`.** The next session is blind without them.
