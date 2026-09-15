# How to open a project by name

> [!NOTE]
> **Goal:** Find a project by name, confirm it's the one you mean, and read a short orientation of where it stands, without changing anything.
> **Prereqs:** the `development-lifecycle` plugin installed ([Install crickets plugins](Install-Crickets-Plugins)). The command works without agentm too, and then leaves out what only agentm supplies (see [Development Lifecycle](Development-Lifecycle)).

Use `/open <name>` (or its alias, `/orient <name>`) when you pick a project back up and need its state before deciding anything. It is read-only, the same posture as [`/queue-status-lite`](See-Every-Active-Plan). It never resumes work or activates a plan.

## Steps

1. **Invoke the command.** Run `/open <name>` or `/orient <name>`; the two are one implementation. The command looks in the registered repos and the vault's `projects/` tree, and asks agentm recall as well. A source that isn't available finds nothing.

   ```
   /open crickets
   /orient crickets --note
   ```

2. **Confirm the match.** With one match, the command shows it with its path and asks you to confirm. The line beside the name is the project charter's What line, when the charter has one. With several matches, it lists them for you to pick from. With none, it says so and stops.

3. **Read the orientation.** Once you confirm, the command prints the rendered block as it is. It leaves out any section that has no source:
   - **Brief** — agentm's opening brief for the project's checkout: where the bound project and task stand.
   - **Plans** — for a project with a repo checkout, every plan agentm lists. The ones in flight come first, ordered by their tracker's importance, each with its status and step checklist. Finished plans show as a count. Without agentm, or for a project with no checkout, the plans come from the project's `_harness/`.
   - **Recent progress** — the last few progress lines of each unfinished plan.
   - **Queued plans** — plans waiting to start.
   - **Board state** — the project's rows in `board-items.json`.

4. **Optionally, keep the orientation as a note.** Add `--note` to write the same block to `orientation-note.md` in the project's `_harness/`, replacing the last one. A project with no `_harness/` has nowhere to put the note yet, so the command writes nothing and tells you so.

## Verify

- The command asks you to confirm before it renders anything.
- Nothing changes on disk (`git status` in the project shows nothing new) unless you passed `--note` to a project that has a `_harness/`.
- A plan agentm doesn't list never appears. Each plan with a tracker shows its tracker's status.

## Related

- [See every active plan](See-Every-Active-Plan) — the read-only glance across every active plan at once. `/open` narrows it to one project and adds its brief.
- [Named plans](Named-Plans) — how plans and their trackers are named and resolved, in both layouts.
- [Development Lifecycle](Development-Lifecycle) — the phase-loop plugin this command belongs to.
