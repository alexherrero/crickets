# How to run a named plan

> [!NOTE]
> **Goal:** Drive a `development-lifecycle` phase (`/plan`, `/work`, `/review`, `/release`) against a **named** plan — a numbered task, `tasks/NNN-<verb-slug>/` with its `plan.md`, `progress.md` and `tracker.md` — so several concurrent plans can share one project.
> **Prereqs:** the `development-lifecycle` plugin installed ([Install crickets plugins](Install-Crickets-Plugins)); agentm installed, since development-lifecycle keeps its plans through it; a chosen, slug-safe plan name.

Use a named plan when you want more than one plan in flight at once — the wedge behind the coordinator-directed agent team. In a project that keeps tasks, a bare `/work` / `/review` asks which task, and a bare `/plan` proposes a name. For the full mapping of invocation → files, see [Named plans](Named-Plans).

## Prerequisites

- The `development-lifecycle` plugin installed on your host ([Install crickets plugins](Install-Crickets-Plugins)).
- agentm installed. It decides where a project's tasks live and numbers a new one; crickets composes no path itself. Without agentm there is no plan, and the commands say so.
- A slug-safe plan name (no path traversal; the resolver rejects unsafe names).

## Steps

1. **Author the named plan.** Run `/plan --name <slug> <brief>`. agentm places a new numbered task, `tasks/NNN-<slug>/`, and `/plan` writes its `plan.md`, seeds its `progress.md`, and opens its `tracker.md` at `queued`. The `--name <slug>` flag selects the task; everything else in the arguments is the brief.

2. **Work the named plan.** Run `/work --name <slug>` to work the task's steps, appending to its `progress.md` and rewriting the tracker's State and Next after each step; the last step closes the tracker with its Outcome. The `--name <slug>` flag and the `step N` selector (`task N` still works) are independent — combine them (`/work --name <slug> step N`) to work a specific step.

   `/work`'s "Read state" step resolves the paths by passing the slug positionally to `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" [<slug>]`. A non-zero exit from the resolver is a **hard stop**: `/work` never falls back to another plan on a dangling marker or unsafe slug. The step mark (`[x]`), the tracker write and the progress append all target the **resolved** paths.

3. **Review the named plan.** Run `/review --name <slug>` to run the adversarial pass against the task — it reads the plan's status and `plan.md` for the step context, and logs the outcome and the status to the task's `progress.md`. With no other scope, a plan whose status is still `queued` has nothing to review yet, and `/review` says so. Any remaining argument (a commit range, branch, or `step N`) still scopes *what* is reviewed, independent of `--name`.

4. **Confirm what a name resolves to** (when in doubt about which files a name maps to). The bridge takes the slug **positionally** — this is a direct call to the resolver, not a slash command, so there's no `--name` flag here:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" <slug>
   ```

   It prints one tab-separated line — `<plan_path>\t<progress_path>\t<tracker_path>`, with an empty tracker field when agentm names none — or exits non-zero with a stderr message: 1 for no agentm, 2 for a dangling marker or unsafe slug, 4 for a bare call in a project that keeps tasks.

## Stage a plan, then activate it later

Use this flow when you want to author one or more tasks **ahead of time** without putting them in front of a worker. A queued task is inert until you activate it; its `queued` tracker is what keeps it so.

### Steps

1. **Stage the plan.** Run `/plan --stage <slug> <brief>`. The rest of the arguments after `<slug>` is the brief, exactly as for `--name`. `/plan` writes the task's own `plan.md` at the path `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stage_plan.py" path <slug>` prints, and opens its tracker at `queued`.

2. **Activate when a worker picks it up.** Run `/plan --activate <slug>`. Activation runs no interview and authors nothing new: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stage_plan.py" activate <slug>` moves the task's tracker from `queued` to `active`, and that move is the activation. It hard-stops (exit 2, writes nothing) if the task's `plan.md` or tracker is missing, or the tracker isn't `queued`.

3. **Work it as a normal named plan.** Once activated, drive it with `/work --name <slug>` exactly as in the [Steps](#steps) above.

Only a task stages. In a repo with no vault, agentm keeps the repo's plans in its repo-local `.harness/` (see [Named plans § A repo with no vault](Named-Plans#a-repo-with-no-vault)); staging refuses there, and you write the plan with `--name`.

## Troubleshooting

- **A bare `/work` picked up the wrong plan.** A present-but-unresolvable `.harness/active-plan` marker surfaces a loud error + non-zero exit rather than silently running another plan. Resolve or remove the marker. See [Named plans § Resolution](Named-Plans#resolution).
- **The name was rejected.** Names are slug-safe; traversal or unsafe characters are refused. Pick a plain name.
- **`/plan --activate <slug>` refused.** Activation is guarded: the task's `plan.md` or tracker is missing, its tracker isn't `queued`, or agentm answered a repo-local flat plan, which doesn't stage. See [Named plans § `--activate` guard](Named-Plans#--activate-guard).
- **A bare `/work` asks which task.** The project keeps its plans in numbered tasks, so the resolver exits 4 and `/work` lists the project's tasks for you to pick. Pass `--name <task-name>`.
- **The commands say there is no plan.** No agentm process seam was found: the resolver exits 1. Install agentm, or point `$AGENTM_SCRIPTS_DIR` at its `scripts/`.
- **The tracker field is empty.** agentm named no tracker for the plan, which an agentm from before the tracker does. The commands say so and run on the plan's `**Status:**` line.

## Related

- [Named plans](Named-Plans) — the lookup: invocation → files, the parse rule, the resolver, and a repo with no vault.
- Once a task is active, running `/work` against it is enough to hand it to its own worktree — with `isolation.mode: worktree-per-plan` set in `.harness/project.json` (or an explicit operator instruction), `/work` auto-spawns the worktree via the host's own worktree primitive, binds it to the plan, and closes it out with an auto-merging pull request when the plan's final step lands. There's no separate spawn or integrate command to run. See [Named plans § Spawning a worker worktree](Named-Plans#spawning-a-worker-worktree) for the mechanism.
- [Development Lifecycle](Development-Lifecycle) — the phase-loop plugin these commands belong to.
- [Install crickets plugins](Install-Crickets-Plugins) — get `development-lifecycle` onto your host.
- [Why phase-gating](Why-Phase-Gating) — why the loop is gated and state lives on disk.
