# Named plans

The `developer-workflows` phase commands `/work`, `/plan`, and `/review` accept an optional `--name <slug>` flag. With a name they operate on a named plan pair — `PLAN-<slug>.md` + `progress-<slug>.md` — instead of the singleton `PLAN.md` / `progress.md`. That is how one shared harness state dir holds several concurrent plans. Bare invocations resolve to the singleton.

Look up here what a name maps to, how the name is resolved, the standalone-fallback paths, and the read-only `/queue-status-lite` command. The task recipes are in [Run a named plan](Run-A-Named-Plan) and [See every active plan](See-Every-Active-Plan); the *why* is in [Why phase-gating](Why-Phase-Gating).

## ⚡ Quick Reference

| Invocation | Plan file read/written | Progress file appended | Notes |
|---|---|---|---|
| `/work` | `PLAN.md` | `progress.md` | singleton |
| `/work --name <slug>` | `PLAN-<slug>.md` | `progress-<slug>.md` | named pair |
| `/work task N` | `PLAN.md` | `progress.md` | singleton, task selector |
| `/work --name <slug> task N` | `PLAN-<slug>.md` | `progress-<slug>.md` | named pair + task selector |
| `/plan` | `PLAN.md` | `progress.md` | singleton |
| `/plan --name <slug>` | `PLAN-<slug>.md` (authored, **active**) | `progress-<slug>.md` | named pair, active tier |
| `/plan --stage <slug>` | `queued-plans/PLAN-<slug>.md` (authored, **staged/inert**) | — | staging tier ([Two-tier staging](#two-tier-named-plan-staging)) |
| `/plan --activate <slug>` | `queued-plans/PLAN-<slug>.md` → `PLAN-<slug>.md` (promoted) | — | promotes staged → active |
| `/review` | `PLAN.md` | — | singleton |
| `/review --name <slug>` | `PLAN-<slug>.md` | — | named pair |
| `/work` (auto-spawn, `isolation.mode: worktree-per-plan`) | — (host creates a worktree; `worktree_marker.py` binds it to the plan) | — | host-native worktree at `.claude/worktrees/<name>` on branch `worktree-<name>` ([Spawning a worker worktree](#spawning-a-worker-worktree)) |
| `/work` (final task, auto-close) | — | plan's close-out summary becomes the PR body | pushes the branch, opens a PR via `finalize_unit.py`, arms `gh pr merge --auto --squash` ([Closing out a plan](#closing-out-a-plan)) |
| `/design author [<slug>]` | the design doc (not a PLAN) | — | walks the 10-section template, drives `draft → review → final` ([The `/design` command](#the-design-command)) |
| `/design translate` | `<doc-dir>/parts/<part-slug>.md` (writes parts, reads the doc) | — | gates on `Status: final`, splits the doc into structural parts |
| `/design sequence` | `PLAN-<doc-slug>-<part-slug>.md` (active) + `queued-plans/PLAN-<doc-slug>-<part-slug>.md` (staged) | — | one named plan per part via `stage_plan.py`; never touches the singleton `PLAN.md` |

> [!NOTE]
> Paths above are shown by basename. The actual directory is whatever the resolver returns — `.harness/` in standalone mode, or a hosting memory layer's state dir when one is present (see [Resolution](#resolution)).

## Commands that accept a name

| Command | Argument | Effect with a name |
|---|---|---|
| `/work` | optional `--name <slug>` (anywhere in args) | reads the named PLAN, appends the scoped progress, marks `[x]` in the named PLAN |
| `/plan` | optional `--name <slug>` (anywhere in args) | authors `PLAN-<slug>.md`, appends the scoped `progress-<slug>.md` line |
| `/review` | optional `--name <slug>` (anywhere in args) | resolves + reads the named pair for adversarial critique |

`/setup`, `/release`, and `/bugfix` do not take a plan name — they are singleton-only.

## The `/design` command

`/design` is the upstream authoring step of the phase loop — it starts earlier than `/plan`. Use it when the problem is ambiguous, multi-stakeholder, or has cross-cutting Quality-Attributes / Operations concerns; use `/plan` for an already-settled design. The task recipe is in [Author a design](Author-A-Design); the reasoning is in the [Development lifecycle design](crickets-development-lifecycle).

| Surface | Location |
|---|---|
| Command prompt | [`commands/design.md`](https://github.com/alexherrero/crickets/blob/main/src/design/commands/design.md) — the three sub-verb flows (interactive, human-judgment) |
| Gate + storage helper | [`scripts/design_doc.py`](https://github.com/alexherrero/crickets/blob/main/src/design/scripts/design_doc.py) — `require_final()` the `Status: final` gate, `detailed_design_nonempty()`, frontmatter parser, harness-root / published-path resolution |
| Topo-sort helper | [`scripts/design_sequence.py`](https://github.com/alexherrero/crickets/blob/main/src/design/scripts/design_sequence.py) — Kahn topo-sort with alphabetical tie-break, part-frontmatter validation |

| Sub-verb | Reads | Writes | Gate (helper) |
|---|---|---|---|
| `/design author [<slug>]` | the design doc (on re-invoke) | the design doc | refuses re-invocation once `Status: final`; only `author` transitions Status |
| `/design translate` | a `Status: final` design doc | `<doc-dir>/parts/<part-slug>.md` | `design_doc.py gate` (`Status: final`) **and** `design_doc.py detailed-design` (non-empty `### Detailed Design`); both exit 2 + reason on failure |
| `/design sequence` | the populated `<doc-dir>/parts/` | one named plan per part (see below) | `design_doc.py gate` + non-empty validated `parts/`; ordering via `design_sequence.py order` (exit 2 on cycle / missing-dep) |

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
| Input | the populated `<doc-dir>/parts/` |
| Ordering | topo-sort, deterministic; alphabetical tie-break |
| Writer | `stage_plan.py` — `/design` does not re-derive harness paths |
| First part | **activated** as `PLAN-<doc-slug>-<part-slug>.md` |
| Remaining parts | **staged** into `queued-plans/PLAN-<doc-slug>-<part-slug>.md` |
| Singleton `PLAN.md` | **never touched** |

### Storage

| Visibility | Design doc home |
|---|---|
| `confidential` | `<resolved-harness>/designs/<slug>.md` — harness root resolved via `design_doc.py harness-root` (composes onto the `resolve_plan.py` resolver; storage-agnostic); not committed |
| `published` | `wiki/designs/<slug>.md` — committed (the crickets path, **not** agentm's `wiki/explanation/designs/`) |

## Two-tier named-plan staging

Alongside writing the active named plan directly (`--name`), `/plan` can stage a plan into an inactive tier and activate it later when a worker picks it up. Staged plans are inert — invisible to `/work` and `/queue-status-lite` until activated.

### The four `/plan` modes

| Mode | Writes | Tier | Seen by `/work` & `/queue-status-lite`? |
|---|---|---|---|
| `/plan <brief>` | `PLAN.md` | singleton | yes |
| `/plan --name <slug> <brief>` | `PLAN-<slug>.md` | active | yes |
| `/plan --stage <slug> <brief>` | `queued-plans/PLAN-<slug>.md` | **staging (inert)** | **no** — until activated |
| `/plan --activate <slug>` | promotes `queued-plans/PLAN-<slug>.md` → `PLAN-<slug>.md` | staging → active | yes, after promotion |

### Staging tier

| Property | Value |
|---|---|
| Staging dir | `<harness>/queued-plans/` — **flat** (crickets flat-vault convention) |
| Staged plan file | `queued-plans/PLAN-<slug>.md` |
| Visibility | inert — not resolved by `/work --name`, not listed by `/queue-status-lite`, until activated |
| Active path it activates into | `<harness>/PLAN-<slug>.md` (the path `/work --name <slug>` reads) |
| Harness dir | whatever the resolver returns — vault-backed `_harness/` when a memory layer is present, `.harness/` standalone (see [Resolution](#resolution)) |

### `--activate` guard

`/plan --activate <slug>` is a **guarded copy** — it hard-stops (non-zero exit, no silent fallback) when promotion would be unsafe:

| Condition | Behavior |
|---|---|
| Active `PLAN-<slug>.md` already exists | refuse — would clobber an active plan |
| Staged `queued-plans/PLAN-<slug>.md` missing | refuse — nothing to promote |
| Both clear | copy `queued-plans/PLAN-<slug>.md` → `PLAN-<slug>.md` |

### Implementation

`scripts/stage_plan.py` (stdlib-only, pure-core + injectable resolver, mirroring `resolve_plan.py`) owns both verbs. It composes onto `resolve_plan.resolve` rather than re-deriving the `_harness/` location or the vault redirect: it takes the resolved active `PLAN-<slug>.md` and composes `queued-plans/` onto its parent.

| Component | Location | Role |
|---|---|---|
| `staging_path()` | [`stage_plan.py:94`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/stage_plan.py#L94) | Composes `queued-plans/` onto the active path the resolver returns → `<_harness>/queued-plans/PLAN-<slug>.md`. Read-only; emits the path. |
| `activate()` | [`stage_plan.py:108`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/stage_plan.py#L108) | The guarded copy. Refuses (exit 2, writes nothing) on missing staged file ([`:128`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/stage_plan.py#L128)) or active-plan collision ([`:141`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/stage_plan.py#L141), "refusing to clobber" — a path-occupancy guard, so a symlink or dangling symlink also counts as a collision and is refused). Copies bytes verbatim; leaves the staged file in place (copy, not move). |
| `_active_plan_path()` | [`stage_plan.py:77`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/stage_plan.py#L77) | Named-only guard — refuses an empty/singleton name (exit 2, "staging requires a named plan") at [`:86`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/stage_plan.py#L86) *before* the resolver is consulted. The singleton `PLAN.md` is the active default; there is nothing to stage for it. |
| `_QUEUED_DIR = "queued-plans"` | [`stage_plan.py:72`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/stage_plan.py#L72) | The flat staging-dir name (crickets flat-vault convention). |
| CLI verbs `path` / `activate` | [`stage_plan.py:176`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/stage_plan.py#L176) (`_build_parser`) | Invoked as `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stage_plan.py" path <slug>` and `... activate <slug>`. Exit codes align with `resolve_plan.py`: `0` ok, `1` graceful-skip propagated from the resolver, `2` loud refusal. |

The `--stage` / `--activate` modes are wired in [`commands/plan.md`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/plan.md). Staged plans stay invisible to `/queue-status-lite` because `queue_status._list_plan_files` globs `PLAN-*.md` non-recursively, so the `queued-plans/` subdir is skipped.

Executable tests in `scripts/test_stage_plan.py` lock this behavior.

## Reading the queue — `/queue-status-lite`

`/queue-status-lite` is the read complement to the `--name` writers above — it lists every active plan in the harness dir, showing each plan's name, its `Status:` line, and the most-recent entry of the matching `progress*.md`. It takes no `--name` flag because it enumerates the whole queue, not one pair. It is read-only by contract: it claims nothing, leases nothing, and gates nothing, so the human stays the arbiter of who works which plan. The task recipe is in [See every active plan](See-Every-Active-Plan).

| Property | Value |
|---|---|
| Command | `/queue-status-lite` |
| Argument | optional `--harness-dir <path>` (default: resolve from cwd) |
| Active plans listed | `PLAN.md` plus every `PLAN-<slug>.md` (archives + GDrive conflict copies skipped) |
| Per-plan output | name · `Status:` line · last `progress*.md` line |
| Mutates | nothing — reads and prints only |
| Exit | `0` in normal use (a status read, never a gate) — `0` even when there is no harness dir to read |

### Read bridge

`/queue-status-lite` calls a bridge script that mirrors the resolver bridge's **two backends, one contract** shape (see [Resolution](#resolution) above):

| Property | Value |
|---|---|
| Script | `${CLAUDE_PLUGIN_ROOT}/scripts/queue_status.py` |
| Args | optional `--harness-dir PATH` (default: resolve from cwd) |
| Output | a deterministic, human-scannable dashboard block on stdout |
| Delegate target | agentm's shipped `queue_status_lite.py` reader when an agentm clone is locatable |
| Standalone fallback | a minimal local `.harness/` dashboard mirroring the reader's format |

When an agentm clone is installed the bridge delegates to agentm's `queue_status_lite.py` and re-emits its stdout verbatim (that reader owns the naming contract, GDrive-conflict skipping, and vault redirection). With no clone the bridge renders the minimal local dashboard itself — a graceful-skip, never an error. The agentm-clone lookup and the PLAN→progress naming helpers come from the resolver bridge (`resolve_plan.py`).

## Spawning a worker worktree

`/work`'s auto-spawn step gives a named plan its own isolated checkout using the host's own worktree primitive — Claude Code's `EnterWorktree` tool, or Antigravity's New-Worktree-Mode / `invoke_subagent`. It is authority-gated, not autonomous by default: it fires only when `.harness/project.json` sets `isolation.mode: worktree-per-plan` (a durable operator config opt-in) or the operator explicitly asks for a worktree. There is no separate spawn command to run — the isolation check happens inside `/work` itself, at step 1.5. The task recipe is in [Run a named plan](Run-A-Named-Plan).

| Property | Value |
|---|---|
| Trigger | `/work` (or `/bugfix`) step 1.5, when `isolation_config.should_auto_isolate()` returns true |
| Worktree creation | the host's native primitive — `EnterWorktree` (Claude Code) or New-Worktree-Mode / `invoke_subagent` (Antigravity) |
| Location | `.claude/worktrees/<name>` on a fresh branch named `worktree-<name>` |
| Plan binding | `worktree_marker.py` writes the plan name into the worktree's local `.harness/active-plan` marker, so `/work` inside the worktree resolves *its* named plan without re-passing `--name` — the one piece of the old `spawn_worker.py` with no host equivalent, since neither host has a concept of "plan" |
| `vault_project` | `worktree_marker.py` reproduces a divergent `vault_project` into the worktree as a fallback only (the LC-2 behavior `spawn_worker.py` used to carry) |
| Preflight | `worktree_marker.py` also carries the LC-6 "already shipped" preflight-reconcile guard |
| Guard | an in-worktree single-owner check (`is_inside_worktree()`) prevents nested spawns |

> [!NOTE]
> **Operator authority, two forms.** Worker worktrees require operator authority — either an explicit operator instruction to spawn one, or a durable `isolation.mode: worktree-per-plan` config opt-in in `.harness/project.json`. Silent authority-free auto-spawn stays forbidden. Both forms are decided in the [Developer safety design](crickets-developer-safety).

## Closing out a plan

On the plan's **final** task, `/work` calls `finalize_unit.py` with the real branch `EnterWorktree` returned. This is the entire replacement for the old manual local-merge-then-gate-then-hard-reset flow — a PR gated by a required status check structurally cannot merge red, so there's no separate post-merge rollback step to run.

| Property | Value |
|---|---|
| Trigger | the plan's final task, after its own CI has gone green |
| Push | `finalize_unit.py --branch <branch>` pushes the worktree's branch |
| PR | opens a PR via `gh pr create`, using the plan's close-out summary as the PR body |
| Auto-merge | `pr_helpers.finalize_pr` arms `gh pr merge --auto --squash` immediately after the PR opens — the merge itself happens once required checks (the `aggregate` status check) go green, with no further operator invocation |
| Worktree | `/work` runs `ExitWorktree keep` — never remove, since the branch still has an open PR against it |
| Repo setting | "Allow auto-merge" must be enabled once per repo (already on for `agentm` and `crickets`) |

### Orphan + stalled-PR shepherd

A periodic sidecar, `worktree_shepherd.py`, runs via `agentm-runner` (a scheduler, not a bespoke cron) and does two things the read-only `doctor_worktrees.py` probe never did on its own: it reclaims worktrees/branches that are orphaned (branch has no worktree, or the worktree's directory is gone), old enough (a few days), and provably safe (every commit already on the branch's remote copy, or the branch never diverged at all — anything not provably safe is left alone); and for an open PR GitHub reports as `BEHIND` its base branch (a sibling plan's PR merged first), it runs `gh pr update-branch` to rebase it, recording any resulting merge conflict rather than swallowing it.

| Property | Value |
|---|---|
| Script | `worktree_shepherd.py` |
| Schedule | via `agentm-runner`, cadence: a few days |
| Reclaims | orphaned worktrees/branches, only when provably safe (fully merged into the branch's remote, or never diverged) |
| Rebases | a `BEHIND` open PR, via `gh pr update-branch` |
| On conflict | records it — never silently swallowed |

### Worktree doctor probe

A read-only `doctor_worktrees.py` (operator-run) lists every `worktree-<slug>` worktree and classifies each with its plan mapping. It mutates nothing — the operator (or the shepherd, when provably safe) prunes on demand. The probe correlates worktree branches (`git for-each-ref refs/heads/worktree-`) with `git worktree list --porcelain`, so it reports both lingering branches with no worktree and worktrees whose directory is gone — not only the worktrees on disk.

| Property | Value |
|---|---|
| Script | `doctor_worktrees.py` (read-only); optional `--project-root <path>` (default: cwd) |
| Lists | every `worktree-<slug>` worktree, plus any lingering `worktree-<slug>` branch with no worktree |
| Classifies each | `active` · `merged-but-unpruned` · `orphaned` · `dangling-marker` (mutually exclusive, precedence-ordered) |
| Per-worktree | the worktree's plan mapping (the `.harness/active-plan` marker's bare slug) + status + a `→` detail line |
| Integration ref | the repo's current `HEAD` (normally `main`) |
| Mutates | nothing — every git call is a query (`list`, `for-each-ref`, `merge-base --is-ancestor`); the operator or the shepherd prunes on demand once they read the report |
| Exit | **always `0`** — a report, not a gate |

The four states, in precedence order:

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

Executable tests in `scripts/test_doctor_worktrees.py` lock this behavior.

## `/work` argument parse rule

The `--name <slug>` flag selects the plan; it can appear anywhere in the arguments and **cannot collide** with the `task N` selector, a brief, a branch, or a commit range. Positional slots keep their meaning — for `/work` that's the `task N` selector. The two are independent:

| Argument | Parsed as |
|---|---|
| _(none)_ | singleton, next unchecked task |
| `task N` | singleton, task N |
| `--name <slug>` | named plan `<slug>`, next unchecked task |
| `--name <slug> task N` | named plan `<slug>`, task N |

> [!NOTE]
> Slugs are slug-safe — the resolver rejects path traversal and unsafe names (non-zero exit, no path printed). A plan whose slug is a reserved positional word (e.g. `task`) is still reachable unambiguously via `--name task`, because the flag never competes with positional slots.

## Resolution

Named-plan resolution is **not** reimplemented in `developer-workflows`. The commands call a thin bridge script that delegates to the hosting memory layer (agentm) when present, and falls back to plain files otherwise.

| Concern | Owner |
|---|---|
| Precedence: explicit name → `.harness/active-plan` marker → singleton | agentm `resolve_active_plan` |
| Slug-safety (reject traversal / unsafe names) | agentm `resolve_active_plan`; mirrored in the standalone fallback |
| Dangling-marker loud error (present-but-unresolvable `active-plan`) | agentm `resolve_active_plan`, propagated through the bridge |
| Standalone fallback to plain `.harness/` | the `developer-workflows` bridge |

> [!IMPORTANT]
> The commands **read** the `.harness/active-plan` marker (via the resolver) but write none. The explicit `--name <slug>` flag is the binding mechanism. A present-but-unresolvable marker surfaces a **loud error + non-zero exit** through the whole bridge — it never silently falls back to whatever `PLAN.md` happens to be there (the worker→plan mis-binding foot-gun).

### Resolver bridge

| Property | Value |
|---|---|
| Script | `${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py` |
| Args | optional positional `name`; `--project-root PATH` (default cwd) |
| Output | one line, tab-separated: `<plan_path>\t<progress_path>` |
| On dangling marker / unsafe slug | non-zero exit + stderr message (never a singleton fallback) |
| Delegate target | agentm `process_seam.py state-path` (via `agentm_bridge.py`'s `process-seam` verb) when the seam is discoverable; else the standalone fallback |

The `--name <slug>` flag is a command-level convention: `/work`, `/plan`, and `/review` parse it out of their arguments and pass the extracted slug positionally to this bridge, whose own CLI takes the name as a positional argument, not a flag. The bridge discovers agentm's process seam via `agentm_bridge.py`'s `process-seam` verb (path-fallback: `$AGENTM_SCRIPTS_DIR` → co-located → `~/Antigravity/agentm/scripts/`), issues two `process_seam.py state-path` calls (plan and progress), and reassembles the tab-separated output.

## Standalone fallback (no agentm installed)

When no hosting memory layer is locatable, the bridge degrades to plain `.harness/` files — flat, no vault redirect, no marker, no CAS:

| Resolver input (positional) | Resolves to |
|---|---|
| bare (no slug) | `.harness/PLAN.md` + `.harness/progress.md` |
| `<slug>` | `.harness/PLAN-<slug>.md` + `.harness/progress-<slug>.md` |
| unsafe slug | rejected locally — non-zero exit, no path printed |

The bare paths are byte-identical to the singleton literals, locked by an executable test.

## Related

- [Author a design](Author-A-Design) — the task recipe for the upstream `/design` authoring step (`author` → `translate` → `sequence`).
- [Run a named plan](Run-A-Named-Plan) — the task recipe for driving `/work --name <slug>` and friends, including the auto-spawn + auto-close-out flow.
- [Development lifecycle design — worktree-native flow](crickets-development-lifecycle) — the decision behind host-native worktree creation and the PR-gated close-out replacing the old merge-then-gate-then-hard-reset model.
- [See every active plan](See-Every-Active-Plan) — the read-side recipe: `/queue-status-lite` for a one-glance view of the queue.
- [Developer Workflows](Developer-Workflows) — the phase-loop plugin these commands belong to.
- [Why phase-gating](Why-Phase-Gating) — why the loop is gated and state lives on disk.
- [Compatibility](Compatibility) — host support for the phase commands.
