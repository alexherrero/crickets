# Named plans

The `development-lifecycle` phase commands `/work`, `/plan`, `/review` and `/release` accept an optional `--name <slug>` flag. A name selects a task: `tasks/NNN-<verb-slug>/` with its `plan.md`, `progress.md` and `tracker.md`, wherever agentm keeps the project's tasks. This lets you hold several concurrent plans in one project. A plan also has a tracker whenever agentm names one, and the commands read its status before the plan's `**Status:**` line (see [Trackers](#trackers)). A bare invocation in a project that keeps tasks asks which task. In a repo with no vault, agentm keeps a repo-local layout instead — a singleton `.harness/PLAN.md` or a flat `.harness/PLAN-<slug>.md` — and the commands follow it (see [A repo with no vault](#a-repo-with-no-vault)).

This page explains what a name maps to and how we resolve it. It also covers the read-only `/queue-status-lite` command. You can find the task recipes in [Run a named plan](Run-A-Named-Plan) and [See every active plan](See-Every-Active-Plan). If you want the context behind this approach, read [Why phase-gating](Why-Phase-Gating).

## ⚡ Quick Reference

| Invocation | Plan file read/written | Progress file appended | Notes |
|---|---|---|---|
| `/work` | — | — | asks which task (a bare call in a project that keeps tasks) |
| `/work --name <task>` | `tasks/<task>/plan.md` | `tasks/<task>/progress.md` | the named task |
| `/work --name <task> step N` | `tasks/<task>/plan.md` | `tasks/<task>/progress.md` | the named task + step selector (`task N` works too) |
| `/plan` | — | — | proposes a task name, then as `--name` |
| `/plan --name <task>` | `tasks/NNN-<task>/plan.md` (authored, **active**) | its `progress.md` | a new numbered task; its tracker opens at `queued` |
| `/plan --stage <task>` | `tasks/NNN-<task>/plan.md` (authored, **queued/inert**) | its `progress.md` | a queued task ([Staging](#staging-a-queued-task)) |
| `/plan --activate <task>` | — | its `progress.md` | moves the task's tracker from `queued` to `active` |
| `/review --name <task>` | `tasks/<task>/plan.md` | — | the named task |
| `/release --name <task>` | `tasks/<task>/plan.md` | — | the named task; its status must be `done` |
| `/work` (auto-spawn, `isolation.mode: worktree-per-plan`) | — (host creates a worktree; `worktree_marker.py` binds it to the plan) | — | host-native worktree at `.claude/worktrees/<name>` on branch `worktree-<name>` ([Spawning a worker worktree](#spawning-a-worker-worktree)) |
| `/work` (final task, auto-close) | — | plan's close-out summary becomes the PR body | pushes the branch, opens a PR via `finalize_unit.py`, arms `gh pr merge --auto --squash` ([Closing out a plan](#closing-out-a-plan)) |
| `/design author [<slug>]` | the design doc (not a PLAN) | — | walks the 10-section template, drives `draft → review → final` ([The `/design` command](#the-design-command)) |
| `/design translate` | `<doc-dir>/parts/<part-slug>.md` (writes parts, reads the doc) | — | gates on `Status: final`, splits the doc into structural parts |
| `/design sequence` | `tasks/NNN-<doc-slug>-<part-slug>/plan.md` + a `queued` `tracker.md`, per part | — | one queued task per part via `design_sequence.py place`; none activated; never a flat staging directory |

> [!NOTE]
> The table shows paths inside the project agentm resolves; the directory is whatever it returns (see [Numbered tasks](#numbered-tasks) and [Resolution](#resolution)). In a repo with no vault the paths are the repo-local ones in [A repo with no vault](#a-repo-with-no-vault).

## Commands that accept a name

| Command | Argument | Effect with a name |
|---|---|---|
| `/work` | optional `--name <slug>` (anywhere in args) | reads the named PLAN, appends the scoped progress, marks `[x]` in the named PLAN, keeps its tracker current |
| `/plan` | optional `--name <slug>` (anywhere in args) | authors the task's `plan.md`, appends its `progress.md` line, opens its `tracker.md` at `queued` |
| `/review` | optional `--name <slug>` (anywhere in args) | resolves + reads the named plan and its status for adversarial critique |
| `/release` | optional `--name <slug>` (anywhere in args) | resolves the named plan and requires its status to be `done` |

The `/setup` command does not accept a plan name. `/bugfix` resolves its plan without one: the plan the worktree's `.harness/active-plan` marker binds, or agentm's answer for a bare call. In a project that keeps tasks, a bare `/work`, `/review` or `/release` asks which task, and a bare `/plan` or `/bugfix` proposes a task name for you to confirm.

## Trackers

A tracker is a plan's living head: its status, what is true now, the next steps, and the outcome at close, in agentm's one schema. Only agentm's `scripts/tracker.py` writes a tracker. The commands reach it through one helper, `plan_tracker.py`, which composes the arguments, reads `tracker.py show`'s JSON, and never edits tracker text itself.

| Layout | Plan | Tracker |
|---|---|---|
| numbered task | `tasks/NNN-<verb-slug>/plan.md` | `tasks/NNN-<verb-slug>/tracker.md` |
| a repo with no vault, bare | `.harness/PLAN.md` | `.harness/tracker.md` |
| a repo with no vault, named | `.harness/PLAN-<slug>.md` | `.harness/tracker-<slug>.md` |

| Command | What it does with the tracker |
|---|---|
| `/plan` | opens it at `queued` after the board step (`plan_tracker.py open`), in the task under `--name` and `--stage`, or beside a repo-local plan |
| `/plan --activate` | moves a queued task's tracker from `queued` to `active` |
| `/work` | marks the start (`step`, which opens a missing tracker and moves it to `active`), rewrites State and Next after each step, records a safety stop's trigger, and writes the Outcome at close (`close`) |
| `/review` | reads the status, and with no explicit scope stops on `queued` |
| `/release` | requires the status to be `done` |
| `/bugfix` | reads the status, and asks before writing into a plan that is `queued`, `active` or `parked` |

`plan_tracker.py status` prints `<status>\t<source>`: the tracker's status when there is one, else the plan's `**Status:**` line in the same five words (`planning` reads as `queued`, `in-progress` as `active`), else `none`. After a `step` or a `close`, the helper rewrites the plan's existing Status line to match (`queued` → `planning`, `active` → `in-progress`, `done` → `done`). Readers that still read the line see the same answer. The helper never adds a line. When agentm names no tracker (a standalone project, or an agentm from before the tracker), the helper exits 3. The command says so, and the plan runs on its Status line.

## Numbered tasks

Once agentm's migration moves a project (agentm-vault plan 10), each plan lives in a task directory, `projects/<slug>/tasks/NNN-<verb-slug>/`, with `plan.md`, `progress.md` and `tracker.md` side by side. A task's name is its directory name, number included. `--name`, the worktree marker and the tracker's `task:` field all carry it. A project that keeps tasks has no singleton, so the resolver answers a bare call with exit 4. The commands then ask for or propose a task name. crickets composes none of these paths. Every command follows the plan, progress and tracker paths agentm returns, and tells a task from a repo-local flat plan by its `plan.md` name.

## The `/design` command

The `/design` command handles the upstream authoring step of the phase loop. It starts earlier than `/plan`. You should use it when the problem is ambiguous, involves multiple stakeholders, or touches cross-cutting Quality Attributes and Operations concerns. If you already have a settled design, use `/plan` instead. We provide the task recipe in [Author a design](Author-A-Design). We explain the reasoning behind this split in the [Development lifecycle design](crickets-development-lifecycle).

| Surface | Location |
|---|---|
| Command prompt | [`commands/design.md`](https://github.com/alexherrero/crickets/blob/main/src/design/commands/design.md) — the three sub-verb flows (interactive, human-judgment) |
| Gate + storage helper | [`scripts/design_doc.py`](https://github.com/alexherrero/crickets/blob/main/src/design/scripts/design_doc.py) — `require_final()` the `Status: final` gate, `detailed_design_nonempty()`, frontmatter parser, designs-home / published-path resolution |
| Topo-sort helper | [`scripts/design_sequence.py`](https://github.com/alexherrero/crickets/blob/main/src/design/scripts/design_sequence.py) — Kahn topo-sort with alphabetical tie-break, part-frontmatter validation |

| Sub-verb | Reads | Writes | Gate (helper) |
|---|---|---|---|
| `/design author [<slug>]` | the design doc (on re-invoke) | the design doc | refuses re-invocation once `Status: final`; only `author` transitions Status |
| `/design translate` | a `Status: final` design doc | `<doc-dir>/parts/<part-slug>.md` | `design_doc.py gate` (`Status: final`) **and** `design_doc.py detailed-design` (non-empty `### Detailed Design`); both exit 2 + reason on failure |
| `/design sequence` | the populated `<designs>/<slug>/parts/` | one queued task per part (see below) | `design_doc.py gate` + non-empty validated `parts/`; ordering via `design_sequence.py order` (exit 2 on cycle / missing-dep) |

### `/design author`

| Property | Value |
|---|---|
| Template | 10 sections: Context → Design → Alternatives Considered → Dependencies → Migrations → Technical Debt & Risks → Quality Attributes → Project management → Operations → Document History |
| Quality-Attributes drill-down | 11 sub-attrs, each described or marked `N/A: <one-sentence reason>` |
| Status lifecycle | `draft → review → final` (only `author` transitions Status; never backwards via the command) |
| Review | inline pass — approve / revise / skip per section |
| Refusal | refuses re-invocation after the doc reaches `Status: final` |

### `/design translate`

| Property | Value |
|---|---|
| Gate | refuses unless the doc is `Status: final` |
| Default split | one part per Detailed-Design subsection, capped at ~6 parts |
| Reshape | interactive — merge / split / rename / reorder before writing |
| Output | structural part files at `<doc-dir>/parts/<part-slug>.md` |

### `/design sequence`

| Property | Value |
|---|---|
| Input | the populated `<designs>/<slug>/parts/` (`design_doc.py parts-dir <slug>`) |
| Ordering | topo-sort, deterministic; alphabetical tie-break |
| Writer | `design_sequence.py check-names` then `place`, one part at a time — agentm places each task (through development-lifecycle's `resolve_plan.py`) and `plan_tracker.py` opens its tracker |
| Every part | a new task `tasks/NNN-<doc-slug>-<part-slug>/`, tracker `queued`, naming the design; **none activated** |
| A project that keeps no tasks | **refused** before anything is written |

### Storage

| Visibility | Design doc home |
|---|---|
| `confidential` | `<designs>/<slug>.md` — the project's own `designs/`, which agentm names (`design_doc.py design-path <slug>`); not committed |
| `published` | `wiki/designs/<slug>.md` — committed (the crickets path, **not** agentm's `wiki/explanation/designs/`) |

## Staging a queued task

The `/plan` command can write an active task directly using `--name`. It can also stage a task: write it but leave it inert until a worker is ready to pick it up. A queued task is its own staging tier — its `plan.md` sits in its own directory, and its `queued` tracker is what keeps it inert. Activation moves the tracker to `active`; nothing is copied.

### The four `/plan` modes

| Mode | Writes | Tier | Picked up by `/work`? |
|---|---|---|---|
| `/plan <brief>` | proposes a task name first | — | — |
| `/plan --name <task> <brief>` | `tasks/NNN-<task>/plan.md` | active | yes |
| `/plan --stage <task> <brief>` | `tasks/NNN-<task>/plan.md`, tracker `queued` | **queued (inert)** | **no** — until activated |
| `/plan --activate <task>` | the tracker: `queued` → `active` | queued → active | yes, after activation |

Only a task stages. Where agentm answers a flat plan — a repo with no vault keeps its plans in its repo-local `.harness/` — `path` and `activate` refuse (exit 2) and write nothing; write that plan with `--name`. The retired `queued-plans/` tier was a layout crickets composed itself.

### `--activate` guard

| Condition | Behavior |
|---|---|
| The task's `plan.md` is missing | refuse — nothing to activate |
| The task has no tracker | refuse — a queued task is its `queued` tracker |
| Its tracker isn't `queued` | refuse |
| agentm answers a flat plan | refuse — staging needs the task layout |
| The plan declares `expected_artifacts` that all exist | exit 3 — already shipped, nothing changed (LC-6) |
| All clear | the tracker moves to `active`; that move is the activation |

### Implementation

The `scripts/stage_plan.py` script owns both verbs. It relies on the standard library and takes an injectable resolver to mirror `resolve_plan.py`. It calls `resolve_plan.resolve` instead of deriving any path, and tells a task from a flat plan by the plan path agentm returns.

| Component | Location | Role |
|---|---|---|
| `staging_path()` | [`stage_plan.py:122`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/stage_plan.py#L122) | The task's own `plan.md`, from the path the resolver returns. Read-only; emits the path. A flat answer is refused. |
| `activate()` | [`stage_plan.py:134`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/stage_plan.py#L134) | Activates a queued task in place: plan present, tracker present and `queued`, then the tracker's move to `active`. |
| `_resolved()` | [`stage_plan.py:72`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/stage_plan.py#L72) | Resolves the plan and its tracker through the resolver. Refuses an empty/singleton name (exit 2, "staging requires a named plan") *before* the resolver is consulted. |
| `_not_a_task()` | [`stage_plan.py:116`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/stage_plan.py#L116) | The refusal for a flat answer: exit 2, nothing written. |
| CLI verbs `path` / `activate` | [`stage_plan.py:173`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/stage_plan.py#L173) (`_build_parser`) | Invoked as `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stage_plan.py" path <task>` and `... activate <task>`. Exit codes align with `resolve_plan.py`: `0` ok, `1` no agentm (passed on), `2` loud refusal, `3` already shipped (LC-6), and a resolver's `4` passed on. |

## Reading the queue — `/queue-status-lite`

The `/queue-status-lite` command serves as the read complement to the `--name` writers. It lists every active task of the project the cwd is bound to — each one's name, its status from its tracker, and the most recent line of its progress log. It takes no arguments. We define it as read-only by contract. It claims nothing, leases nothing, and gates nothing. This leaves you as the final arbiter of who works on which task. You can find the task recipe in [See every active plan](See-Every-Active-Plan).

| Property | Value |
|---|---|
| Command | `/queue-status-lite` |
| Argument | none — agentm resolves the project from the cwd |
| Listed | every task whose tracker is not `done` or `dropped` (in a repo with no vault, its repo-local plans) |
| Per-task output | name · tracker status · last progress line |
| Mutates | nothing — reads and prints only |
| Exit | `0` in normal use (a status read, never a gate) |

### Read bridge

| Property | Value |
|---|---|
| Script | `${CLAUDE_PLUGIN_ROOT}/scripts/queue_status.py` |
| Args | none |
| Output | agentm's `queue_status_lite.py` render, passed through verbatim |
| Without agentm | one line saying there is no plan list, exit 0 |

The bridge finds agentm's reader the way every agentm script is found (`$AGENTM_SCRIPTS_DIR`, co-located, then `~/Antigravity/agentm/scripts/`), runs it from the cwd, and re-emits its output. The reader owns which plans a project has, where they live, and their status. crickets enumerates nothing itself.

## Spawning a worker worktree

The auto-spawn step in the `/work` command gives a named plan its own isolated checkout. It uses the host's native worktree primitive to do this. For Claude Code, it uses the `EnterWorktree` tool. For Antigravity, it uses New-Worktree-Mode and `invoke_subagent`. We gate this step behind your authority. It does not run autonomously by default. It triggers only when `.harness/project.json` contains `isolation.mode: worktree-per-plan` or when you explicitly ask for a worktree. You do not need to run a separate spawn command. The `/work` command checks for isolation settings internally at step 1.5. You can read the task recipe in [Run a named plan](Run-A-Named-Plan).

| Property | Value |
|---|---|
| Trigger | `/work` (or `/bugfix`) step 1.5, when `isolation_config.should_auto_isolate()` returns true |
| Worktree creation | the host's native primitive — `EnterWorktree` (Claude Code) or New-Worktree-Mode / `invoke_subagent` (Antigravity) |
| Location | `.claude/worktrees/<name>` on a fresh branch named `worktree-<name>` |
| Plan binding | `worktree_marker.py` writes the plan name into the worktree's local `.harness/active-plan` marker, so `/work` inside the worktree resolves *its* named plan without re-passing `--name` — the one piece of the old `spawn_worker.py` with no host equivalent, since neither host has a concept of "plan" |
| Resume binding | `worktree_marker.py` also writes `.harness/worktree-for-<slug>` in the **original root**, holding the worktree's path. Both other writes are worktree-local, so without it a later session opened at the repo root has no way to learn which worktree the plan is bound to. Per-slug by name — more than one plan is routinely in flight, and a shared file would have them overwrite each other |
| `vault_project` | `worktree_marker.py` reproduces a divergent `vault_project` into the worktree as a fallback only (the LC-2 behavior `spawn_worker.py` used to carry) |
| Preflight | `worktree_marker.py` also carries the LC-6 "already shipped" preflight-reconcile guard |
| Guard | an in-worktree single-owner check (`is_inside_worktree()`) prevents nested spawns |

### Resuming a plan in its worktree

A plan that outlives one session resumes at step 1.5's *Re-enter* branch instead of its *Auto-spawn* branch. `worktree_marker.py read <slug> --project-root <root>` resolves the pointer above; `/work` re-enters the printed path through the host's own primitive (Claude Code: `EnterWorktree` with `path`, which accepts an existing worktree). You no longer have to tell a resumed session where its worktree is.

This is a re-entry, not a spawn. The pointer is only ever followed to a directory `git worktree list` already claims, so nothing here creates a worktree, and the authority that permitted the original spawn is what put the pointer there in the first place.

| Read result | What `/work` does |
|---|---|
| exit 0 | announces, then re-enters the printed worktree and runs the rest of the plan from inside it |
| exit 1 | proceeds in the current directory, printing the reason: singleton plan, no pointer recorded, a **stale** pointer (the worktree was removed by hand, is no longer registered, can't be verified, or now carries a different plan's marker), or already being inside the right worktree |
| exit 2 | a malformed slug — surfaces the error and still proceeds in the current directory |

> [!NOTE]
> Every state-of-the-world failure collapses to exit 1 on purpose. Re-entry is a convenience layer, so a pointer left behind by a worktree you deleted by hand degrades to a visible note and carries on — it can never become something that stops a plan. `worktree_marker.py clear <slug>` drops a pointer; `/work` runs it itself at close-out (step 12), and the note tells you the command when a stale one turns up.

> [!NOTE]
> **Operator authority, two forms.** Worker worktrees require your authority. You provide this through an explicit instruction to spawn one, or through a durable `isolation.mode: worktree-per-plan` configuration in `.harness/project.json`. We forbid silent, authority-free auto-spawning. The [Developer safety design](crickets-developer-safety) document explains both forms.

## Closing out a plan

When you reach the plan's **final** task, `/work` calls `finalize_unit.py`. It passes the actual branch that `EnterWorktree` returned. This replaces the old flow where you manually ran a local merge, a gate, and a hard reset. A PR protected by a required status check cannot merge if the checks fail. This removes the need for a separate post-merge rollback step.

| Property | Value |
|---|---|
| Trigger | the plan's final task, after its own CI has gone green |
| Push | `finalize_unit.py --branch <branch>` pushes the worktree's branch |
| PR | opens a PR via `gh pr create`, using the plan's close-out summary as the PR body |
| Auto-merge | `pr_helpers.finalize_pr` arms `gh pr merge --auto --squash` immediately after the PR opens — the merge itself happens once required checks (the `aggregate` status check) go green, with no further operator invocation |
| Worktree | `/work` runs `ExitWorktree keep` — never remove, since the branch still has an open PR against it |
| Repo setting | "Allow auto-merge" must be enabled once per repo (already on for `agentm` and `crickets`) |

### Orphan + stalled-PR shepherd

The `worktree_shepherd.py` sidecar runs periodically via `agentm-runner`. This scheduler replaces custom cron jobs. The shepherd performs two tasks that the read-only `doctor_worktrees.py` probe ignores. First, it reclaims orphaned worktrees and branches. It targets branches with no worktree, or worktrees with missing directories. It only removes resources that are a few days old and provably safe. A safe branch has all its commits on the remote copy, or it never diverged in the first place. It leaves everything else alone. Second, it handles open PRs that GitHub marks as `BEHIND` their base branch. This happens when a sibling plan merges first. The shepherd runs `gh pr update-branch` to rebase the PR. It records any merge conflict it encounters. It never swallows conflicts silently.

| Property | Value |
|---|---|
| Script | `worktree_shepherd.py` |
| Schedule | via `agentm-runner`, cadence: a few days |
| Reclaims | orphaned worktrees/branches, only when provably safe (fully merged into the branch's remote, or never diverged) |
| Rebases | a `BEHIND` open PR, via `gh pr update-branch` |
| On conflict | records it — never silently swallowed |

### Worktree doctor probe

You run the read-only `doctor_worktrees.py` script to list every `worktree-<slug>` worktree. The script classifies each worktree based on its plan mapping. It mutates nothing. You prune the worktrees on demand. The shepherd also prunes them when it determines they are safe to remove. The probe queries `git for-each-ref refs/heads/worktree-` and correlates the result with `git worktree list --porcelain`. This allows it to report lingering branches missing a worktree and worktrees missing a directory. It looks beyond the worktrees currently on disk.

| Property | Value |
|---|---|
| Script | `doctor_worktrees.py` (read-only); optional `--project-root <path>` (default: cwd) |
| Lists | every `worktree-<slug>` worktree, plus any lingering `worktree-<slug>` branch with no worktree |
| Classifies each | `active` · `merged-but-unpruned` · `orphaned` · `dangling-marker` (mutually exclusive, precedence-ordered) |
| Per-worktree | the worktree's plan mapping (the `.harness/active-plan` marker's bare slug) + status + a `→` detail line |
| Integration ref | the repo's current `HEAD` (normally `main`) |
| Mutates | nothing — every git call is a query (`list`, `for-each-ref`, `merge-base --is-ancestor`); the operator or the shepherd prunes on demand once they read the report |
| Exit | **always `0`** — a report, not a gate |

We define four states in precedence order:

| Status | Means | When |
|---|---|---|
| `orphaned` | a leftover ref / stale registration | the branch has no worktree at all (already pruned, or never checked out), **or** its registered worktree directory is gone (git lists it as prunable) — `git worktree prune` + `git branch -d` cleans it up |
| `dangling-marker` | the worktree cannot bind to a named plan | on disk, but no readable `.harness/active-plan` marker (missing or blank) |
| `merged-but-unpruned` | a prune candidate | on disk, marker present, and the branch is already an ancestor of the integration ref (an integration that did not prune, or work that landed by hand) |
| `active` | work in progress — leave it alone | on disk, marker present, branch **not** yet merged |

#### Implementation

| Component | Location | Role |
|---|---|---|
| `diagnose()` | [`doctor_worktrees.py:172`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/doctor_worktrees.py#L172) | Pure-core `diagnose(root, *, integration_ref="HEAD")`. Anchored on worker branches ([`_worker_branches`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/doctor_worktrees.py#L135)) correlated with the worktree list ([`_worktrees`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/doctor_worktrees.py#L100)), it classifies each into exactly one of the four states (precedence-ordered) and returns one `WorkerWorktree` ([`:73`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/doctor_worktrees.py#L73)) per branch. Reads the plan mapping via [`_read_marker`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/doctor_worktrees.py#L160) and the merged test via [`_is_merged`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/doctor_worktrees.py#L151). No mutation, no printing. |
| `_format()` | [`doctor_worktrees.py:219`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/doctor_worktrees.py#L219) | Renders the report: a header tally (counts per status) plus, per worktree, its branch · status · plan slug, the worktree path (or `(no worktree)`), and a `→` detail line. Pure — formats a list into a string. |
| `main()` | [`doctor_worktrees.py:247`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/doctor_worktrees.py#L247) | The CLI: parses `--project-root`, prints `_format(diagnose(root))`, and **returns `0` always** — a read-only diagnostic, never a gate. |

You can find executable tests in `scripts/test_doctor_worktrees.py` that lock this behavior.

## `/work` argument parse rule

The `--name <slug>` flag selects the plan. You can place it anywhere in the arguments. It cannot collide with the `step N` selector, a brief, a branch, or a commit range. Positional slots retain their meaning. For the `/work` command, that positional slot is the `step N` selector, and `task N` still works as the same selector. The flag and the selector remain completely independent.

| Argument | Parsed as |
|---|---|
| _(none)_ | the worktree's bound task, else agentm's answer for a bare call: a project that keeps tasks asks which task |
| `step N` or `task N` | the same plan, step N |
| `--name <slug>` | named plan `<slug>`, next unchecked step |
| `--name <slug> step N` | named plan `<slug>`, step N |

> [!NOTE]
> Slugs are slug-safe. The resolver rejects path traversal and unsafe names. It returns a non-zero exit code and prints no path on failure. If your plan uses a reserved positional word for its slug (like `task`), you can still reach it cleanly using `--name task`. The flag never competes with positional slots.

## Resolution

We do not reimplement plan resolution in `development-lifecycle`. The commands call a thin bridge script that asks agentm, which keeps the project's plans. With no agentm there is no plan.

| Concern | Owner |
|---|---|
| Precedence: explicit name → `.harness/active-plan` marker → bare call | agentm `resolve_active_plan` |
| Where a task lives, and its number when it is new | agentm |
| Slug-safety (reject traversal / unsafe names) | agentm `resolve_active_plan`; pre-checked by `stage_plan.py` and `worktree_marker.py` |
| Dangling-marker loud error (present-but-unresolvable `active-plan`) | agentm `resolve_active_plan`, propagated through the bridge |

> [!IMPORTANT]
> The commands **read** the `.harness/active-plan` marker via the resolver. They never write to it. The explicit `--name <slug>` flag provides the binding mechanism. If the resolver finds a present but unresolvable marker, it surfaces a **loud error and a non-zero exit code** up through the whole bridge. It never falls back silently to another plan. This prevents the common worker-to-plan mis-binding error.

### Resolver bridge

| Property | Value |
|---|---|
| Script | `${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py` |
| Args | optional positional `name`; `--project-root PATH` (default cwd) |
| Output | one line, tab-separated: `<plan_path>\t<progress_path>\t<tracker_path>`, the tracker field empty when agentm names none |
| Exit 1 | no agentm process seam was found (or the seam found no plan home): nothing on stdout, and stderr says so |
| Exit 2 | a dangling marker or an unsafe slug: nothing on stdout |
| Exit 4 | a bare call on a project that keeps tasks: nothing on stdout, and the command asks for a task name |
| Delegate target | agentm `process_seam.py state-path` (via `agentm_bridge.py`'s `process-seam` verb) |

The `--name <slug>` flag acts as a command-level convention. The `/work`, `/plan`, `/review` and `/release` commands parse the flag out of their arguments and pass the slug positionally to the bridge. The bridge locates agentm's process seam using the `process-seam` verb in `agentm_bridge.py`: `$AGENTM_SCRIPTS_DIR`, then a co-located path, then `~/Antigravity/agentm/scripts/`. It issues three calls to `process_seam.py state-path`, for the plan, progress and tracker paths, and reassembles them into one tab-separated line. A seam from before the tracker refuses the third call; the tracker field is then empty, and the exit stays 0.

## A repo with no vault

In a repo that isn't bound to a vault project, agentm keeps the repo's plans in its repo-local `.harness/`, and the commands follow its answers unchanged:

| Resolver input | agentm answers |
|---|---|
| bare (no slug) | `.harness/PLAN.md` + `.harness/progress.md` + `.harness/tracker.md` |
| `<slug>` | `.harness/PLAN-<slug>.md` + `.harness/progress-<slug>.md` + `.harness/tracker-<slug>.md` |

Such a plan can't be staged (staging needs the task layout), and it archives at close-out to `.harness/archive/PLAN.archive.YYYYMMDD-<slug>.md`, its tracker staying in `.harness/` at `done`. With no agentm at all there is no plan: the resolver exits 1, and the commands say so.

## Related

- [Author a design](Author-A-Design) — the task recipe for the upstream `/design` authoring step (`author` → `translate` → `sequence`).
- [Run a named plan](Run-A-Named-Plan) — the task recipe for driving `/work --name <slug>` and friends, including the auto-spawn + auto-close-out flow.
- [Development lifecycle design — worktree-native flow](crickets-development-lifecycle) — the decision behind host-native worktree creation and the PR-gated close-out replacing the old merge-then-gate-then-hard-reset model.
- [See every active plan](See-Every-Active-Plan) — the read-side recipe: `/queue-status-lite` for a one-glance view of the queue.
- [Development Lifecycle](Development-Lifecycle) — the phase-loop plugin these commands belong to.
- [Why phase-gating](Why-Phase-Gating) — why the loop is gated and state lives on disk.
- [Compatibility](Compatibility) — host support for the phase commands.
