<!-- mode: reference -->
# Coordinator roles

> [!NOTE]
> **Status: implemented.** The coordinator roster shipped as loose `agents/` role-definitions in `developer-workflows` 0.8.0 (V5-10 sibling #4 — `role-agent-defs`) — that plugin has since renamed to `development-lifecycle` (AG Wave A; `developer-workflows` still resolves as a declared-both-names capability alias). All four roles live under `src/development-lifecycle/agents/`.

The **coordinator roster** is four loose role-definitions that compose onto the `developer-workflows` phase loop. They are **thin skins over capabilities that already exist** — no new engine, and no net-new sub-agent. Each role names a persona in the operator-as-coordinator flow (research → author a plan → execute it in a worktree → integrate it → read the queue) and binds to the commands and agents that already drive that step. Each entry below states what the role wraps, whether it's read-only or active, its tool allowlist, and any forward-reference to a surface not built yet.

## ⚡ Quick Reference

| Role | Kind | Mode | Wraps | Drives the loop step |
|---|---|---|---|---|
| `researcher` | role | read-only · `Read · Glob · Grep · WebFetch` | `explorer` + its own `WebFetch` + forward-ref to the operator's global research agent | the brief-research front of the loop |
| `tech-lead` | role | active · full access | `/design` → `/plan` | turns a brief into queued / named plans |
| `worker` | role | active · full access | `/work` (one per worktree) | the autonomous executor |
| `project-manager` | role | read-only · `Read · Glob · Grep · Bash` | `/queue-status-lite` | the coordinator's read-model over the queue |

> [!NOTE]
> **Read-only vs active.** A read-only role's tool allowlist excludes `Write`, `Edit`, and any state-mutating Bash — it surfaces and decides nothing it writes. An active role authors or executes work (no `tools:` line = full access). `researcher` and `project-manager` are read-only; `tech-lead` and `worker` are active.

## The compose-onto-`developer-workflows` contract

These are **roles** — thin layers that compose onto surfaces `development-lifecycle` (formerly `developer-workflows`) already ships. Each is a loose `agents/` role-definition (a sub-agent definition under `src/development-lifecycle/agents/`, beside the existing `explorer.md` / `evaluator.md`) that names a persona and points at the phase commands and agents that already do the work. A role adds no new mechanism — it wraps shipped surfaces:

- `researcher` dispatches the shipped `explorer` (codebase fan-out) and runs its own `WebFetch` for light web lookups, and forward-references the operator's global research agent for deep / multi-source work — composing with it when present, never vendoring or porting it. It fronts those capabilities without adding a fan-out engine of its own.
- `tech-lead` is the authoring persona for the `/design → /plan` step — both shipped; `/design` is the upstream authoring step, `/plan` the floor it sequences down to (see below).
- `worker` is the persona of a `/work` session — one per worktree, bound to its plan by the worktree-local `.harness/active-plan` marker that `worktree_marker.py` writes once `/work`'s own auto-spawn step has created the worktree, integrated back via the auto-merging PR `finalize_unit.py` opens at the plan's final task.
- `project-manager` wraps the shipped `/queue-status-lite` read-model.

Because each role is a thin skin, the engine it rides is documented on the surface it wraps — see [Named plans](Named-Plans) for the command surface and [Evaluator](Evaluator) / the agent specs for the agents.

## Per-role detail

### `researcher` (role, read-only)

The brief-research front of the loop — the persona that answers "what do we actually know before we plan this?" It is a **thin skin** owning no new engine: it composes two capabilities that already exist plus one forward-reference.

- **In-repo fan-out.** For "where does X live / how does Y work / what tests cover Z," `researcher` dispatches the shipped `explorer` sub-agent (read-only `Read · Glob · Grep`) and consumes its structured `file:line` summary; it does not re-implement codebase exploration.
- **Light web lookups.** For a quick spec / API / changelog check, `researcher` fetches directly with its own `WebFetch`, bounded to a few targeted lookups rather than a crawl.
- **Deep or multi-source research.** `researcher` forward-references the operator's global research agent (e.g. a personally-installed `memory-idea-researcher`), composing with it **when present** and never vendoring, porting, or reaching into its internals. That agent is operator-personal and out of scope for this public plugin, so `researcher` names it generically. When none is installed, `researcher` degrades gracefully to `explorer` plus its own `WebFetch` — still useful, just shallower.

Its allowlist is `Read`, `Glob`, `Grep`, and `WebFetch`; it cannot write, edit, or run mutating Bash. Output is a structured research finding (1–3 sentence answer + `file:line` / web sources + open questions), never raw tool output; findings flow to `tech-lead` (`/plan`) or `worker` (`/work`), never into the tree itself.

### `tech-lead` (role, active)

The brief-to-plan authoring persona (full tool access): it turns a brief into an **executable plan** a worker can pick up. Its working tool today is the shipped `/plan` phase command, including the named-plan surface:

- `/plan --name <slug>` — author to `PLAN-<slug>.md` instead of the singleton.
- `/plan --stage <slug>` — stage a plan into the inactive `queued-plans/` tier (invisible to `/work` and `/queue-status-lite`).
- `/plan --activate <slug>` — promote a staged plan to the active `PLAN-<slug>.md` (no-clobber guarded).

This lets `tech-lead` queue several plans and activate them one at a time, feeding the worker pool without singleton collisions. After it stages and activates a named plan, running `/work` against it is what hands the plan to a worktree — `/work`'s own auto-spawn step creates the worktree via the host's native primitive when authorized (an explicit operator instruction, or the durable `isolation.mode: worktree-per-plan` config opt-in — never autonomous, [Developer safety design](crickets-developer-safety)); `tech-lead` produces plans, it does not spawn worktrees itself.

> [!NOTE]
> **`/design` is the shipped upstream step.** The richer author → translate → sequence authoring path (`/design`, `src/design/commands/design.md`) shipped at crickets v3.11.0 (2026-06-14). `tech-lead` authors via `/design` when a brief needs the fuller translate-and-sequence treatment, and drops straight to `/plan` (its original floor) for briefs that don't. `/design`'s output is a topo-ordered set of named plans that `/plan` still feeds one at a time.

### `worker` (role, active)

The autonomous executor (full tool access) — the persona of a `/work` **session, one per worktree**, not a sub-agent dispatched inside the coordinator. It binds to its plan via the worktree-local `.harness/active-plan` marker that `worktree_marker.py` writes once the host has created the worktree: a `/work` session launched **inside** the `worktree-<slug>` worktree resolves its own `PLAN-<slug>.md` from the marker — **no `--name` needed**.

- Runs `/work` autonomously through the bound plan's **full** task list, single-threaded, with the per-task safety pre-check gating each task (stop-and-ask only on a hard-to-reverse / ambiguous / scope-drifting / unverifiable task).
- Gates green before every `[x]`; one task, one commit; updates `PLAN-<slug>.md` + `progress-<slug>.md`.
- Closes the loop on its own, at the plan's final task: `finalize_unit.py` pushes the branch, opens a PR carrying the plan's close-out summary, and arms `gh pr merge --auto --squash` — the PR merges once required checks go green, with no separate operator-invoked integrate step. `/work` then runs `ExitWorktree keep`, since the branch still has an open PR against it.

Never fans out parallel implementers — single-threaded execution is the safety constraint everything else leans on, and the per-task safety check sets the autonomy boundary.

### `project-manager` (role, read-only)

The read-only coordinator glance — the persona that answers "what's the state of every plan in flight?" It wraps the shipped [`/queue-status-lite`](See-Every-Active-Plan) read-model, surfacing across every active plan:

- the active-plan binding(s) — singleton and/or named `PLAN-<slug>.md`,
- each plan's progress at a glance,
- worker-worktree state (via the read-only `doctor_worktrees.py` probe).

Its allowlist is `Read`, `Glob`, `Grep`, and `Bash`, and the Bash is read-only by contract — it runs the `queue_status.py` reader and the read-only probes, never anything that mutates. It shows you the read-model's render exactly as produced: it marks no task done, writes no progress file, activates no plan, and merges nothing. Merge order stays a human decision (**LC-5**) — the project-manager gives you the picture and leaves the call to you.

> [!NOTE]
> **crickets #41 (github-projects board-sync) has shipped** as `src/github-projects/scripts/project_sync.py` — a synced board view on top of the local queue, composing with `project-manager`'s read-model. (A `project_sync.py` idempotency bug is tracked separately in R2.3; it doesn't affect this factual correction.)
>
> `project-manager` still forward-references one later surface, not built here: **V5-11** — the chief-of-staff intelligence layer (`/standup`, readiness / safe-parallelization analysis, integration-order *advisory* — still advisory; LC-5 stands). It composes with this when it ships.

## Related

- [Named plans](Named-Plans) — the command surface the roles wrap: `/work`, `/plan`, `/queue-status-lite`, and the auto-spawn / auto-close-out worktree flow inside `/work`.
- [Run a coordinator-directed worker team](Run-A-Coordinator-Directed-Worker-Team) — the playbook that ties the roster together end to end.
- [Evaluator](Evaluator) — a companion read-only agent in `development-lifecycle/agents/`; the same tight-allowlist pattern the read-only roles follow.
- [Run a named plan](Run-A-Named-Plan) · [See every active plan](See-Every-Active-Plan) — the worker-lifecycle recipes the `worker` and `project-manager` roles drive.
