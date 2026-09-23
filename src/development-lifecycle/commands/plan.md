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

> **Recommended model for this phase:** Sonnet 5 (`claude-sonnet-5`) — lighter model for planning and authoring. Override with `/model` if needed.

> **Workflow-step persona (advisory, graceful-skip).** `/plan` wears the **Tech-Lead** persona for this phase — the phase spec is the source of truth for this adoption (`agentm-persona-activation.md`'s workflow-step path; a persona's `triggers:` field feeds only sub-agent routing, never this lookup). Check: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agentm_bridge.py" workflow-persona plan-phase`. **Exit 0** → read the printed persona's manifest (`<agentm-root>/personas/<name>.md`) and hold its stance + `opinions:` for this session. **Exit 1** (agentm absent, or no persona declared for this step) → proceed with this phase's own prose, unchanged — a clean graceful-skip. An operator who already put on a different persona this session keeps it — pass `--explicit <that-name>` so the resolved answer reflects the override (explicit invocation always wins over the workflow-step default).

> **Standalone + storage-agnostic.** State is plain `.harness/<file>` unless a hosting memory layer redirects it. A plan exists so a later `/work` session has a shared contract (not a verbal understanding that evaporates with context), scope is fixed before you're deep in code, and verification is pre-negotiated — the single biggest lever on review quality.

## When to use

If the brief is underspecified, run `/interview-me` first. If it's a non-trivial feature, run `/spec` first to produce `SPEC.md`, then pass `SPEC.md` to `/plan`.

## Non-negotiable constraints

1. **Do not write any application code.** Implementation is the `/work` phase.
2. **Read the resolved `PLAN.md` and `progress.md` first** (the paths agentm gives: a task under `--name` and `--stage`, and for a bare call in a repo with no vault its repo-local singleton; `--activate` is promote-only and reads no plan). If a plan is in flight (`plan_tracker.py status` says `active`, from its tracker or, without one, its Status line) and the new brief is related, **ask** "continue or replace?" — never silently overwrite.
3. **Interview only if the brief is ambiguous** (≤5 batched questions). Skip if it's clear or derivable from the codebase.
4. **Write the plan using the PLAN.md shape** below.
5. **Update `.harness/features.json`** only if this plan introduces net-new user-visible features.
6. **Dispatch the `documenter` sub-agent** (via the `wiki-maintenance` capability probe — exit 0 dispatch, exit 1 skip) once `PLAN.md` is written, to create `pending` pages for steps affecting user-visible behavior or architecture.
7. **Sync the plan to the GitHub Project board** (optional, graceful-skip) — when `github-projects` is installed (capability probe) + `.harness/project.json` present + `gh` authed, record the new plan in `board-items.json` and emit its kickoff via the github-projects plugin's `project_sync.py post`; capture `## Out of scope` deferrals as board-backed `Backlog-item`/`Idea` entries in `board-items.json` (**never** a raw `gh project item-create` — an unbacked board issue is an orphan the `vault==board` gate flags as drift). Deterministic + idempotent → announce + proceed. Silent-skip (zero behavior change) if the plugin, `project.json`, or `gh` is absent.
8. **Append one line to the resolved `progress.md`** (the resolver's second field: a task's own `progress.md` under `--name`, `--stage` and `--activate`; in a repo with no vault, the repo-local log agentm names).
9. **End with a ≤5-bullet summary.** Next command is `/work`.
10. **Ground the plan in its governing design (Hook 2, design-doc §6).** Before decomposing, resolve the living design that governs this work and read a **bounded** slice of it (frontmatter + `## Locked design calls`, ≈400-line cap — **never the whole arc**); cite it in the plan's `## Locked design calls` + `parent_design_doc:` frontmatter, or assert greenfield. Graceful-skip when agentm is absent. See step 1b.
11. **Open the plan's tracker once the plan is written** (step 7b). Only agentm's `tracker.py` writes a tracker: `/plan` calls `plan_tracker.py open` and never writes tracker text itself. The plan keeps its `**Status:**` line, mirrored from the tracker, which is the authority.

## Process

### 1. Triage existing state

