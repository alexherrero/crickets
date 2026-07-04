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
| `/spawn-worker <name>` | — (creates a worktree bound to the named plan) | — | operator-initiated worktree + `worker/<name>` branch ([Spawning a worker worktree](#spawning-a-worker-worktree)) |
| `/integrate-worker <name>` | — | `progress-<slug>.md` appended into `progress.md` | merges `worker/<slug>` → `main` only if the integrated tree passes the full gate, then prunes ([Integrating a worker](#integrating-a-worker)) |
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
| Command prompt | [`commands/design.md`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/design.md) — the three sub-verb flows (interactive, human-judgment) |
| Gate + storage helper | [`scripts/design_doc.py`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/design_doc.py) — `require_final()` the `Status: final` gate, `detailed_design_nonempty()`, frontmatter parser, harness-root / published-path resolution |
| Topo-sort helper | [`scripts/design_sequence.py`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/design_sequence.py) — Kahn topo-sort with alphabetical tie-break, part-frontmatter validation |

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
| `staging_path()` | [`stage_plan.py:86`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/stage_plan.py#L86) | Composes `queued-plans/` onto the active path the resolver returns → `<_harness>/queued-plans/PLAN-<slug>.md`. Read-only; emits the path. |
| `activate()` | [`stage_plan.py:100`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/stage_plan.py#L100) | The guarded copy. Refuses (exit 2, writes nothing) on missing staged file ([`:113`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/stage_plan.py#L113)) or active-plan collision ([`:122`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/stage_plan.py#L122), "refusing to clobber" — a path-occupancy guard, so a symlink or dangling symlink also counts as a collision and is refused). Copies bytes verbatim; leaves the staged file in place (copy, not move). |
| `_active_plan_path()` | [`stage_plan.py:69`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/stage_plan.py#L69) | Named-only guard — refuses an empty/singleton name (exit 2, "staging requires a named plan") at [`:78`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/stage_plan.py#L78) *before* the resolver is consulted. The singleton `PLAN.md` is the active default; there is nothing to stage for it. |
| `_QUEUED_DIR = "queued-plans"` | [`stage_plan.py:64`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/stage_plan.py#L64) | The flat staging-dir name (crickets flat-vault convention). |
| CLI verbs `path` / `activate` | [`stage_plan.py:148`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/stage_plan.py#L148) (`_build_parser`) | Invoked as `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stage_plan.py" path <slug>` and `... activate <slug>`. Exit codes align with `resolve_plan.py`: `0` ok, `1` graceful-skip propagated from the resolver, `2` loud refusal. |

The `--stage` / `--activate` modes are wired in [`commands/plan.md`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/plan.md). Staged plans stay invisible to `/queue-status-lite` because `queue_status._list_plan_files` globs `PLAN-*.md` non-recursively, so the `queued-plans/` subdir is skipped.

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

`/spawn-worker <name>` gives a named plan its own isolated checkout. It is operator-initiated — a normal session never spawns a worktree on its own. It fits the coordinator flow after a plan is staged and activated: `/plan --stage` → `/plan --activate` → `/spawn-worker` → launch a `/work` session in the new worktree. The task recipe is in [Spawn a worker in a worktree](Spawn-A-Worker-In-A-Worktree).

| Property | Value |
|---|---|
| Command | `/spawn-worker <name>` |
| Argument | `<name>` — the worker name; also the named plan slug it binds to |
| Worktree | a new `git worktree` on a fresh `worker/<name>` branch |
| Plan binding | writes the plan name into the worktree's local `.harness/active-plan` marker, so `/work` inside the worktree resolves *its* named plan without re-passing `--name` |
| `vault_project` | reproduces a divergent `vault_project` into the worktree as a fallback only |
| Guard | refuses (no-clobber) if the worktree path or the `worker/<name>` branch already exists, or the name is empty/singleton |
| Helper | wraps `scripts/spawn_worker.py` (inside the `developer-workflows` plugin), invoked as `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spawn_worker.py" <name>`; accepts `--project-root <path>` / `--worktree-path <path>`. Stdlib-only; mirrors `resolve_plan.py`'s pure-core + injectable-backend shape. Exit codes: `0` ok (worktree path on stdout), `1` graceful-skip (located resolver, no resolvable harness), `2` loud refusal (empty/singleton/unsafe name, no-clobber path/branch collision, resolver refusal, or failed `git worktree add` — never a partial spawn) |

> [!NOTE]
> **Operator authority, two forms.** Worker worktrees require operator authority — either an explicit `/spawn-worker` command (where the invocation is the authority) or a durable `isolation.mode: worktree-per-plan` config opt-in in `.harness/project.json` (where the config field is the authority). Silent authority-free auto-spawn stays forbidden. Both forms are decided in the [Developer safety design](crickets-developer-safety).
>
> With `isolation.mode: worktree-per-plan` set, `/work` and `/bugfix` auto-spawn a `worker/<slug>` worktree at step 1.5 (isolation check) and finalize it (push + open PR) at the plan's end via `finalize_unit.py`. The `isolation_config.should_auto_isolate()` check is the authority gate; `is_inside_worktree()` prevents nested spawns.

## Integrating a worker

`/integrate-worker <name>` is the coordinator-side counterpart to [`/spawn-worker`](#spawning-a-worker-worktree) — it lands a finished worker, closing the lifecycle: `/plan --stage` → `/plan --activate` → `/spawn-worker` → run `/work` in the worktree → `/integrate-worker`. It is operator-initiated and merge order is human-decided; it never auto-sequences merges. The gate runs on the integrated (post-merge) tree, not the worker branch in isolation, and a red gate hard-resets `main` so it is never left broken. The task recipe is in [Integrate a worker](Integrate-A-Worker).

| Property | Value |
|---|---|
| Command | `/integrate-worker <name>` |
| Argument | `<name>` — the worker name; also the named plan slug it was spawned on; optional `--project-root <path>` |
| Merge | `git merge --no-ff worker/<slug>` → `main` (preserves the worker's per-task commits + records an explicit integration point) |
| Gate | `scripts/check-all.sh` (the full 10-gate battery) run on the **post-merge / integrated** tree |
| On RED gate | hard-resets `main` back to the captured pre-merge HEAD; leaves the worktree intact for inspection; prints the gate output |
| On merge CONFLICT | `git merge --abort`; leaves the worktree intact |
| On GREEN | appends `progress-<slug>.md` into the singleton `progress.md` (additive — named file kept), then prunes: removes the worktree (worktree-first), then `git branch -d worker/<slug>` (safe — `--no-ff` recorded the merge) |
| Does **not** | push `main` (local merge only — push stays the operator's act); delete/archive the vault named plan/progress pair; auto-resolve conflicts; auto-sequence merges |
| Helper | wraps `scripts/integrate_worker.py` (inside the `developer-workflows` plugin), invoked as `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/integrate_worker.py" <name>`. Stdlib-only; mirrors `resolve_plan.py` / `spawn_worker.py`'s pure-core + injectable-backend shape |
| Exit codes | `0` integrated · `1` graceful-skip (located resolver, no resolvable `_harness/`) · `2` loud (guard refusal · conflict aborted · red gate rolled back) |

### Implementation

| Component | Location | Role |
|---|---|---|
| `integrate()` | [`integrate_worker.py:312`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/integrate_worker.py#L312) | Pure-core `integrate(name, root, *, gate, resolver)`. Runs every guard (resolve-first), the `--no-ff` merge, the gate on the merged tree, and on green the promote-then-prune — returns the exit code. |
| `git merge --no-ff` | [`integrate_worker.py:375`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/integrate_worker.py#L375) | The integration merge. Preserves the worker's per-task commits and records an explicit integration point; a conflict is `git merge --abort`-ed and a red gate hard-resets to the captured pre-merge HEAD. |
| `_promote()` | [`integrate_worker.py:236`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/integrate_worker.py#L236) | Green-path, additive: appends the worker's `progress-<slug>.md` plus a one-line integration record into the singleton `progress.md` (named file kept). Runs **before** prune. |
| `_prune()` / `_branch_safe_gone()` | [`integrate_worker.py:217`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/integrate_worker.py#L217), [`:196`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/integrate_worker.py#L196) | Green-path cleanup: removes the worktree (worktree-first), then safe-deletes the branch with `git branch -d` (not `-D` — `--no-ff` made it an ancestor of HEAD). A promote/prune failure is reported but never undoes the merge. |
| Command wiring | [`commands/integrate-worker.md`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/integrate-worker.md) | The operator-facing `/integrate-worker`. Wires the real gate (`bash scripts/check-all.sh` on the merged tree), surfaces helper output verbatim, never pushes. |

Executable tests in `scripts/test_integrate_worker.py` lock this behavior.

### Pre-mutation guards

All run before any merge — a refusal (exit 2) leaves `main` and the worktree untouched, so there is no partial integration to clean up. The command refuses when:

| Condition | Behavior |
|---|---|
| `<name>` empty or the singleton | refuse — `<name>` must be a real named-plan slug |
| `worker/<slug>` branch missing | refuse — nothing to integrate |
| worktree undiscoverable | refuse — cannot locate the worker's checkout |
| `main` working tree dirty | refuse — would entangle in-flight changes with the merge |
| plan/progress pair unresolvable | refuse — the resolver's refusal is authoritative and propagated verbatim |

### Orphaned-worktree doctor probe

A read-only `doctor_worktrees.py` (operator-run) lists every `worker/<slug>` worktree and classifies each with its plan mapping. It is the cleanup complement to `/integrate-worker` — zero mutation; the coordinator prunes on demand. The probe correlates worker branches (`git for-each-ref refs/heads/worker/`) with `git worktree list --porcelain`, so it reports both lingering branches with no worktree and worktrees whose directory is gone — not only the worktrees on disk.

| Property | Value |
|---|---|
| Script | `doctor_worktrees.py` (read-only); optional `--project-root <path>` (default: cwd) |
| Lists | every `worker/<slug>` worktree, plus any lingering `worker/<slug>` branch with no worktree |
| Classifies each | `active` · `merged-but-unpruned` · `orphaned` · `dangling-marker` (mutually exclusive, precedence-ordered) |
| Per-worktree | the worktree's plan mapping (the `.harness/active-plan` marker's bare slug) + status + a `→` detail line |
| Integration ref | the repo's current `HEAD` (normally `main`), matching `integrate_worker.py` |
| Mutates | nothing — every git call is a query (`list`, `for-each-ref`, `merge-base --is-ancestor`); the coordinator prunes on demand once they read the report |
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
| `diagnose()` | [`doctor_worktrees.py:164`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/doctor_worktrees.py#L164) | Pure-core `diagnose(root, *, integration_ref="HEAD")`. Anchored on worker branches ([`_worker_branches`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/doctor_worktrees.py#L132)) correlated with the worktree list ([`_worktrees`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/doctor_worktrees.py#L97)), it classifies each into exactly one of the four states (precedence-ordered) and returns one `WorkerWorktree` ([`:70`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/doctor_worktrees.py#L70)) per branch. Reads the plan mapping via [`_read_marker`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/doctor_worktrees.py#L152) and the merged test via [`_is_merged`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/doctor_worktrees.py#L143). No mutation, no printing. |
| `_format()` | [`doctor_worktrees.py:211`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/doctor_worktrees.py#L211) | Renders the report: a header tally (counts per status) plus, per worktree, its branch · status · plan slug, the worktree path (or `(no worktree)`), and a `→` detail line. Pure — formats a list into a string. |
| `main()` | [`doctor_worktrees.py:239`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/doctor_worktrees.py#L239) | The CLI: parses `--project-root`, prints `_format(diagnose(root))`, and **returns `0` always** — a read-only diagnostic, never a gate. |

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
| Delegate target | agentm `process_seam.py state-path` (via `find_process_seam.py`) when the seam is discoverable; else the standalone fallback |

The `--name <slug>` flag is a command-level convention: `/work`, `/plan`, and `/review` parse it out of their arguments and pass the extracted slug positionally to this bridge, whose own CLI takes the name as a positional argument, not a flag. The bridge discovers agentm's process seam via `find_process_seam.py` (path-fallback: `$AGENTM_SCRIPTS_DIR` → co-located → `~/Antigravity/agentm/scripts/`), issues two `process_seam.py state-path` calls (plan and progress), and reassembles the tab-separated output.

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
- [Run a named plan](Run-A-Named-Plan) — the task recipe for driving `/work --name <slug>` and friends.
- [Spawn a worker in a worktree](Spawn-A-Worker-In-A-Worktree) — the task recipe for `/spawn-worker`: hand an activated named plan to a worker in its own checkout.
- [Integrate a worker](Integrate-A-Worker) — the task recipe for `/integrate-worker`: land a finished worker's branch on `main` only if the integrated tree still passes the gate.
- [Development lifecycle design — gate the integrated tree](crickets-development-lifecycle) — the decision behind the gate-on-merged-tree + hard-reset-rollback rows in [Integrating a worker](#integrating-a-worker).
- [See every active plan](See-Every-Active-Plan) — the read-side recipe: `/queue-status-lite` for a one-glance view of the queue.
- [Developer Workflows](Developer-Workflows) — the phase-loop plugin these commands belong to.
- [Why phase-gating](Why-Phase-Gating) — why the loop is gated and state lives on disk.
- [Compatibility](Compatibility) — host support for the phase commands.
