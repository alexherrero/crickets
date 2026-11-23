---
name: plan
description: Turn a brief into .harness/PLAN.md with per-step verification criteria. No code written.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
argument-hint: <brief>  |  --name <slug> <brief> (active named)  |  --stage <slug> <brief> (inactive)  |  --activate <slug> (promote staged→active)
---

You are running the **plan** phase of the developer-workflows loop. Turn a brief into `.harness/PLAN.md` — a structured, executable plan with per-step verification criteria, and open its tracker. **No code is written in this phase.**

**Brief from the user:** $ARGUMENTS

> **Recommended model for this phase:** Sonnet 5.5 (`claude-sonnet-5-5`) — lighter model for planning and authoring. Override with `/model` if needed.

> **Standalone + storage-agnostic.** State is plain `.harness/<file>` unless a hosting memory layer redirects it. A plan exists so a later `/work` session has a shared contract (not a verbal understanding that evaporates with context), scope is fixed before you're deep in code, and verification is pre-negotiated — the single biggest lever on review quality.

## When to use

Every task is graded against a spec. If the task has none, run `/spec` first: it asks at most 5 questions when the brief is ambiguous, writes the spec, and you approve it once. Then pass the spec to `/plan`.

## Non-negotiable constraints

1. **Do not write any application code.** Implementation is the `/work` phase.
2. **Read the resolved `PLAN.md` and `progress.md` first** (the paths agentm gives: a task under `--name` and `--stage`, and for a bare call in a repo with no vault its repo-local singleton; `--activate` is promote-only and reads no plan). If a plan is in flight (`plan_tracker.py status` says `active`, from its tracker) and the new brief is related, **ask** "continue or replace?" — never silently overwrite.
3. **Every task has a spec.** If it has none, run `/spec` (step 2): at most 5 batched questions, only when the brief is ambiguous. The plan's steps point to the spec; they do not restate it.
4. **Write the plan using the PLAN.md shape** below.
5. **No feature list.** The plan's tracker records what is done.
6. **Docs are not part of planning.** `/plan` writes no wiki pages: run `wiki-author` when a page should change; a repo that keeps a wiki can let `wiki-watch` catch up on a schedule.
7. **The board is not part of planning.** `/plan` posts nothing to a project board: a project that keeps one runs the `report-board-drift` cycle (on a loop or cron) to see what the board is missing, and `planner-maintain` to fix it.
8. **Append one line to the resolved `progress.md`** (the resolver's second field: a task's own `progress.md` under `--name`, `--stage` and `--activate`; in a repo with no vault, the repo-local log agentm names).
9. **End with a ≤5-bullet summary.** Next command is `/work`.
10. **Ground the plan in its governing design (Hook 2, design-doc §6).** Before decomposing, resolve the living design that governs this work and read a **bounded** slice of it (frontmatter + `## Locked design calls`, ≈400-line cap — **never the whole arc**); cite it in the plan's `## Locked design calls` + `parent_design_doc:` frontmatter, or assert greenfield. Graceful-skip when agentm is absent. See step 1b.
11. **Open the plan's tracker once the plan is written** (step 7b). Only agentm's `tracker.py` writes a tracker: `/plan` calls `plan_tracker.py open` and never writes tracker text itself. The tracker is the plan's only status: the plan carries no `**Status:**` line.

## Process

### 1. Triage existing state

