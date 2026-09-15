# How to run a named plan

> [!NOTE]
> **Goal:** Drive a `development-lifecycle` phase (`/plan`, `/work`, `/review`, `/release`) against a **named** plan — `PLAN-<slug>.md` + `progress-<slug>.md` and its tracker, or a numbered task once agentm keeps a project's plans in tasks — so several concurrent plans can share one project, instead of being limited to the singleton `PLAN.md` / `progress.md`.
> **Prereqs:** the `development-lifecycle` plugin installed ([Install crickets plugins](Install-Crickets-Plugins)); a chosen, slug-safe plan name. Optional: a hosting memory layer (agentm) — when present, resolution is delegated to it; when absent, plans degrade to plain `.harness/PLAN-<slug>.md` + `.harness/progress-<slug>.md` (see [Named plans](Named-Plans)).

Use a named plan when you want more than one plan in flight at once — the wedge behind the coordinator-directed agent team. Bare `/work` / `/plan` / `/review` keep operating on the singleton, unchanged; adding `--name <slug>` is purely additive. For the full mapping of invocation → files, see [Named plans](Named-Plans).

## Prerequisites

- The `development-lifecycle` plugin installed on your host ([Install crickets plugins](Install-Crickets-Plugins)).
- A slug-safe plan name (no path traversal; the resolver rejects unsafe names).
- _Optional:_ agentm installed as the hosting memory layer, for vault-backed state + the precedence chain. Without it, named plans live flat in `.harness/`.

## Steps

1. **Author the named plan.** Run `/plan --name <slug> <brief>` to write `PLAN-<slug>.md` (and seed its `progress-<slug>.md`). The `--name <slug>` flag selects the named pair; everything else in the arguments is the brief. Bare `/plan <brief>` (no `--name`) authors the singleton `PLAN.md`, unchanged. When agentm names a tracker for the plan, `/plan` also opens it at `queued`: `tracker-<slug>.md` beside the plan, or `tracker.md` in a task.

2. **Work the named plan.** Run `/work --name <slug>` to work `PLAN-<slug>.md`'s steps, appending to `progress-<slug>.md` and rewriting the tracker's State and Next after each step; the last step closes the tracker with its Outcome. The `--name <slug>` flag and the `step N` selector (`task N` still works) are independent — combine them (`/work --name <slug> step N`) to work a specific step of a named plan.

   `/work`'s "Read state" step resolves the pair by passing the slug positionally to `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" [<slug>]` (omit it for the singleton). A non-zero exit from the resolver is a **hard stop**: `/work` never falls back to the singleton on a dangling marker or unsafe slug. The step mark (`[x]`), the tracker write and the progress append all target the **resolved** paths, so `/work --name <slug>` writes `PLAN-<slug>.md` + `progress-<slug>.md` and bare `/work` stays byte-identical to the singleton.

3. **Review the named plan.** Run `/review --name <slug>` to run the adversarial pass against the named pair — it reads the plan's status and `PLAN-<slug>.md` for the step context, and logs the outcome and the status to `progress-<slug>.md`. With no other scope, a plan whose status is still `queued` has nothing to review yet, and `/review` says so. Any remaining argument (a commit range, branch, or `step N`) still scopes *what* is reviewed, independent of `--name`. Bare `/review` (no `--name`) reviews against the singleton, unchanged.

4. **Confirm what a name resolves to** (when in doubt about which files a name maps to). The bridge takes the slug **positionally** — this is a direct call to the resolver, not a slash command, so there's no `--name` flag here:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" <slug>
   ```

   It prints one tab-separated line — `<plan_path>\t<progress_path>\t<tracker_path>`, with an empty tracker field when agentm names none — or exits non-zero with a stderr message on a dangling marker or unsafe slug (never a silent singleton fallback). Exit 4 means the project keeps its plans in numbered tasks: pass the task's name.

## Stage a plan, then activate it later

Use this flow when you want to author one or more named plans **ahead of time** without putting them in front of a worker — staged plans are inert (invisible to `/work` and `/queue-status-lite`) until you activate one. The active-tier `--name` flow above is unchanged.

### Steps

1. **Stage the plan.** Run `/plan --stage <slug> <brief>` to author the plan into the inactive staging tier. The rest of the arguments after `<slug>` is the brief, exactly as for `--name`. `/plan` writes the plan to the staging path that `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stage_plan.py" path <slug>` prints — `<harness>/queued-plans/PLAN-<slug>.md` — *instead of* the active path, and logs a `staged plan "<slug>"` line to the singleton `progress.md` (a staged plan has no run-scoped progress log until it is activated and first worked). In a project that keeps tasks, the staging path is the task's own `plan.md`, and `/plan` opens its tracker at `queued`, which keeps it inert; a staged flat plan gets no tracker until it is worked.

