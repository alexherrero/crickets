---
name: plan
description: Turn a brief into .harness/PLAN.md with per-task verification criteria. No code written.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: <brief>  |  --name <slug> <brief> (active named)  |  --stage <slug> <brief> (inactive)  |  --activate <slug> (promote staged→active)
---

You are running the **plan** phase of the developer-workflows loop. Turn a brief into `.harness/PLAN.md` — a structured, executable plan with per-task verification criteria. **No code is written in this phase.**

**Brief from the user:** $ARGUMENTS

> **Recommended model for this phase:** Sonnet 4.6 (`claude-sonnet-4-6`) — lighter model for planning and authoring. Override with `/model` if needed.

> **Standalone + storage-agnostic.** State is plain `.harness/<file>` unless a hosting memory layer redirects it. A plan exists so a later `/work` session has a shared contract (not a verbal understanding that evaporates with context), scope is fixed before you're deep in code, and verification is pre-negotiated — the single biggest lever on review quality.

## When to use

If the brief is underspecified, run `/interview-me` first. If it's a non-trivial feature, run `/spec` first to produce `SPEC.md`, then pass `SPEC.md` to `/plan`.

## Non-negotiable constraints

1. **Do not write any application code.** Implementation is the `/work` phase.
2. **Read the resolved `PLAN.md` and `progress.md` first** (the named pair under `--name`, the staged path under `--stage`, the singleton otherwise; `--activate` is promote-only and reads no plan). If a plan is in flight (`Status: in-progress`) and the new brief is related, **ask** "continue or replace?" — never silently overwrite.
3. **Interview only if the brief is ambiguous** (≤5 batched questions). Skip if it's clear or derivable from the codebase.
4. **Write the plan using the PLAN.md shape** below.
5. **Update `.harness/features.json`** only if this plan introduces net-new user-visible features.
6. **Dispatch the `documenter` sub-agent** (via the `wiki-maintenance` capability probe — exit 0 dispatch, exit 1 skip) once `PLAN.md` is written, to create `pending` pages for tasks affecting user-visible behavior or architecture.
7. **Sync the plan to the GitHub Project board** (optional, graceful-skip) — when `github-projects` is installed (capability probe) + `.harness/project.json` present + `gh` authed, record the new plan in `board-items.json` and emit its kickoff via the github-projects plugin's `project_sync.py post`; capture `## Out of scope` deferrals as board-backed `Backlog-item`/`Idea` entries in `board-items.json` (**never** a raw `gh project item-create` — an unbacked board issue is an orphan the `vault==board` gate flags as drift). Deterministic + idempotent → announce + proceed. Silent-skip (zero behavior change) if the plugin, `project.json`, or `gh` is absent.
8. **Append one line to the resolved `progress.md`** (the scoped `progress-<slug>.md` for `--name`; the singleton for `--stage` and `--activate`, which have no run-scoped log yet).
9. **End with a ≤5-bullet summary.** Next command is `/work`.

## Process

### 1. Triage existing state

