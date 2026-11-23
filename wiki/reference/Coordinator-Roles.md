<!-- mode: reference -->
# Coordinator roles

> [!NOTE]
> **Status: implemented — one role left.** The roster shipped as four role definitions in `developer-workflows` 0.8.0 (now `development-lifecycle`). Crickets plan 105 retired three of them: `researcher`, `tech-lead` and `project-manager` (`development-lifecycle` 2.0.0). `worker` is the one coordinator role, at `src/development-lifecycle/agents/worker.md`.

The **coordinator roster** is now one role definition on the `development-lifecycle` phase loop. `worker` wraps `/work` without adding a new engine or sub-agent. It names the executor persona in the coordinator flow (author a plan → execute it in a worktree → integrate it) and binds to the step commands.

## ⚡ Quick Reference

| Role | Kind | Mode | Wraps | Drives the loop step |
|---|---|---|---|---|
| `worker` | role | active · full access · pins the `sonnet` model alias | `/work` (one per worktree) | autonomous executor |

| Retired role | What it wrapped | Use instead |
|---|---|---|
| `researcher` | `explorer` plus `WebFetch` | `explorer` agent |
| `tech-lead` | `/plan` | `/plan` (`--name`, `--stage`, `--activate`) |
| `project-manager` | `/queue-status-lite` (also retired) | `/open <name>`, which lists a project's plans with their tracker status |

> [!NOTE]
> **Active, not read-only.** Active roles author or execute work with full access (no `tools:` line). `worker` is active.

## The compose-onto-`development-lifecycle` contract

`worker` is a **role** layered onto existing `development-lifecycle` surfaces. It lives in `agents/` beside `explorer.md` and `evaluator.md`, names a persona, and points at `/work`.

- One `/work` session runs per worktree, bound to its plan by the worktree-local `.harness/active-plan` marker that `worktree_marker.py` writes once `/work`'s auto-spawn step creates the worktree. It integrates back through an auto-merging PR that `finalize_unit.py` opens at the final task.

See [Named plans](Named-Plans) for the command surface and [Evaluator](Evaluator) for agent specs.

## `worker` (role, active)

The autonomous executor runs as one `/work` **session per worktree** with full tool access (a session persona, not a coordinator sub-agent). Once the host creates the worktree, `worktree_marker.py` writes the worktree-local `.harness/active-plan` marker. A `/work` session inside `worktree-<slug>` resolves `PLAN-<slug>.md` from that marker, with **no `--name` needed**.

- Runs `/work` single-threaded through the plan's **full** task list. A per-task safety pre-check gates each task and stops to ask only when a step is hard to reverse, ambiguous, out of scope, or unverifiable.
- Checks gates before every `[x]`, makes one commit per task, and updates `PLAN-<slug>.md` and `progress-<slug>.md`.
- Closes the loop at the final task: `finalize_unit.py` pushes the branch, opens a PR carrying the plan's close-out summary, and arms `gh pr merge --auto --squash`. The PR merges once required checks pass. `/work` then runs `ExitWorktree keep`, since the branch still has an open PR against it.

It never runs parallel implementers. Single-threaded execution is the safety rule everything else depends on, and the per-task check sets the autonomy boundary.

Plans reach a worker through `/plan`. `/plan --name <slug>` authors a named plan. `/plan --stage <slug>` stages a queued task that `/work` ignores. `/plan --activate <slug>` promotes it. Running `/work` on an active plan hands it to a worktree when authorized by your instruction or `isolation.mode: worktree-per-plan` ([Developer safety design](crickets-developer-safety)).

## Related

- [Named plans](Named-Plans) — the wrapped commands (`/work`, `/plan`) and worktree flow.
- [Run a coordinator-directed worker team](Run-A-Coordinator-Directed-Worker-Team) — end-to-end team playbook.
- [Evaluator](Evaluator) — companion read-only agent in `development-lifecycle/agents/`.
- [Run a named plan](Run-A-Named-Plan) · [Open a project by name](Open-A-Project-By-Name) — worker recipe and read-only plan view.