2. **Confirm it is inert.** A staged plan is **not** resolved by `/work --name <slug>` and **not** listed by `/queue-status-lite` until you activate it — staged means inactive by design. This needs no flag or marker: `/queue-status-lite` globs `PLAN-*.md` non-recursively at the harness root, so the `queued-plans/` subdir is skipped for free. Stage as many plans as you like; the queue glance stays empty until you promote one.

3. **Activate when a worker picks it up.** Run `/plan --activate <slug>` to promote the staged plan. Activation only promotes — it runs no interview and authors nothing new; it copies the staged plan into the active path that `/work` reads. Specifically, it copies `queued-plans/PLAN-<slug>.md` → the active `PLAN-<slug>.md` that `/work --name <slug>` reads (via `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stage_plan.py" activate <slug>`), reports the activated path, and appends an `activated plan "<slug>"` line to the singleton `progress.md`. The copy is **guarded** — it hard-stops (exit 2, writes nothing) if an active `PLAN-<slug>.md` already exists (would clobber), the staged file is missing (nothing to promote), or a tracker already at the plan's tracker path isn't `queued`. The staged copy is left in place (activation is a copy, not a move), and a `queued` tracker moves to `active` after the copy. A task activates by that move alone.

4. **Work it as a normal named plan.** Once activated, drive it with `/work --name <slug>` exactly as in the [Steps](#steps) above — activation is the only extra step.

## Troubleshooting

- **A bare `/work` picked up the wrong plan.** A present-but-unresolvable `.harness/active-plan` marker surfaces a loud error + non-zero exit rather than silently running the singleton. Resolve or remove the marker — never assume the singleton ran. See [Named plans § Resolution](Named-Plans#resolution).
- **The name was rejected.** Names are slug-safe; traversal or unsafe characters are refused. Pick a plain name.
- **`/plan --activate <slug>` refused.** Activation is guarded: it hard-stops (exit 2, writes nothing) if an active `PLAN-<slug>.md` already exists (would clobber) or the staged `queued-plans/PLAN-<slug>.md` is missing (nothing to promote). See [Named plans § `--activate` guard](Named-Plans#--activate-guard).
- **A bare `/work` asks which task.** The project keeps its plans in numbered tasks, so there is no singleton: the resolver exits 4, and `/work` lists the project's tasks for you to pick. Pass `--name <task-name>`.
- **The tracker field is empty.** agentm named no tracker for the plan: you're running standalone, or on an agentm from before the tracker. The commands say so and run on the plan's `**Status:**` line.

## Related

- [Named plans](Named-Plans) — the lookup: invocation → files, the parse rule, the resolver + standalone-fallback paths.
- Once a named plan is activated, running `/work` against it is enough to hand it to its own worktree — with `isolation.mode: worktree-per-plan` set in `.harness/project.json` (or an explicit operator instruction), `/work` auto-spawns the worktree via the host's own worktree primitive, binds it to the plan, and closes it out with an auto-merging pull request when the plan's final task lands. There's no separate spawn or integrate command to run. See [Named plans § Spawning a worker worktree](Named-Plans#spawning-a-worker-worktree) for the mechanism.
- [Development Lifecycle](Development-Lifecycle) — the phase-loop plugin these commands belong to.
- [Install crickets plugins](Install-Crickets-Plugins) — get `development-lifecycle` onto your host.
- [Why phase-gating](Why-Phase-Gating) — why the loop is gated and state lives on disk.
