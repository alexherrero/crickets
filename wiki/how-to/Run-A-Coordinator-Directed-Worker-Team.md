# How to run a coordinator-directed worker team

> [!NOTE]
> **Goal:** Run the full coordinator loop as one operator — take a brief through research, plan-authoring, isolated execution, integration, and a queue read — using the role roster as personas over the phase commands you already have. This is the capstone that ties the four V5-10 worker-team siblings together.
> **Prereqs:** the `developer-workflows` plugin installed ([Install crickets plugins](Install-Into-Project)) at 0.8.0 or later (the version that ships the role roster); a clean `main` working tree; a brief — the thing you want built. Read [Coordinator roles](Coordinator-Roles) first for what each role wraps and which are read-only.

You are the **coordinator**. The roster gives you four personas — `researcher`, `tech-lead`, `worker`, and `project-manager` — that are thin skins over the shipped phase commands ([Coordinator roles](Coordinator-Roles)). This page walks the whole loop once, in order, cross-linking the per-step recipes. Each role wraps a command you can also run bare; the roster just names the persona doing it.

## Steps

1. **Research the brief (`researcher`).** Front the loop with the read-only `researcher` role to scope the work before any plan exists. It wraps `explorer` for an in-repo fan-out ("where does X live / what tests cover Z") and runs its own `WebFetch` for a few targeted web lookups (a spec / API / changelog check). For deeper multi-source research it forward-references the operator's global research agent (e.g. a personally-installed `memory-idea-researcher`), composing with it when present and never vendoring or porting it — degrading gracefully to `explorer` + `WebFetch` when none is installed. Adopt the `researcher` persona (or paste its def from `src/developer-workflows/agents/researcher.md`) and ask your scoping question; it returns a structured finding — a 1–3 sentence answer, the `file:line` / web sources backing it, and the open questions a planner needs. The output is a scoped brief, not a plan; because the role is read-only it makes no edits.

2. **Author the plan (`tech-lead`).** Hand the scoped brief to the active `tech-lead` role — the brief-to-plan authoring persona (full tool access). Today its floor is `/plan` (`/design` is V5-10 sibling #5, a forward-reference — do not expect it yet). Author a named plan and stage it into the inactive tier, then promote it when you are ready to run it: `/plan --name <slug>` (or `--stage <slug>` to park it in `queued-plans/`, invisible to `/work` and `/queue-status-lite`), then `/plan --activate <slug>` to promote the staged plan to the active `PLAN-<slug>.md` (no-clobber guarded). Staging then activating lets you queue several plans and turn them on one at a time without singleton collisions. See [Run a named plan](Run-A-Named-Plan) for the full staging / activation surface.

3. **Spawn the worker's worktree.** Give the activated named plan its own checkout: run `/spawn-worker <name>`. This creates a `git worktree` on a fresh `worker/<name>` branch and drops the worktree-local `.harness/active-plan` marker that binds it. Worktrees are operator-initiated — this command is the sanctioned way to create one. Full recipe: [Spawn a worker in a worktree](Spawn-A-Worker-In-A-Worktree).

4. **Execute the plan (`worker`).** `cd` into the worktree the spawn step printed, then run `/work` bare — the worktree-local `.harness/active-plan` marker binds it to `PLAN-<name>.md`, no `--name` needed. The active `worker` role is the persona of this session: one per worktree, autonomous over its plan's **full** task list, single-threaded. Each task is gated by the per-task safety pre-check — it works straight through and only stops to ask on a hard-to-reverse, ambiguous, scope-drifting, or unverifiable task. It gates green before every `[x]`, commits one task per commit, and updates `PLAN-<name>.md` + `progress-<name>.md` as it goes. It never fans out parallel implementers — single-threaded execution is the load-bearing safety constraint. Several workers can run concurrently, each in its own worktree bound to its own plan, without colliding.

5. **Integrate the finished worker.** Back on `main` with a clean tree (not inside the worktree), run `/integrate-worker <name>`. It merges `worker/<name>` → `main`, runs the full deterministic battery on the **integrated** tree, and — only if green — promotes the worker's progress and prunes the worktree. A red gate hard-resets `main` back; it never pushes. Full recipe and the three outcomes: [Integrate a worker](Integrate-A-Worker).

6. **Read the queue (`project-manager`).** At any point, adopt the read-only `project-manager` role to see the whole queue at a glance: it wraps the `/queue-status-lite` read-model and surfaces — across every active plan — the active-plan binding(s) (singleton and/or named `PLAN-<slug>.md`), each plan's progress at a glance, and worker-worktree state (via the read-only `doctor_worktrees.py` probe). It shows that render verbatim: it marks nothing `[x]`, writes no progress, activates no plan, merges nothing. It is a glance, not a gate — per **LC-5**, merge order is human-decided, so picking what to `/work` or integrate next stays your call. Two refinements are forward-referenced (neither built here): **crickets #41** (github-projects board-sync — a synced board view) and **V5-11** (the chief-of-staff intelligence layer — `/standup`, readiness signals, integration-order *advisory*, still advisory). Full recipe: [See every active plan](See-Every-Active-Plan).

## Verify

- Each step's verify is the verify of the command it drives — see the per-step how-tos linked above.
- After step 2, `/plan --activate <slug>` leaves an active `PLAN-<slug>.md`; after step 3, the `worker/<name>` worktree exists with a `.harness/active-plan` marker holding the bare slug.
- The whole loop is complete when `/integrate-worker` reports GREEN for the plan you spawned (the full gate battery passing on the merged tree), and a fresh `project-manager` glance via `/queue-status-lite` shows the plan dropped from the active queue with its worktree pruned.

## Troubleshooting

- **`/work` can't find a plan inside the worktree.** The `.harness/active-plan` marker binds it — confirm you `cd`'d into the worktree the spawn step printed, not back on `main`. Run `/work` bare there; do not pass `--name`.
- **`/integrate-worker` reports RED.** The gate battery failed on the merged tree; integration hard-resets `main` to pre-merge HEAD and never pushes. Fix the failure in the worker's worktree, re-gate green there, then re-run `/integrate-worker <name>`. A merge conflict aborts instead of resetting — resolve in the worktree first.
- **`project-manager` shows a stale or orphaned plan.** The PM only reads; it never prunes. Use the `doctor_worktrees.py` probe / [See every active plan](See-Every-Active-Plan) to spot an orphaned worktree, then clean it up through the worker lifecycle — the PM will not do it for you.
- Per-command failure modes (spawn refusals, red-gate rollback, conflict handling) live on each step's how-to; this page only sequences them.

## Related

- [Coordinator roles](Coordinator-Roles) — the roster: what each role wraps, read-only vs active, tool allowlists, and the forward-references.
- [Run a named plan](Run-A-Named-Plan) — the write-side recipe behind step 2: authoring + staging + activating a named plan.
- [Spawn a worker in a worktree](Spawn-A-Worker-In-A-Worktree) — step 3: hand an activated plan to a worker in its own checkout.
- [Integrate a worker](Integrate-A-Worker) — step 5: land a finished worker's branch on `main`, gated on the integrated tree.
- [See every active plan](See-Every-Active-Plan) — step 6: the read-only glance over the plan queue.
- [Named plans](Named-Plans) — the command surface the whole loop rides.