Read `PLAN.md` (in flight? continuing or replacing — ask, don't overwrite) and `progress.md` (what happened last). If the current plan is `done` or absent, proceed to a fresh plan.

**Plan mode?** `$ARGUMENTS` selects one of **four** modes. For every *named* mode, consume the helper scripts (never re-derive paths) and treat any non-zero exit as a **hard stop** that surfaces stderr — never a singleton fallback on a dangling/unsafe binding:

- **Bare `/plan`** (no flag) — the singleton `.harness/PLAN.md` / `progress.md` pair, **byte-identical to today**; every step below targets the singleton.
- **`--name <slug> <brief>`** — author a named, *active* plan **directly** to the pair `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" <slug>` resolves (`PLAN-<slug>.md` / `progress-<slug>.md` — the path `/work --name` reads). The quick single-worker path: the plan is live the moment it's written. The rest of `$ARGUMENTS` is the brief; every read/write below targets this pair.
- **`--stage <slug> <brief>`** — author the plan to the **inactive** staging path that `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stage_plan.py" path <slug>` prints (`<_harness>/queued-plans/PLAN-<slug>.md`), *instead of* the active path. The written plan is **inert** — invisible to `/work` and `/queue-status-lite` — so a coordinator can pre-author a batch of worker plans, one file each. The rest of `$ARGUMENTS` is the brief; every read/write below targets the **staging path** (step 4 writes the plan there; step 8 logs to the singleton `progress.md`, since no run-scoped `progress-<slug>.md` exists until the plan is activated and first worked).
- **`--activate <slug>`** — a **promote-only** verb, *not* an authoring run: copy the staged `queued-plans/PLAN-<slug>.md` onto the active `PLAN-<slug>.md` via `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stage_plan.py" activate <slug>`, report the activated path, append an `activated plan "<slug>"` line to the singleton `progress.md`, and **stop — `--activate` bypasses steps 2–8 entirely** (no interview, no decompose, no plan write). The guarded copy refuses (writes nothing) when an active `PLAN-<slug>.md` already exists *or* the staged file is missing — that exit 2 + stderr is a hard stop (Risk #7). The operator runs `/work --name <slug>` next.
  - **Pre-flight reconcile (LC-6) — exit 3 is a benign no-op, not an error.** Before the copy, `activate` runs a cheap reconcile: if the staged plan declares the net-new files it ships under an `expected_artifacts:` frontmatter list and **every one already exists on `main`**, the lane is **already shipped** — `activate` exits **3** with `already shipped — nothing to do` and writes nothing. Treat exit 3 as "report the message and stop — do **not** activate or `/spawn-worker`"; it means the work is done, not that something failed. The guard is **dormant unless the plan opts in** (no `expected_artifacts` → activates exactly as before). A coordinator staging a batch declares each plan's net-new artifacts (e.g. `expected_artifacts: [src/foo/new_helper.py, wiki/decisions/0099-x.md]`) so a sibling lane that already shipped that work isn't re-launched. `/spawn-worker` runs the same reconcile as a backstop.

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

Author to the **resolved PLAN path** — the staged `queued-plans/PLAN-<slug>.md` under `--stage`, the active `PLAN-<slug>.md` under `--name`, else the singleton `.harness/PLAN.md`. Same shape either way:

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

Check availability: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_capability.py" wiki-maintenance`. On **exit 0** dispatch its `documenter` with the new `PLAN.md` to create/update `pending` pages for tasks affecting user-visible behavior or architecture (Feature/Subsystem pages, how-to skeletons, reference rows). It does not touch `Home.md` / `_Sidebar.md` (release-time concerns). Resolve any `OPEN QUESTIONS` before `/work`. On **exit 1** (unavailable, or no `CLAUDE_PLUGIN_ROOT`) skip silently.

### 7. Sync the plan to the GitHub Project board (graceful-skip)

Check availability: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_capability.py" board-sync`. On **exit 1** (unavailable, or no `CLAUDE_PLUGIN_ROOT`) skip silently — zero behavior change. On **exit 0** with `.harness/project.json` present and `gh` authed, mirror this `/plan` onto the board:

- **Plan kickoff** — record the new plan in `board-items.json` (the agent-maintained item source beside `project.json`, kept current like `features.json`; `items_source` in the config may redirect it) as a `Plan` under its Feature/Sub-feature parent with its kickoff goal, then render+write it: `python3 "${CLAUDE_PLUGIN_ROOT}/../github-projects/scripts/project_sync.py" post --config <project.json> --id <plan-id>` (full re-render — kickoff is template-driven, not a `--type` flag stage). Per **DC-1** a Plan posts only once it's the active plan; a staged/future plan is recorded but not posted.
- **Deferred items** — capture each intentionally-deferred `## Out of scope` entry into `board-items.json` as a `Backlog-item` (or `Idea`) so the next sync materializes it. Add them to the vault source, **never** raw `gh project item-create` — an item not backed by `board-items.json` is an orphan the `vault==board` gate (the `github-projects` check-all gate) flags as drift.

The render+write path is deterministic, one-way, and idempotent-by-stable-id (a re-run repairs, never duplicates) → recoverable, so **announce + proceed**; preview the exact `gh` argv with `--dry-run` first. Silent-skip if `project.json` or `gh` is absent.

### 8. Stop

Do **not** start implementing — that's `/work`. Append one line to the resolved `progress.md` (under `--stage`, write to the singleton `progress.md` — the staged plan has no run-scoped log until it's activated and first worked):

```
<YYYY-MM-DD HH:MM> /plan — created plan "<title>" with N tasks
```

Under `--stage`, lead the line with `staged` (`/plan --stage — staged plan "<title>" with N tasks`) so the coordinator's log distinguishes inert plans from active ones.

Summarize in ≤5 bullets: the goal, task count, biggest risk, next command (`/work` to start task 1, or `/plan --activate <slug>` when this was a `--stage` author).

After `progress.md` is written, run `/clear` rather than `/compact`. State is on disk; a compaction summary re-bills on every later turn.

## Failure modes to avoid

- **Premature coding** — write it as a task; handle it in `/work`.
- **Tasks too large** — if a task touches >5 files or its verification is "it works", split it.
- **Verification hand-waving** — "manual QA" is a fallback, not a primary check.
- **Overwriting an in-flight plan** without asking.
- **Forgetting `progress.md`** — the next session won't know what happened.
- **Recoverability-gate mismatch** — planning a task step that stops for push/tag/release confirmation after the operator's invocation already granted authorization. The invocation *is* the authorization; recoverable actions proceed announced, only unrecoverable ones stop.
- **Close-out approval gate** — writing a plan task that pauses for explicit approval before archiving a completed plan, appending `progress.md`, or moving a ROADMAP item. Close-out bookkeeping is autonomous by contract.
