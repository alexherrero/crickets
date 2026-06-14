<!-- mode: reference -->
# Coordinator roles

> [!NOTE]
> **Status: implemented.** The coordinator roster shipped as loose `agents/` role-definitions in `developer-workflows` 0.8.0 (V5-10 sibling #4 — `role-agent-defs`). All four roles live under `src/developer-workflows/agents/`.

The **coordinator roster** is four loose role-definitions that compose onto the `developer-workflows` phase loop. They are **thin skins over capabilities that already exist** — no new engine, and no net-new sub-agent. Each role names a persona in the operator-as-coordinator flow (research → author a plan → execute it in a worktree → integrate it → read the queue) and binds to the commands and agents that already drive that step. Use this page to look up what each role wraps, whether it is read-only or active, its tool allowlist, and the forward-references it carries to surfaces that are not built yet.

## ⚡ Quick Reference

| Role | Kind | Mode | Wraps | Drives the loop step |
|---|---|---|---|---|
| `researcher` | role | read-only · `Read · Glob · Grep · WebFetch` | `explorer` + its own `WebFetch` + forward-ref to the operator's global research agent | the brief-research front of the loop |
| `tech-lead` | role | active · full access | `/design` (forward-ref) → `/plan` | turns a brief into queued / named plans |
| `worker` | role | active · full access | `/work` (one per worktree) | the autonomous executor |
| `project-manager` | role | read-only · `Read · Glob · Grep · Bash` | `/queue-status-lite` | the coordinator's read-model over the queue |

> [!NOTE]
> **Read-only vs active.** A read-only role's tool allowlist excludes `Write`, `Edit`, and any state-mutating Bash — it surfaces and decides nothing it writes. An active role authors or executes work (no `tools:` line = full access). `researcher` and `project-manager` are read-only; `tech-lead` and `worker` are active.

## The compose-onto-`developer-workflows` contract

These are **roles, not new commands or a new engine.** Each is a loose `agents/` role-definition (a sub-agent definition under `src/developer-workflows/agents/`, beside the existing `explorer.md` / `evaluator.md`) that names a persona and points at the phase commands and agents that already do the work. A role adds no new mechanism — it wraps shipped surfaces:

- `researcher` dispatches the shipped `explorer` (codebase fan-out) and runs its own `WebFetch` for light web lookups, and forward-references the operator's global research agent for deep / multi-source work — composing with it when present, never vendoring or porting it. It is a front, not a fan-out engine of its own.
- `tech-lead` is the authoring persona for the `/design → /plan` step; `/plan` is its shipped floor today and `/design` is its forward-reference (see below).
- `worker` is the persona of a `/work` session — one per worktree, bound to its plan by the worktree-local `.harness/active-plan` marker that `/spawn-worker` drops, integrated back by `/integrate-worker`.
- `project-manager` wraps the shipped `/queue-status-lite` read-model.

Because each role is a thin skin, the engine it rides is documented on the surface it wraps — see [Named plans](Named-Plans) for the command surface and [Evaluator](Evaluator) / the agent specs for the agents.

## Per-role detail

### `researcher` (role, read-only)

The brief-research front of the loop — the persona that answers "what do we actually know before we plan this?" It is a **thin skin** owning no new engine: it composes two capabilities that already exist plus one forward-reference.

- **In-repo fan-out** → the shipped `explorer` sub-agent (read-only `Read · Glob · Grep`). For "where does X live / how does Y work / what tests cover Z," `researcher` dispatches `explorer` and consumes its structured `file:line` summary — it does not re-implement codebase exploration.
- **Light web lookups** → its own `WebFetch`. For a quick spec / API / changelog check it fetches directly, bounded by intent (a few targeted lookups), not a crawl.
- **Deep / multi-source research** → a **forward-reference** to the operator's global research agent (e.g. a personally-installed `memory-idea-researcher`), composing with it **when present** and never vendoring, porting, or reaching into its internals. That agent is operator-personal and out of scope for this public plugin; `researcher` names it generically. When none is installed, `researcher` degrades gracefully to `explorer` + its own `WebFetch` — still useful, just shallower.

Tool allowlist `Read · Glob · Grep · WebFetch` — no `Write`, `Edit`, or mutating Bash. Output is a structured research finding (1–3 sentence answer + `file:line` / web sources + open questions), never raw tool output; findings flow to `tech-lead` (`/plan`) or `worker` (`/work`), never into the tree itself.

### `tech-lead` (role, active)

The brief-to-plan authoring persona (full tool access): it turns a brief into an **executable plan** a worker can pick up. Its working tool today is the shipped `/plan` phase command, including the named-plan surface:

- `/plan --name <slug>` — author to `PLAN-<slug>.md` instead of the singleton.
- `/plan --stage <slug>` — stage a plan into the inactive `queued-plans/` tier (invisible to `/work` and `/queue-status-lite`).
- `/plan --activate <slug>` — promote a staged plan to the active `PLAN-<slug>.md` (no-clobber guarded).

This lets `tech-lead` queue several plans and activate them one at a time, feeding the worker pool without singleton collisions. After it stages and activates a named plan, the **operator** runs `/spawn-worker <slug>` (operator-initiated, never autonomous — [ADR 0022](0022-retire-worktrees-never-auto)) to hand the plan to a worktree; `tech-lead` produces plans, it does not spawn worktrees.

> [!IMPORTANT]
> **`/design` is a forward-reference.** The richer author → translate → sequence authoring path (`/design`) is **not yet shipped** — it is V5-10 sibling #5 (Design-docs packaging). `tech-lead` forward-references it and must not claim it exists; its current floor is `/plan` (shipped). When sibling #5 lands, `/design` becomes the upstream step and `/plan` remains the floor it sequences down to.

### `worker` (role, active)

The autonomous executor (full tool access) — the persona of a `/work` **session, one per worktree**, not a sub-agent dispatched inside the coordinator. It binds to its plan via the worktree-local `.harness/active-plan` marker that [`/spawn-worker`](Spawn-A-Worker-In-A-Worktree) drops: a `/work` session launched **inside** the `worker/<slug>` worktree resolves its own `PLAN-<slug>.md` from the marker — **no `--name` needed**.

- Runs `/work` autonomously through the bound plan's **full** task list, single-threaded, with the per-task safety pre-check gating each task (stop-and-ask only on a hard-to-reverse / ambiguous / scope-drifting / unverifiable task).
- Gates green before every `[x]`; one task, one commit; updates `PLAN-<slug>.md` + `progress-<slug>.md`.
- Closes the loop via [`/integrate-worker <slug>`](Integrate-A-Worker) — a `--no-ff` merge that runs the full gate battery on the merged tree (red gate → hard-reset to pre-merge HEAD; conflict → abort), promotes `progress-<slug>.md` into mainline progress, and prunes the worktree. Integration is local-merge-only — no push.

Never fans out parallel implementers: single-threaded execution is the load-bearing safety constraint, and the autonomy boundary is the per-task safety check, not the task count.

### `project-manager` (role, read-only)

The read-only coordinator glance — the persona that answers "what's the state of every plan in flight?" It wraps the shipped [`/queue-status-lite`](See-Every-Active-Plan) read-model, surfacing across every active plan:

- the active-plan binding(s) — singleton and/or named `PLAN-<slug>.md`,
- each plan's progress at a glance,
- worker-worktree state (via the read-only `doctor_worktrees.py` probe).

Tool allowlist `Read · Glob · Grep · Bash` — and the `Bash` is **read-only by contract** (the `queue_status.py` reader and read-only probes, nothing that mutates). It shows the read-model's render **verbatim**, marking no task `[x]`, writing no `progress-<slug>.md`, activating no plan, merging nothing. It is a *glance, not a gate*: per **LC-5**, merge order is **human-decided** — the PM advises, it does not arbitrate.

> [!NOTE]
> **Forward-references.** `project-manager` forward-references two later surfaces, neither built here:
> - **crickets #41** — github-projects board-sync (unbuilt; sequenced before V5-10 proper). The later "PM ⊃ #41" refinement: a synced board view on top of the local queue.
> - **V5-11** — the chief-of-staff intelligence layer (`/standup`, readiness / safe-parallelization analysis, integration-order *advisory* — still advisory; LC-5 stands). It composes with this when it ships.

## Related

- [Named plans](Named-Plans) — the command surface the roles wrap: `/work`, `/plan`, `/spawn-worker`, `/integrate-worker`, `/queue-status-lite`.
- [Run a coordinator-directed worker team](Run-A-Coordinator-Directed-Worker-Team) — the playbook that ties the roster together end to end.
- [Evaluator](Evaluator) — a companion read-only agent in `developer-workflows/agents/`; the same tight-allowlist pattern the read-only roles follow.
- [Spawn a worker in a worktree](Spawn-A-Worker-In-A-Worktree) · [Integrate a worker](Integrate-A-Worker) · [See every active plan](See-Every-Active-Plan) — the worker-lifecycle recipes the `worker` and `project-manager` roles drive.