Read the plan's status first: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/plan_tracker.py" status --plan <plan> --tracker <tracker>`, with the fields `resolve_plan.py` printed. It prints `<status>\t<source>`: the tracker's status (`queued`, `active`, `parked`, `done`, `dropped`), else `none`. Then read `PLAN.md` (in flight? continuing or replacing — ask, don't overwrite) and `progress.md` (what happened last). If the plan is `done`, `dropped` or absent, proceed to a fresh plan.

**Plan mode?** `$ARGUMENTS` selects one of **four** modes. For every *named* mode, consume the helper scripts (never re-derive paths) and treat any non-zero exit as a **hard stop** that surfaces stderr — never a singleton fallback on a dangling/unsafe binding:

- **Bare `/plan`** (no flag) — run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py"` with no name. Where it exits **4**, the project keeps its plans in numbered tasks and has no singleton: propose a verb-first task name from the brief (e.g. `build-the-brief`), wait for the operator to confirm or change it, and continue as `--name <that name>`. When the brief is arc-sized (more than one task's work), say so and point to `/design` instead: an arc is a design with parts, and each part becomes a task of its own. Where it exits **0**, you are in a repo with no vault, and agentm has answered its repo-local singleton (`.harness/PLAN.md`, `progress.md`, `tracker.md`): every step below targets those paths. Where it exits **1**, agentm is not installed: stop and say so — development-lifecycle keeps its plans through agentm.
- **`--name <slug> <brief>`** — author a named, *active* plan **directly** to the paths `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" <slug>` resolves. It prints three tab-separated fields, `<plan>\t<progress>\t<tracker>`: a task's `plan.md` / `progress.md` / `tracker.md` in `tasks/<name>/`, or, in a repo with no vault, the repo-local flat `PLAN-<slug>.md` / `progress-<slug>.md` / `tracker-<slug>.md` agentm keeps in `.harness/`. The third field is empty when agentm names no tracker. These are the paths `/work --name` reads. The quick single-worker path: the plan is live the moment it's written. The rest of `$ARGUMENTS` is the brief; every read/write below targets these paths.
- **`--stage <slug> <brief>`** — author the plan as a **queued task**: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stage_plan.py" path <slug>` prints the task's own `plan.md`, since a queued task is its own staging tier. The task stays **inert** — kept that way by the `queued` tracker step 7b opens — so a coordinator can pre-author a batch of worker tasks, one each. Only a task stages: where agentm answers a flat plan (a repo with no vault), `path` exits 2 and writes nothing; author it with `--name` instead. The rest of `$ARGUMENTS` is the brief; every read/write below targets the **staging path**. Step 4 writes the plan there, and step 8 logs to the task's own progress log (the resolver's second field).
- **`--activate <slug>`** — a **promote-only** verb, *not* an authoring run: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stage_plan.py" activate <slug>` activates a queued task in place — its tracker's move to `active` is the activation, and nothing is copied. Report the activated path, append an `activated plan "<slug>"` line to the task's own `progress.md` (the resolver's second field), and **stop — `--activate` bypasses steps 2–8 entirely** (no spec, no decompose, no plan write). It refuses (writes nothing) when the task's plan is missing, it has no tracker, or its tracker isn't `queued`, and when agentm answers a flat plan — that exit 2 + stderr is a hard stop (Risk #7). The operator runs `/work --name <slug>` next.
  - **Pre-flight reconcile (LC-6) — exit 3 is a benign no-op, not an error.** Before the activation, `activate` runs a cheap reconcile: if the staged plan declares the net-new files it ships under an `expected_artifacts:` frontmatter list and **every one already exists on `main`**, the lane is **already shipped** — `activate` exits **3** with `already shipped — nothing to do` and writes nothing. Treat exit 3 as "report the message and stop — do **not** activate or `/spawn-worker`"; it means the work is done, not that something failed. The guard is **dormant unless the plan opts in** (no `expected_artifacts` → activates exactly as before). A coordinator staging a batch declares each plan's net-new artifacts (e.g. `expected_artifacts: [src/foo/new_helper.py, wiki/decisions/0099-x.md]`) so a sibling lane that already shipped that work isn't re-launched. `/spawn-worker` runs the same reconcile as a backstop.

### 1b. Ground in the governing design (Hook 2 · design-doc §6)

Before decomposing, resolve the **living design that governs this work** and read a *bounded* slice — so the plan is built on the locked architectural calls, not in ignorance of them.

1. **Resolve.** Pick the plan's primary target (a representative repo-relative path the work will touch, or a known `area:` name) and run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agentm_bridge.py" governing-design <target>`. **Exit 0** → it prints the governing design's repo-relative path. **Exit 1** → no `wiki/designs/` page governs this, or agentm is absent: look in the vault next. (The bridge passes `--root` = cwd so it resolves *this* repo's `wiki/designs/`.) **Then the vault.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vault_designs.py" find <target> --cwd .` prints the path of the project's living design note that governs the target. **Exit 0** → read it as step 2 says. **Exit 1** (no note governs it) or **exit 3** (no vault, or agentm absent) → greenfield; proceed as greenfield. Deterministic; any failure resolves to greenfield, never a hang.
2. **Bounded read — never the whole arc.** On exit 0, read **only** the design's YAML frontmatter **and** its `## Locked design calls` section — cap ≈400 lines. A folded arc can be tens of thousands of tokens; reading it whole on every `/plan` blows the token floor the operator just trimmed. If the design has no `## Locked design calls` section, read the frontmatter + at most the first ≈400 lines.
3. **Cite or assert greenfield.** Set the plan's `parent_design_doc:` frontmatter to the resolved path (omit when greenfield), and in `## Locked design calls` either record the locked calls this plan must honor (cite the design) or write `Greenfield — no governing design.`

### 2. Anchor: the spec

Every task is graded against a spec: Goal, Done when, Rules (each with its source), Not doing, Open questions. If the task has none, run **`/spec`** now, with `--plan <the resolved plan path>` (add `--multi` when one spec covers several tasks). It asks at most 5 questions, batched, and only when the brief is ambiguous; you approve it once. Its Done when is this plan's success criterion and its Not doing is the plan's out-of-scope, so do not ask those again. A task that already has a spec (`spec.md` beside the plan, or one the brief names) keeps it.

### 3. Decompose into steps

Each step is: **small enough** one `/work` session finishes it (≈ one PR); **independently verifiable** (its own pass/fail); **ordered** (dependencies explicit); **concretely scoped**. Rule of thumb: if you can't describe a step's verification in one sentence, split it further.

### 4. Write the resolved `PLAN.md`

Author to the **resolved PLAN path** — the task's `plan.md` under `--name` or `--stage`, or, in a repo with no vault, the repo-local path agentm gave a bare call or `--name`. Same shape either way:

```markdown
---
parent_design_doc: <repo-relative path to the governing design — omit if greenfield>
---

# Plan: <short title>

**Created:** <YYYY-MM-DD>
**Brief:** <1-3 sentence restatement>

## Goal
<2-4 sentences, user-facing.>

## Constraints
- <non-obvious constraint>

## Out of scope
- <explicit non-goal>

## Locked design calls
<Hook 2: the locked architectural calls from `parent_design_doc` this plan must honor (cite the design path), or "Greenfield — no governing design.">

## Steps

### 1. <Step title>
- **What:** <1-2 sentences>
- **Anchor:** <path to the spec this step is graded against>
- **Profile:** build | create | both
- **Size:** small | medium | large
- **Verification:** <executable if possible>
- **Status:** [ ]

## Risks / open questions
- <real risk — what could go wrong, what we'll do>
(Keep short. "None identified" beats invented padding.)

## Verification strategy
<Which deterministic gates apply + project-specific extras.>
```

**Anchor, Profile and Size** tell `/work` how to run the step's loop (`/build-it` or `/create-it`). Anchor is the spec's path. Profile is `build` for code, `create` for art, sound, UI look or prose, `both` for a step that makes both. Size is your call: `small` (a few lines, no new behaviour), `medium` (one feature or fix), `large` (a new module, a changed contract, roughly 300 changed lines or 8 files). A step with none of the three is a legacy step: `/work` treats it as `build`, `medium`, anchored to the plan.

**No Status line.** The plan carries no `**Status:**` line: its status is its tracker's, which step 7b opens at `queued`. Each step keeps its own `- **Status:** [ ]` checkbox.

### 5. Features

Nothing happens here (constraint 5).

### 6. Docs

Nothing happens here (constraint 6).

### 7. Board

Nothing happens here (constraint 7).

### 7b. Open the plan's tracker (graceful-skip)

With the plan written, open the plan's tracker at `queued`, using the fields step 1 resolved:

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/plan_tracker.py" open --plan <plan> --tracker <tracker> [--issue <N>]`

`plan_tracker.py` fills the tracker from the plan (the title; the Goal as its Objective; the first unchecked step as Next; `parent_design_doc:` as its design; the plan's name as its task) and hands the write to agentm's `tracker.py`, the only writer of a tracker. Where the tracker goes is agentm's call, never this command's:

- **`--name` and `--stage`:** `tracker.md` in the task, at `queued` — which is also what keeps a staged task inert.
- **A repo with no vault:** beside the repo-local plan agentm answered (`tracker.md` beside the singleton, `tracker-<slug>.md` beside a flat pair).

**Exit 0** includes "already open", which leaves an existing tracker alone. **Exit 3** (agentm named no tracker, its `tracker.py` is missing, or a tracker there is already final) — announce the reason and carry on without a tracker; the first `/work` opens one at its first step. **Exit 1 or 2** — surface stderr and stop before step 8.

### 8. Stop

Do **not** start implementing — that's `/work`. Append one line to the resolved `progress.md` — under `--stage` too, since a staged task writes to its own progress log:

```
<YYYY-MM-DD HH:MM> /plan — created plan "<title>" with N steps
```

Under `--stage`, lead the line with `staged` (`/plan --stage — staged plan "<title>" with N steps`) so the coordinator's log distinguishes inert plans from active ones.

Summarize in ≤5 bullets: the goal, step count, biggest risk, next command (`/work` to start step 1, or `/plan --activate <slug>` when this was a `--stage` author).

After `progress.md` is written, run `/clear` rather than `/compact`. State is on disk; a compaction summary re-bills on every later turn.

## Failure modes to avoid

- **Premature coding** — write it as a step; handle it in `/work`.
- **Steps too large** — if a step touches >5 files or its verification is "it works", split it.
- **Verification hand-waving** — "manual QA" is a fallback, not a primary check.
- **Overwriting an in-flight plan** without asking.
- **Forgetting `progress.md`** — the next session won't know what happened.
- **Recoverability-gate mismatch** — planning a step that stops for push/tag/release confirmation after the operator's invocation already granted authorization. The invocation *is* the authorization; recoverable actions proceed announced, only unrecoverable ones stop.
- **Close-out approval gate** — writing a plan step that pauses for explicit approval before archiving a completed plan, appending `progress.md`, or moving a ROADMAP item. Close-out bookkeeping is autonomous by contract.
