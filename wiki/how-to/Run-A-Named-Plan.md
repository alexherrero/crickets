# How to run a named plan

> [!NOTE]
> **Goal:** Drive a `developer-workflows` phase (`/work`, `/plan`, `/review`) against a **named** plan pair — `PLAN-<slug>.md` + `progress-<slug>.md` — so several concurrent plans can share one harness state dir, instead of being limited to the singleton `PLAN.md` / `progress.md`.
> **Prereqs:** the `developer-workflows` plugin installed ([Install crickets plugins](Install-Into-Project)); a chosen, slug-safe plan name. Optional: a hosting memory layer (agentm) — when present, resolution is delegated to it; when absent, plans degrade to plain `.harness/PLAN-<slug>.md` + `.harness/progress-<slug>.md` (see [Named plans](Named-Plans)).

Use a named plan when you want more than one plan in flight at once — the wedge behind the coordinator-directed agent team. Bare `/work` / `/plan` / `/review` keep operating on the singleton, unchanged; adding `--name <slug>` is purely additive. For the full mapping of invocation → files, see [Named plans](Named-Plans).

## Prerequisites

- The `developer-workflows` plugin installed on your host ([Install crickets plugins](Install-Into-Project)).
- A slug-safe plan name (no path traversal; the resolver rejects unsafe names).
- _Optional:_ agentm installed as the hosting memory layer, for vault-backed state + the precedence chain. Without it, named plans live flat in `.harness/`.

## Steps

1. **Author the named plan.** Run `/plan --name <slug> <brief>` to write `PLAN-<slug>.md` (and seed its `progress-<slug>.md`). The `--name <slug>` flag selects the named pair; everything else in the arguments is the brief. Bare `/plan <brief>` (no `--name`) authors the singleton `PLAN.md`, unchanged.

2. **Work the named plan.** Run `/work --name <slug>` to work `PLAN-<slug>.md`'s task list, appending to `progress-<slug>.md`. The `--name <slug>` flag and the `task N` selector are independent — combine them (`/work --name <slug> task N`) to work a specific task of a named plan.

   `/work`'s "Read state" step resolves the pair by passing the slug positionally to `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" [<slug>]` (omit it for the singleton). A non-zero exit from the resolver is a **hard stop**: `/work` never falls back to the singleton on a dangling marker or unsafe slug. The task-mark (`[x]`) and the progress append at the end of the run both target the **resolved** pair, so `/work --name <slug>` writes `PLAN-<slug>.md` + `progress-<slug>.md` and bare `/work` stays byte-identical to the singleton.

3. **Review the named plan.** Run `/review --name <slug>` to run the adversarial pass against the named pair — it reads `PLAN-<slug>.md` for the task context and logs the outcome to `progress-<slug>.md`. Any remaining argument (a commit range, branch, or `task N`) still scopes *what* is reviewed, independent of `--name`. Bare `/review` (no `--name`) reviews against the singleton, unchanged.

4. **Confirm what a name resolves to** (when in doubt about which files a name maps to). The bridge takes the slug **positionally** — this is a direct call to the resolver, not a slash command, so there's no `--name` flag here:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" <slug>
   ```

   It prints one tab-separated line — `<plan_path>\t<progress_path>` — or exits non-zero with a stderr message on a dangling marker or unsafe slug (never a silent singleton fallback).

## Stage a plan, then activate it later

Use this flow when you want to author one or more named plans **ahead of time** without putting them in front of a worker — staged plans are inert (invisible to `/work` and `/queue-status-lite`) until you activate one. The active-tier `--name` flow above is unchanged.

### Steps

1. **Stage the plan.** Run `/plan --stage <slug> <brief>` to author the plan into the inactive staging tier. The rest of the arguments after `<slug>` is the brief, exactly as for `--name`. `/plan` writes the plan to the staging path that `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stage_plan.py" path <slug>` prints — `<harness>/queued-plans/PLAN-<slug>.md` — *instead of* the active path, and logs a `staged plan "<slug>"` line to the singleton `progress.md` (a staged plan has no run-scoped progress log until it is activated and first worked).

2. **Confirm it is inert.** A staged plan is **not** resolved by `/work --name <slug>` and **not** listed by `/queue-status-lite` until you activate it — staged means inactive by design. This needs no flag or marker: `/queue-status-lite` globs `PLAN-*.md` non-recursively at the harness root, so the `queued-plans/` subdir is skipped for free. Stage as many plans as you like; the queue glance stays empty until you promote one.

3. **Activate when a worker picks it up.** Run `/plan --activate <slug>` to promote the staged plan. Activation only promotes — it runs no interview and authors nothing new; it copies the staged plan into the active path that `/work` reads. Specifically, it copies `queued-plans/PLAN-<slug>.md` → the active `PLAN-<slug>.md` that `/work --name <slug>` reads (via `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stage_plan.py" activate <slug>`), reports the activated path, and appends an `activated plan "<slug>"` line to the singleton `progress.md`. The copy is **guarded** — it hard-stops (exit 2, writes nothing) if an active `PLAN-<slug>.md` already exists (would clobber) or the staged file is missing (nothing to promote). The staged copy is left in place (activation is a copy, not a move).

4. **Work it as a normal named plan.** Once activated, drive it with `/work --name <slug>` exactly as in the [Steps](#steps) above — activation is the only extra step.

## Troubleshooting

- **A bare `/work` picked up the wrong plan.** A present-but-unresolvable `.harness/active-plan` marker surfaces a loud error + non-zero exit rather than silently running the singleton. Resolve or remove the marker — never assume the singleton ran. See [Named plans § Resolution](Named-Plans#resolution).
- **The name was rejected.** Names are slug-safe; traversal or unsafe characters are refused. Pick a plain name.
- **`/plan --activate <slug>` refused.** Activation is guarded: it hard-stops (exit 2, writes nothing) if an active `PLAN-<slug>.md` already exists (would clobber) or the staged `queued-plans/PLAN-<slug>.md` is missing (nothing to promote). See [Named plans § `--activate` guard](Named-Plans#--activate-guard).

## Related

- [Named plans](Named-Plans) — the lookup: invocation → files, the parse rule, the resolver + standalone-fallback paths.
- Once a named plan is activated, running `/work` against it is enough to hand it to its own worktree — with `isolation.mode: worktree-per-plan` set in `.harness/project.json` (or an explicit operator instruction), `/work` auto-spawns the worktree via the host's own worktree primitive, binds it to the plan, and closes it out with an auto-merging pull request when the plan's final task lands. There's no separate spawn or integrate command to run. See [Named plans § Spawning a worker worktree](Named-Plans#spawning-a-worker-worktree) for the mechanism.
- [Developer Workflows](Developer-Workflows) — the phase-loop plugin these commands belong to.
- [Install crickets plugins](Install-Into-Project) — get `developer-workflows` onto your host.
- [Why phase-gating](Why-Phase-Gating) — why the loop is gated and state lives on disk.