Read the plan's status first: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/plan_tracker.py" status --plan <plan> --tracker <tracker>`, with the fields `resolve_plan.py` printed. It prints `<status>\t<source>`: the tracker's status when there is one, else the plan's Status line in the same five words (`queued`, `active`, `parked`, `done`, `dropped`), else `none`. Then read `PLAN.md` (in flight? continuing or replacing — ask, don't overwrite) and `progress.md` (what happened last). If the plan is `done`, `dropped` or absent, proceed to a fresh plan.

**Plan mode?** `$ARGUMENTS` selects one of **four** modes. For every *named* mode, consume the helper scripts (never re-derive paths) and treat any non-zero exit as a **hard stop** that surfaces stderr — never a singleton fallback on a dangling/unsafe binding:

- **Bare `/plan`** (no flag) — run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py"` with no name. Where it exits **4**, the project keeps its plans in numbered tasks and has no singleton: propose a verb-first task name from the brief (e.g. `build-the-brief`), wait for the operator to confirm or change it, and continue as `--name <that name>`. When the brief is arc-sized (more than one task's work), say so and point to `/design` instead: an arc is a design with parts, and each part becomes a task of its own. Where it exits **0**, you are in a repo with no vault, and agentm has answered its repo-local singleton (`.harness/PLAN.md`, `progress.md`, `tracker.md`): every step below targets those paths. Where it exits **1**, agentm is not installed: stop and say so — development-lifecycle keeps its plans through agentm.
- **`--name <slug> <brief>`** — author a named, *active* plan **directly** to the paths `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" <slug>` resolves. It prints three tab-separated fields, `<plan>\t<progress>\t<tracker>`: a task's `plan.md` / `progress.md` / `tracker.md` in `tasks/<name>/`, or, in a repo with no vault, the repo-local flat `PLAN-<slug>.md` / `progress-<slug>.md` / `tracker-<slug>.md` agentm keeps in `.harness/`. The third field is empty when agentm names no tracker. These are the paths `/work --name` reads. The quick single-worker path: the plan is live the moment it's written. The rest of `$ARGUMENTS` is the brief; every read/write below targets these paths.
- **`--stage <slug> <brief>`** — author the plan as a **queued task**: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stage_plan.py" path <slug>` prints the task's own `plan.md`, since a queued task is its own staging tier. The task stays **inert** — kept that way by the `queued` tracker step 7b opens — so a coordinator can pre-author a batch of worker tasks, one each. Only a task stages: where agentm answers a flat plan (a repo with no vault), `path` exits 2 and writes nothing; author it with `--name` instead. The rest of `$ARGUMENTS` is the brief; every read/write below targets the **staging path**. Step 4 writes the plan there, and step 8 logs to the task's own progress log (the resolver's second field).
- **`--activate <slug>`** — a **promote-only** verb, *not* an authoring run: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stage_plan.py" activate <slug>` activates a queued task in place — its tracker's move to `active` is the activation, and nothing is copied. Report the activated path, append an `activated plan "<slug>"` line to the task's own `progress.md` (the resolver's second field), and **stop — `--activate` bypasses steps 2–8 entirely** (no interview, no decompose, no plan write). It refuses (writes nothing) when the task's plan is missing, it has no tracker, or its tracker isn't `queued`, and when agentm answers a flat plan — that exit 2 + stderr is a hard stop (Risk #7). The operator runs `/work --name <slug>` next.
  - **Pre-flight reconcile (LC-6) — exit 3 is a benign no-op, not an error.** Before the activation, `activate` runs a cheap reconcile: if the staged plan declares the net-new files it ships under an `expected_artifacts:` frontmatter list and **every one already exists on `main`**, the lane is **already shipped** — `activate` exits **3** with `already shipped — nothing to do` and writes nothing. Treat exit 3 as "report the message and stop — do **not** activate or `/spawn-worker`"; it means the work is done, not that something failed. The guard is **dormant unless the plan opts in** (no `expected_artifacts` → activates exactly as before). A coordinator staging a batch declares each plan's net-new artifacts (e.g. `expected_artifacts: [src/foo/new_helper.py, wiki/decisions/0099-x.md]`) so a sibling lane that already shipped that work isn't re-launched. `/spawn-worker` runs the same reconcile as a backstop.

### 1b. Ground in the governing design (Hook 2 · design-doc §6)

Before decomposing, resolve the **living design that governs this work** and read a *bounded* slice — so the plan is built on the locked architectural calls, not in ignorance of them.

