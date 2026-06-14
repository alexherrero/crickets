<!-- mode: reference -->
# Coordinator roles

> [!NOTE]
> **Status: pending.** These role-definitions are planned (V5-10 sibling #4 — `role-agent-defs`, `developer-workflows` 0.7.0 → 0.8.0) and not yet shipped. The roster is reserved here; the per-role detail fills in once the task ships. Tracked at `.harness/PLAN.md` (V5-10 sibling #4).

The **coordinator roster** is four loose role-definitions plus one net-new sub-agent that compose onto the `developer-workflows` phase loop. They are **thin skins over capabilities that already exist** — no new engine. Each role names a persona in the operator-as-coordinator flow (research → author a plan → execute it in a worktree → integrate it → read the queue) and binds to the commands and agents that already drive that step. Use this page to look up what each role wraps, whether it is read-only or active, its tool allowlist, and the forward-references it carries to surfaces that are not built yet.

## ⚡ Quick Reference

| Role / agent | Kind | Mode | Wraps | Drives the loop step |
|---|---|---|---|---|
| `deep-researcher` | agent (net-new) | read-only · `Read · Glob · Grep · WebFetch` | — (a new generalized read-only deep-research agent) | bounded multi-source research (in-repo + bounded web) |
| `researcher` | role | read-only | `explorer` + `deep-researcher` | the brief-research front of the loop |
| `tech-lead` | role | active | `/design` (forward-ref) → `/plan` | turns a brief into queued / named plans |
| `worker` | role | active | `/work <named-plan>` (one per worktree) | the autonomous executor |
| `project-manager` | role | read-only · `Read · Glob · Grep · Bash` | `/queue-status-lite` | the coordinator's read-model over the queue |

> [!NOTE]
> **Read-only vs active.** A read-only role's tool allowlist excludes `Write`, `Edit`, and any state-mutating Bash — it surfaces and decides nothing it writes. An active role authors or executes work. `researcher`, `project-manager`, and the `deep-researcher` agent are read-only; `tech-lead` and `worker` are active.

## The compose-onto-`developer-workflows` contract

These are **roles, not new commands or a new engine.** Each is a loose `agents/` role-definition (a sub-agent definition under `src/developer-workflows/agents/`, beside the existing `explorer.md` / `evaluator.md`) that names a persona and points at the phase commands and agents that already do the work. A role adds no new mechanism — it wraps shipped surfaces:

- `researcher` dispatches the shipped `explorer` (codebase fan-out) and the new `deep-researcher` (deep / web) — it is a front, not a fan-out engine of its own.
- `tech-lead` is the authoring persona for the `/design → /plan` step; `/plan` is its shipped floor today and `/design` is its forward-reference (see below).
- `worker` is the persona of a `/work` session — one per worktree, bound to its plan by the worktree-local `.harness/active-plan` marker that `/spawn-worker` drops, integrated back by `/integrate-worker`.
- `project-manager` wraps the shipped `/queue-status-lite` read-model.

Because each role is a thin skin, the engine it rides is documented on the surface it wraps — see [Named plans](Named-Plans) for the command surface and [Evaluator](Evaluator) / the agent specs for the agents.

## Per-role detail

### `deep-researcher` (agent, read-only)

A generalized, public-safe **read-only deep-research sub-agent**: bounded multi-source research over an in-repo scan plus bounded web fetches. Tool allowlist `Read · Glob · Grep · WebFetch` — no writes, no state-mutating Bash. It takes **caller-supplied budget caps** (wall-time / fetch-count / tokens) and, on overrun, returns **partial results plus an overrun flag** rather than running unbounded.

_Filled by /work once the task ships — the dispatch contract (input sections, the budget-cap parameters, the partial-results-plus-flag output shape) lands here from the shipped agent spec._

### `researcher` (role, read-only)

The brief-research front of the loop. It wraps `explorer` (codebase fan-out) and `deep-researcher` (deep / web), giving `tech-lead` a single research entry point before a plan is authored.

> [!NOTE]
> **Why a port, not a vendor.** The `researcher` does **not** vendor the operator's personal `memory-idea-researcher` agent. That agent is a MemoryVault-system agent (idea-incubator / recall-engine / Obsidian-coupled) — operator-personal and unsafe to ship in a public repo. Instead, `researcher` wraps a **generalized port of its read-only-deep-research pattern** (`deep-researcher`), which carries **zero** MemoryVault / Obsidian / idea-incubator coupling. The pattern is portable; the personal agent is not.

_Filled by /work once the task ships — the dispatch shape and how it hands off to `tech-lead` land here._

### `tech-lead` (role, active)

The `/design → /plan` authoring persona: it turns a brief into queued or named plans.

> [!IMPORTANT]
> **`/design` is a forward-reference.** `/design` is **not yet shipped** — it is V5-10 sibling #5. `tech-lead` forward-references it; its current floor is `/plan` (shipped). Until `/design` lands, `tech-lead` authors directly through `/plan`.

_Filled by /work once the task ships — the authoring hand-off (brief → `/plan --stage` / `--activate` → named plans) lands here._

### `worker` (role, active)

The autonomous executor: `/work <named-plan>`, **one per worktree**. A worker binds to its plan via the worktree-local `.harness/active-plan` marker that [`/spawn-worker`](Spawn-A-Worker-In-A-Worktree) drops, and integrates back to `main` via [`/integrate-worker`](Integrate-A-Worker). In practice it is the persona of a worker *session* — one per worktree.

_Filled by /work once the task ships — the bind-to-marker and integrate-back details land here._

### `project-manager` (role, read-only)

The coordinator surface. It wraps the shipped [`/queue-status-lite`](See-Every-Active-Plan) read-model to surface active-plan / progress / worktree state. Tool allowlist `Read · Glob · Grep · Bash` (read-only Bash only — it reads state, it does not mutate it). It surfaces the queue and decides nothing.

> [!NOTE]
> **Forward-references.** `project-manager` forward-references two later surfaces, neither built yet:
> - **crickets #41** — github-projects board-sync (unbuilt). The later "PM ⊃ #41" refinement: the PM role grows to drive a project board, not just read the local queue.
> - **V5-11** — the chief-of-staff intelligence layer (`/standup`, readiness signals, integration-order advisory). The intelligence refinement on top of the read-model.

_Filled by /work once the task ships — the read-model surface and what each field maps to land here._

## Related

- [Named plans](Named-Plans) — the command surface the roles wrap: `/work`, `/plan`, `/spawn-worker`, `/integrate-worker`, `/queue-status-lite`.
- [Run a coordinator-directed worker team](Run-A-Coordinator-Directed-Worker-Team) — the playbook that ties the roster together end to end.
- [Evaluator](Evaluator) — a companion read-only agent in `developer-workflows/agents/`; the same tight-allowlist pattern the read-only roles follow.
- [Spawn a worker in a worktree](Spawn-A-Worker-In-A-Worktree) · [Integrate a worker](Integrate-A-Worker) · [See every active plan](See-Every-Active-Plan) — the worker-lifecycle recipes the `worker` and `project-manager` roles drive.
