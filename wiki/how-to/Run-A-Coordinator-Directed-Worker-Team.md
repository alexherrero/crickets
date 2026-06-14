# How to run a coordinator-directed worker team

> [!NOTE]
> **Goal:** Run the full coordinator loop as one operator — take a brief through research, plan-authoring, isolated execution, integration, and a queue read — using the role roster as personas over the phase commands you already have. This is the capstone that ties the four V5-10 worker-team siblings together.
> **Prereqs:** the `developer-workflows` plugin installed ([Install crickets plugins](Install-Into-Project)) at the version that ships the role roster; a clean `main` working tree; a brief — the thing you want built. Read [Coordinator roles](Coordinator-Roles) first for what each role wraps and which are read-only.

> [!IMPORTANT]
> **Status: pending.** The roles this playbook names (`researcher`, `tech-lead`, `worker`, `project-manager`, and the `deep-researcher` agent) are planned — V5-10 sibling #4 (`role-agent-defs`, `developer-workflows` 0.7.0 → 0.8.0) — and not yet shipped. The commands the playbook drives (`/plan`, `/spawn-worker`, `/work`, `/integrate-worker`, `/queue-status-lite`) **are** shipped; the steps below are reserved and fill in once the roles land. Tracked at `.harness/PLAN.md` (V5-10 sibling #4).

You are the **coordinator**. The roster gives you five personas — `researcher`, `tech-lead`, `worker`, `project-manager`, and the `deep-researcher` agent — that are thin skins over the shipped phase commands ([Coordinator roles](Coordinator-Roles)). This page walks the whole loop once, in order, cross-linking the per-step recipes. Each role wraps a command you can also run bare; the roster just names the persona doing it.

## Steps

1. **Research the brief (`researcher`).** Front the loop with the `researcher` role to scope the work before any plan exists. It wraps `explorer` for a codebase fan-out and the new read-only `deep-researcher` agent for deep / web research (bounded by caller-supplied caps — see [Coordinator roles](Coordinator-Roles#deep-researcher-agent-read-only)). The output is a scoped brief, not a plan.

   _Filled by /work once the task ships — the exact `researcher` dispatch and what it returns land here._

2. **Author the plan (`tech-lead`).** Hand the scoped brief to the `tech-lead` role — the `/design → /plan` authoring persona. Today its floor is `/plan` (`/design` is V5-10 sibling #5, a forward-reference). Stage and activate a named plan so a worker can bind to it: `/plan --stage` then `/plan --activate`. See [Run a named plan](Run-A-Named-Plan) for the staging / activation surface.

   _Filled by /work once the task ships — the `tech-lead` → named-plan hand-off lands here._

3. **Spawn the worker's worktree.** Give the activated named plan its own checkout: run `/spawn-worker <name>`. This creates a `git worktree` on a fresh `worker/<name>` branch and drops the worktree-local `.harness/active-plan` marker that binds it. Worktrees are operator-initiated — this command is the sanctioned way to create one. Full recipe: [Spawn a worker in a worktree](Spawn-A-Worker-In-A-Worktree).

4. **Execute the plan (`worker`).** `cd` into the worktree the spawn step printed, then run `/work` bare — the worktree-local marker binds it to `PLAN-<name>.md`, no `--name` needed. The `worker` role is the persona of this session: one per worktree, autonomous over its plan's task list. Several workers can run concurrently, each in its own worktree, without colliding.

   _Filled by /work once the task ships — the `worker` per-session behavior detail lands here._

5. **Integrate the finished worker.** Back on `main` with a clean tree (not inside the worktree), run `/integrate-worker <name>`. It merges `worker/<name>` → `main`, runs the full deterministic battery on the **integrated** tree, and — only if green — promotes the worker's progress and prunes the worktree. A red gate hard-resets `main` back; it never pushes. Full recipe and the three outcomes: [Integrate a worker](Integrate-A-Worker).

6. **Read the queue (`project-manager`).** At any point, use the `project-manager` role to see the whole queue at a glance: it wraps the read-only `/queue-status-lite` read-model — one entry per active plan, its `Status:`, and its latest progress line. It surfaces state and decides nothing; picking what to `/work` or integrate next stays your call. Full recipe: [See every active plan](See-Every-Active-Plan).

   _Filled by /work once the task ships — what the `project-manager` read-model surfaces (and its forward-references to crickets #41 and V5-11) lands here._

## Verify

_Filled by /work once the task ships._

- Each step's verify is the verify of the command it drives — see the per-step how-tos linked above.
- The whole loop is complete when `/integrate-worker` reports GREEN for the plan you spawned, and `/queue-status-lite` shows the plan dropped from the active queue.

## Troubleshooting

_Filled by /work once the task ships._

- Per-command failure modes live on each step's how-to (spawn refusals, red-gate rollback, conflict handling). This page only sequences them.

## Related

- [Coordinator roles](Coordinator-Roles) — the roster: what each role wraps, read-only vs active, tool allowlists, and the forward-references.
- [Run a named plan](Run-A-Named-Plan) — the write-side recipe behind step 2: authoring + staging + activating a named plan.
- [Spawn a worker in a worktree](Spawn-A-Worker-In-A-Worktree) — step 3: hand an activated plan to a worker in its own checkout.
- [Integrate a worker](Integrate-A-Worker) — step 5: land a finished worker's branch on `main`, gated on the integrated tree.
- [See every active plan](See-Every-Active-Plan) — step 6: the read-only glance over the plan queue.
- [Named plans](Named-Plans) — the command surface the whole loop rides.