1. **Resolve.** Pick the plan's primary target (a representative repo-relative path the work will touch, or a known `area:` name) and run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agentm_bridge.py" governing-design <target>`. **Exit 0** → it prints the governing design's repo-relative path. **Exit 1** → greenfield (no design governs this) *or* agentm absent — both mean "no design to read"; proceed as greenfield. Deterministic; any failure resolves to greenfield, never a hang. (The bridge passes `--root` = cwd so it resolves *this* repo's `wiki/designs/`.)
2. **Bounded read — never the whole arc.** On exit 0, read **only** the design's YAML frontmatter **and** its `## Locked design calls` section — cap ≈400 lines. A folded arc can be tens of thousands of tokens; reading it whole on every `/plan` blows the token floor the operator just trimmed. If the design has no `## Locked design calls` section, read the frontmatter + at most the first ≈400 lines.
3. **Cite or assert greenfield.** Set the plan's `parent_design_doc:` frontmatter to the resolved path (omit when greenfield), and in `## Locked design calls` either record the locked calls this plan must honor (cite the design) or write `Greenfield — no governing design.` Set `touches_architecture: true` when the work changes architecture the design governs, else `false` (the Hook 3 gate keys off it).

### 2. Interview, if ambiguous

The single most valuable thing this phase does. Before writing, confirm:
- **Scope boundary** — what's explicitly out of scope? Name at least one thing.
- **Success criterion** — how will we know this is done? If the user can't answer, the plan is premature.
- **Non-obvious constraints** — performance budgets, compatibility, deadlines, regulated behavior.
- **Risk surface** — what part of the system is this most likely to break? What's load-bearing nearby?

Keep it ≤5 questions, batched. Default to *not* asking when the answer is derivable. Interview fatigue is a real failure mode.

### 3. Decompose into steps

Each step is: **small enough** one `/work` session finishes it (≈ one PR); **independently verifiable** (its own pass/fail); **ordered** (dependencies explicit); **concretely scoped**. Rule of thumb: if you can't describe a step's verification in one sentence, split it further.

### 4. Write the resolved `PLAN.md`

Author to the **resolved PLAN path** — the task's `plan.md` under `--name` or `--stage`, or, in a repo with no vault, the repo-local path agentm gave a bare call or `--name`. Same shape either way:

```markdown
---
parent_design_doc: <repo-relative path to the governing design — omit if greenfield>
touches_architecture: true | false
---

# Plan: <short title>

**Status:** planning
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
- **Work-type (optional):** <a token-audit routing_table.py work-type key, e.g. `mechanical-log-scraping` — only when the step's own dispatch shape is distinct from the plan's default `worker-build`>
- **Tier hint (auto, only present when Work-type is set):** <rendered via `classify_work_type.render_tier_hint(work_type)` — never hand-typed>
- **Verification:** <executable if possible>
- **Status:** [ ]

## Risks / open questions
- <real risk — what could go wrong, what we'll do>
(Keep short. "None identified" beats invented padding.)

## Verification strategy
<Which deterministic gates apply + project-specific extras.>
```

**The Status line and the tracker.** Write `**Status:** planning`. From here on `plan_tracker.py` keeps the line in step with the plan's tracker (`queued` → `planning`, `active` → `in-progress`, `done` → `done`). The tracker is the authority; the line stays for the readers that still read it.

**Tier hints (routed-dispatch amendment, graceful-skip).** Check availability: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agentm_bridge.py" capability token-audit`. On **exit 0**, for any step whose dispatch shape genuinely differs from the plan's own default (most steps don't need this — leave `Work-type` unset and skip the hint entirely), declare `Work-type` as a `routing_table.py` key and render `Tier hint` via `classify_work_type.render_tier_hint(work_type)` — never hand-type the tier/model/effort values. On **exit 1** (unavailable) omit both fields; this is optional annotation, not a plan-grounding requirement.

### 4b. Self-check grounding (Hook 3 · design-doc §6.3)

Run the deterministic plan-grounding gate on the plan you just wrote:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check-plan-grounding.py" <resolved-plan-path>`. **Exit 1** means the plan set `touches_architecture: true` but carries neither a `parent_design_doc:` nor a non-empty `## Locked design calls` — fix it (revisit step 1b) before `/work`. **Exit 0** = grounded, or the plan isn't architecture-touching (nothing to enforce). The gate is keyed off the explicit flag, never an inference.

### 5. Update `features.json` if appropriate

A feature is a user-visible capability (changelog-worthy); a step is a unit of work — **not 1:1**. Scaffolding/refactors produce no feature entry. `passes: true` is set later by `/review`, never by `/plan`. Err toward fewer feature entries.

### 6. Declare future state in the wiki (graceful-skip)

Check availability: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agentm_bridge.py" capability wiki-maintenance`. On **exit 0** dispatch its `documenter` with the new `PLAN.md` to create/update `pending` pages for steps affecting user-visible behavior or architecture (Feature/Subsystem pages, how-to skeletons, reference rows). It does not touch `Home.md` / `_Sidebar.md` (release-time concerns). Resolve any `OPEN QUESTIONS` before `/work`. On **exit 1** (unavailable, or no `CLAUDE_PLUGIN_ROOT`) skip silently. **Routed dispatch (separate graceful-skip):** additionally check `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agentm_bridge.py" capability token-audit`; on exit 0, resolve `classify_work_type('documenter')` + `agent_tool_alias(...)` and pass as the dispatch's `model` param; on exit 1, no `model` override — unchanged. **Mandatory fan-out announcement (unconditional):** print `fanout_announcement.py`'s `render_announcement()` line before dispatching regardless of the probe's result; an `INHERITED` source at a frontier-tier (T3/T4) session triggers `needs_inheritance_pause()` — stop for confirmation, never proceed silently. At `agent_count >= 4`, `announce_dispatch()` also runs the fleet cost gate (`token-audit`'s `fanout_cost_gate.py`, capability-gated) — a blocked result raises the same `pause_required` flag, stop for confirmation the same way.

### 7. Sync the plan to the GitHub Project board (graceful-skip)

Check availability: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agentm_bridge.py" capability board-sync`. On **exit 1** (unavailable, or no `CLAUDE_PLUGIN_ROOT`) skip silently — zero behavior change. On **exit 0** with `.harness/project.json` present and `gh` authed, mirror this `/plan` onto the board:

- **Plan kickoff** — record the new plan in `board-items.json` (the agent-maintained item source beside `project.json`, kept current like `features.json`; `items_source` in the config may redirect it) as a `Plan` under its Feature/Sub-feature parent with its kickoff goal, then render+write it: `python3 "$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sibling_plugin.py" github-projects scripts/project_sync.py)" post --config <project.json> --id <plan-id>` (full re-render — kickoff is template-driven, not a `--type` flag stage). Per **DC-1** a Plan posts only once it's the active plan; a staged/future plan is recorded but not posted.
- **Deferred items** — capture each intentionally-deferred `## Out of scope` entry into `board-items.json` as a `Backlog-item` (or `Idea`) so the next sync materializes it. Add them to the vault source, **never** raw `gh project item-create` — an item not backed by `board-items.json` is an orphan the `vault==board` gate (the `github-projects` check-all gate) flags as drift.

The render+write path is deterministic, one-way, and idempotent-by-stable-id (a re-run repairs, never duplicates) → recoverable, so **announce + proceed**; preview the exact `gh` argv with `--dry-run` first. Silent-skip if `project.json` or `gh` is absent.

### 7b. Open the plan's tracker (graceful-skip)

With the plan written and the board step run (so any issue number is known), open the plan's tracker at `queued`, using the fields step 1 resolved:

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/plan_tracker.py" open --plan <plan> --tracker <tracker> [--issue <N>]`

`plan_tracker.py` fills the tracker from the plan (the title; the Goal as its Objective; the first unchecked step as Next; `parent_design_doc:` as its design; the plan's name as its task) and hands the write to agentm's `tracker.py`, the only writer of a tracker. Where the tracker goes is agentm's call, never this command's:

- **`--name` and `--stage`:** `tracker.md` in the task, at `queued` — which is also what keeps a staged task inert.
- **A repo with no vault:** beside the repo-local plan agentm answered (`tracker.md` beside the singleton, `tracker-<slug>.md` beside a flat pair).

**Exit 0** includes "already open", which leaves an existing tracker alone. **Exit 3** (agentm named no tracker, its `tracker.py` is missing, or a tracker there is already final) — announce the reason and carry on: the plan runs on its Status line, as it always has. **Exit 1 or 2** — surface stderr and stop before step 8.

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
