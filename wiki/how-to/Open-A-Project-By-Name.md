# How to open a project by name

> [!NOTE]
> **Status: pending** — reserved by `PLAN-open-a-project-by-name.md` (vault-backed at `<vault>/projects/crickets/_harness/PLAN-open-a-project-by-name.md`), tasks 2-5. Not yet implemented; this page's shape is locked, its step bodies are filled by `/work` once the command ships.
>
> **Goal:** Resolve a project, idea, or context by name — across the registered-repos list, the vault's `projects/` tree, and agentm recall — confirm the match, and get a short orientation (what it is, its PLAN task-status chart, recent progress, queued plans, board state), read-only, in one turn.
> **Prereqs:** the `development-lifecycle` plugin installed ([Install crickets plugins](Install-Into-Project)). Works standalone; the vault-projects and recall sources degrade gracefully when no agentm clone is mounted (see [Development Lifecycle](Development-Lifecycle)).

Use `/open <name>` (or its alias, `/orient <name>`) when you want to pick a project back up and need the state of it before deciding anything — instead of manually finding the repo, opening its `PLAN.md`, and scanning `progress.md` by hand. It is read-only, the same posture as [`/queue-status-lite`](See-Every-Active-Plan): it locates, confirms, and renders — it never resumes work, marks a task, or activates a plan.

## Steps

1. **Invoke the command.** _Filled by `/work` once task 4 ships._

2. **Confirm the match.** _Filled by `/work` once task 2 ships._

3. **Read the orientation.** _Filled by `/work` once task 3 ships._

4. **Optionally, persist the orientation as a note.** _Filled by `/work` once task 5 ships._

## Verify

_Filled by `/work` once the command ships._

## Related

- [See every active plan](See-Every-Active-Plan) — the sibling read-only glance across every active plan at once; `/open` narrows to one project and adds identity + progress + board context.
- [Named plans](Named-Plans) — the queued-plans tier and `Status:` parsing `/open`'s orientation renderer reuses rather than re-deriving.
- [Development Lifecycle](Development-Lifecycle) — the phase-loop plugin this command belongs to.
