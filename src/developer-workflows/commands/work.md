---
name: work
description: Implement exactly one task from .harness/PLAN.md. Stop after one, gates green.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: [optional — "task N" to pick a specific task instead of the next unchecked one]
---

You are running the **work** phase of the developer-workflows loop. Implement **exactly one** task from `.harness/PLAN.md`. Stop when that task is done and its verification gates are green. **Do not start the next task.**

**Argument (if any):** $ARGUMENTS

> "One task per session" is not a suggestion — it's the load-bearing constraint that keeps implementation single-threaded and coherent. Parallel implementers produce mutually-inconsistent decisions; single-task sessions let you hold the full context of what you're changing and why.

## Non-negotiable constraints

1. **One task per session.** Do not start the next task, even if it looks easy.
2. **Gates must be green before the task is marked `[x]`.** No "I'll fix this next session" on failed gates.
3. **Never edit or delete a failing test to make it pass.** If a test is wrong, surface it and stop.
4. **Feed full error output back** on gate failures — do not summarize. The exact error is the signal.
5. **Cap iterations at 5 per gate.** If not green after 5, stop and report.
6. **Do not silently expand task scope.** If it turns out bigger than planned, stop and ask.
7. **Do not touch `wiki/` during implementation.** Documentation updates are phase-boundary-only.
8. **After gates are green (before committing), dispatch the `documenter` sub-agent** with the task spec + the diff (graceful-skip if no docs/wiki plugin). It flips matching `pending → implemented` pages and adds operational pages if the task introduced one. Resolve `OPEN QUESTIONS` before committing.
9. **End by updating `PLAN.md` (mark `[x]`), `progress.md` (append line), and committing.**
10. **Offer deferred items to the GitHub Project** (optional). If this session surfaced anything *out of task scope* (adjacent bug, refactor opportunity, stale doc elsewhere — not follow-ups to the current task), propose one item per finding via `gh project item-create`, batched into a single preview at phase end. Silent-skip if `.harness/project.json` absent or `gh` unavailable. **No `gh` without confirmation.** Then stop.

## Process

### 1. Read state

Read `PLAN.md` (find the first unchecked `[ ]` task, or honor `/work task N`); `progress.md` (was a prior session interrupted — resume or restart?); `AGENTS.md` / `CLAUDE.md` (commit style, test runner, conventions).

### 2. Confirm scope

Before writing any code, state the task in one sentence and confirm:

> About to work on **task N: <title>**. Verification: <one-line criterion>. OK?

Skip only if the user explicitly said "just work on the next task." The confirmation is cheap and catches plan/intent drift.

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

Once all gates are green: edit `PLAN.md` to mark the task `[x]` (`planning → in-progress` on the first task; `→ done` if it was the last). Do **not** set `features.json` `passes: true` — that's `/review`'s job. Append to `progress.md`:

```
<YYYY-MM-DD HH:MM> /work — completed task N: "<title>" (<filesChanged> files, <testsAdded> tests)
```

### 8. Update the wiki (post-gates, graceful-skip)

If a docs/wiki plugin is installed, dispatch its `documenter` with the task's title + What + Verification and the diff. It flips `pending → implemented` **only if the diff proves it** (speculative flips are worse than missed ones), fills `## Implementation` with real `file:line` refs, and adds how-to pages for new operational concerns. Resolve `OPEN QUESTIONS` before committing; `NO CHANGES` is fine. Not invoked during step 4.

### 9. Commit

One task, one commit, referencing the task. Follow project trailer conventions (check recent `git log`). **Do not add a `Co-Authored-By:` trailer** — the user is the sole author of intent, the agent is the tool. Don't use `--no-verify`; let pre-commit hooks run.

### 10. Offer deferred items to the GitHub Project (optional)

If `.harness/project.json` exists and `gh` is authed, consider whether this session surfaced anything **out of task scope** (an adjacent bug, a refactor, missing coverage elsewhere, a stale doc) — *not* follow-ups to the current task. Batch one item per finding into a single preview after the commit. Preview-and-ask is non-negotiable. Silent-skip if absent / nothing surfaced.

### 11. Stop

**Do not start the next task** — it gets its own session (`/work` again, or `/review` first if the task was high-risk). Return a ≤5-bullet summary: task completed; files changed; tests added; gates (all green, or N iterations + why); next (`/review` if high-risk, else `/work`, or `/release` if all tasks done).

When to `/review` rather than straight to the next `/work`: the task touched security/auth/payments/persistence; it was the last task in the plan; the plan's Risks flagged this area; or the change feels brittle. Skip review for routine changes (new tests, pure refactors, docs, scaffolding) — the next `/work` runs gates anyway.

## Failure modes to avoid

- **Starting the next task "while you're in there."** The most common way `/work` breaks coherence. Stop after one.
- **Editing tests to make them pass.** Banned — if a test is wrong, say so and stop.
- **Skipping failed gates** ("I'll fix it next session"). Green before `[x]`.
- **Silently expanding scope.** Surface it; don't quietly do more than the plan says.
- **Summarizing errors** instead of passing them through on failure.
- **Committing without running gates.** Gates first, commit second.
- **Forgetting `PLAN.md` + `progress.md`.** The next session is blind without them.
