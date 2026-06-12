---
name: plan
description: Turn a brief into .harness/PLAN.md with per-task verification criteria. No code written.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: <brief — what to build or change; prefix "--name <plan-name>" to author a named plan>
---

You are running the **plan** phase of the developer-workflows loop. Turn a brief into `.harness/PLAN.md` — a structured, executable plan with per-task verification criteria. **No code is written in this phase.**

**Brief from the user:** $ARGUMENTS

> **Standalone + storage-agnostic.** State is plain `.harness/<file>` unless a hosting memory layer redirects it. A plan exists so a later `/work` session has a shared contract (not a verbal understanding that evaporates with context), scope is fixed before you're deep in code, and verification is pre-negotiated — the single biggest lever on review quality.

## Non-negotiable constraints

1. **Do not write any application code.** Implementation is the `/work` phase.
2. **Read the resolved `PLAN.md` and `progress.md` first** (the named pair when `--name <slug>` is given; the singleton otherwise). If a plan is in flight (`Status: in-progress`) and the new brief is related, **ask** "continue or replace?" — never silently overwrite.
3. **Interview only if the brief is ambiguous** (≤5 batched questions). Skip if it's clear or derivable from the codebase.
4. **Write the plan using the PLAN.md shape** below.
5. **Update `.harness/features.json`** only if this plan introduces net-new user-visible features.
6. **Dispatch the `documenter` sub-agent** (via the `wiki-maintenance` capability probe — exit 0 dispatch, exit 1 skip) once `PLAN.md` is written, to create `pending` pages for tasks affecting user-visible behavior or architecture.
7. **Offer deferred items to the GitHub Project** (optional) — scan `## Out of scope` for intentionally-deferred items (not hard non-goals); batch a single preview; **no `gh` without confirmation**; silent-skip if `.harness/project.json` absent or `gh` unavailable.
8. **Append one line to the resolved `progress.md`** (the scoped `progress-<slug>.md` for a named plan).
9. **End with a ≤5-bullet summary.** Next command is `/work`.

## Process

### 1. Triage existing state

Read `PLAN.md` (in flight? continuing or replacing — ask, don't overwrite) and `progress.md` (what happened last). If the current plan is `done` or absent, proceed to a fresh plan.

**Named plan?** If `$ARGUMENTS` contains **`--name <slug>`**, this authors a *named* plan: resolve its pair with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" <slug>` (consume the resolver — never re-derive paths) and treat the rest of `$ARGUMENTS` as the brief. Every read/write below targets the **resolved `PLAN-<slug>.md`** / scoped **`progress-<slug>.md`** pair, never the singleton. A non-zero exit is a **hard stop** (surface stderr; no singleton fallback on a dangling binding). Bare `/plan` (no `--name`) is **byte-identical** to today's singleton.

### 2. Interview, if ambiguous

The single most valuable thing this phase does. Before writing, confirm:
- **Scope boundary** — what's explicitly out of scope? Name at least one thing.
- **Success criterion** — how will we know this is done? If the user can't answer, the plan is premature.
- **Non-obvious constraints** — performance budgets, compatibility, deadlines, regulated behavior.
- **Risk surface** — what part of the system is this most likely to break? What's load-bearing nearby?

Keep it ≤5 questions, batched. Default to *not* asking when the answer is derivable. Interview fatigue is a real failure mode.

### 3. Decompose into tasks

Each task is: **small enough** one `/work` session finishes it (≈ one PR); **independently verifiable** (its own pass/fail); **ordered** (dependencies explicit); **concretely scoped**. Rule of thumb: if you can't describe a task's verification in one sentence, split it further.

### 4. Write the resolved `PLAN.md`

Author to the **resolved PLAN path** — the named `PLAN-<slug>.md` when `--name` was given, else the singleton `.harness/PLAN.md`. Same shape either way:

```markdown
# Plan: <short title>

**Status:** planning | in-progress | done
**Created:** <YYYY-MM-DD>
**Brief:** <1-3 sentence restatement>

## Goal
<2-4 sentences, user-facing.>

## Constraints
- <non-obvious constraint>

## Out of scope
- <explicit non-goal>

## Tasks

### 1. <Task title>
- **What:** <1-2 sentences>
- **Verification:** <executable if possible>
- **Status:** [ ]

## Risks / open questions
- <real risk — what could go wrong, what we'll do>
(Keep short. "None identified" beats invented padding.)

## Verification strategy
<Which deterministic gates apply + project-specific extras.>
```

### 5. Update `features.json` if appropriate

A feature is a user-visible capability (changelog-worthy); a task is a unit of work — **not 1:1**. Scaffolding/refactors produce no feature entry. `passes: true` is set later by `/review`, never by `/plan`. Err toward fewer feature entries.

### 6. Declare future state in the wiki (graceful-skip)

Probe with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/capability_probe.py" wiki-maintenance`. On **exit 0** dispatch its `documenter` with the new `PLAN.md` to create/update `pending` pages for tasks affecting user-visible behavior or architecture (Feature/Subsystem pages, how-to skeletons, reference rows). It does not touch `Home.md` / `_Sidebar.md` (release-time concerns). Resolve any `OPEN QUESTIONS` before `/work`. On **exit 1** (absent, or no `CLAUDE_PLUGIN_ROOT`) skip silently.

### 7. Offer deferred items to the GitHub Project (optional)

If `.harness/project.json` exists and `gh` is authed, scan `## Out of scope` for **intentionally-deferred** items (not hard non-goals) and propose one project item each, batched into a single preview. Preview-and-ask is non-negotiable — no `gh project item-create` without confirmation. Silent-skip if `project.json` absent or `gh` unavailable.

### 8. Stop

Do **not** start implementing — that's `/work`. Append to the resolved `progress.md`:

```
<YYYY-MM-DD HH:MM> /plan — created plan "<title>" with N tasks
```

Summarize in ≤5 bullets: the goal, task count, biggest risk, next command (`/work` to start task 1).

## Failure modes to avoid

- **Premature coding** — write it as a task; handle it in `/work`.
- **Tasks too large** — if a task touches >5 files or its verification is "it works", split it.
- **Verification hand-waving** — "manual QA" is a fallback, not a primary check.
- **Overwriting an in-flight plan** without asking.
- **Forgetting `progress.md`** — the next session won't know what happened.
