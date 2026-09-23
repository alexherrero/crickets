# How to see every active plan at a glance

> [!NOTE]
> **Goal:** List every active task of a project — each one's name, its status from its tracker, and the most-recent line of its progress log — in one read-only dashboard, so a coordinator can see the queue before deciding what to `/work` next.
> **Prereqs:** the `development-lifecycle` plugin installed ([Install crickets plugins](Install-Crickets-Plugins)); agentm installed, since it keeps the project's plans; at least one task in the project (see [Named plans](Named-Plans)).

Use `/queue-status-lite` when several tasks are in flight at once and you want a single view of all of them. It is the **read side** of the multi-plan surface: the `--name` writers ([Run a named plan](Run-A-Named-Plan)) drive one task; this glance shows them all. It only reads: it shows you the queue and leaves every decision — what to work, review, or merge — to you.

## Steps

1. **Run the glance** from the project's repo. Invoke `/queue-status-lite`. It takes no arguments: agentm resolves the project from the working directory.

   ```
   /queue-status-lite
   ```

2. **Read the dashboard.** One entry per active task — its name (`042-build-the-brief`), its status from its tracker, and the last line of its progress log. Tasks whose tracker says `done` or `dropped` are left out. In a repo with no vault, the rows are its repo-local plans, which agentm keeps in `.harness/`. The output is agentm's reader's render, passed through verbatim (see [Named plans § Reading the queue](Named-Plans#reading-the-queue--queue-status-lite)).

3. **Decide, then act.** The glance stops at showing. Choose the next move yourself — `/work --name <task>` to work a task, `/review --name <task>` to review one, or nothing at all.

## Verify

- Running `/queue-status-lite` prints one block, one entry per active task, and exits `0`.
- No file changes: the working tree is identical before and after (`git status` shows nothing new) — the command mutates no state.

## Troubleshooting

- **`No plan list: …`.** No agentm checkout was found. development-lifecycle keeps its plans through agentm, so there is no queue to show; install agentm, or set `$AGENTM_SCRIPTS_DIR` to its `scripts/`.
- **A task is missing from the list.** Check its tracker: a `done` or `dropped` task is intentionally left out. A task directory needs a `plan.md` to be listed.

## Related

- [Named plans](Named-Plans) — the lookup: the command's arguments and the read bridge's contract.
- [Run a named plan](Run-A-Named-Plan) — the write-side recipe: driving `/work --name <task>` and friends against one task.
- [Open a project by name](Open-A-Project-By-Name) — one project's brief and tasks, each with its tracker status.
- [Development Lifecycle](Development-Lifecycle) — the phase-loop plugin this command belongs to.
- [Why phase-gating](Why-Phase-Gating) — why state lives on disk.
