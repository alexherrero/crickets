<!-- mode: how-to -->
# Run isolated tasks

> [!NOTE]
> **Goal:** Run individual plan tasks inside their own git worktrees so each task's changes are fully isolated — rollback and CI granularity at the task level, not the plan level.
> **Prereqs:** `developer-workflows` plugin installed ([Install crickets plugins](Install-Into-Project)); `isolation.mode: worktree-per-task` set in `.harness/project.json`; tasks to isolate marked `**Isolated:** true` in `PLAN.md`.

## When to use this

Use `worktree-per-task` when tasks within a plan are independent enough that you want:

- **Per-task rollback** — a failing task can be discarded without touching the others.
- **Parallel CI validation** — each task's merge commit is separately bisectable.

Cost: every isolated task multiplies CI minutes. Mark only tasks that are genuinely independent; sequential tasks that build on each other should run directly.

## Prerequisites

- `developer-workflows` plugin installed.
- A `.harness/project.json` in your repo (created by `/setup`).
- The `isolation.mode` field set to `worktree-per-task` in that file.

## Steps

### 1. Enable the isolation mode

In `.harness/project.json`, add or update the `isolation` block:

```json
{
  "isolation": {
    "mode": "worktree-per-task"
  }
}
```

This tells `/work`'s step 2.5 to check each task for an isolation flag before executing it.

### 2. Mark tasks as isolated in PLAN.md

In your `.harness/PLAN.md`, add `**Isolated:** true` to each task that should run in its own worktree:

```markdown
### 3. Refactor auth module — Status: [ ]
**Isolated:** true
Rewrite `src/auth/` to the new interface contract.
```

Leave the flag off tasks that must run sequentially or depend on a preceding task's output.

### 3. Run `/work` normally

```
/work
```

When `/work` reaches a task marked `**Isolated:** true`, step 2.5 fires:

1. A per-task worktree is spawned: `worker/<plan-slug>-task-<N>`.
2. Steps 3–9 (implement → commit) run inside the task worktree.
3. After the task commits, the branch merges back into the plan's main context with `git merge --no-ff`.
4. The task worktree and branch are pruned.
5. The task loop continues in the plan's main context.

For non-isolated tasks, step 2.5 exits 1 and `/work` proceeds directly — no worktree spawned.

## Notes

- **Knob separation** — per-task isolation is independent of per-plan integration. Task worktrees merge back into the plan branch; the plan-level `integration` setting (step 12) still controls whether the finished plan lands as a PR or a direct push.
- **Authority is operator-declared** — the agent never auto-marks tasks isolated. Only tasks with `**Isolated:** true` in `PLAN.md` get a worktree.
- **Re-audit trigger** — if the per-task override rate stays near zero across several plans, the N× CI cost isn't earning its keep. Consider reverting to `worktree-per-plan` or `direct`.

## Related

- [Spawn a worker in a worktree](Spawn-A-Worker-In-A-Worktree) — plan-level worktree isolation via `/spawn-worker`.
- [Run a coordinator-directed worker team](Run-A-Coordinator-Directed-Worker-Team) — multi-worker parallel execution.
- [Named plans](Named-Plans) — how plan slugs and `.harness/active-plan` bind workers to plans.
- [Developer Workflows](../architecture/plugins/Developer-Workflows) — full primitive reference.
