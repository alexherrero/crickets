# How to run a coordinator-directed worker team

> [!NOTE]
> **Goal:** Run the coordinator loop yourself: take a brief through research, planning, isolated execution, integration, and project review using the phase commands and the `worker` role.
> **Prereqs:** the `development-lifecycle` plugin at 2.0.0 or later ([Install crickets plugins](Install-Crickets-Plugins)), a clean `main` working tree, and a brief for what you want built. Read [Coordinator roles](Coordinator-Roles) first to see what `worker` wraps.

You are the **coordinator**. This guide walks the loop in order and links to each step's recipe. You run the other steps directly and use the `worker` role for execution.

## Steps

1. **Research the brief.** Dispatch the read-only `explorer` agent to map relevant files and tests before planning. It makes no edits and returns a `file:line` summary. The output is a scoped brief.

2. **Author the plan.** If the brief settles a call for the project's design note, record it with `/design` first. Write a named plan with `/plan --name <slug>`. Or queue it with `/plan --stage <slug>` so `/work` skips it, then activate it with `/plan --activate <slug>`. Staging lets you queue plans and activate them one at a time without collisions. See [Run a named plan](Run-A-Named-Plan) for staging and activation details.

3. **Run `/work` to spawn the worktree.** With `isolation.mode: worktree-per-plan` in `.harness/project.json` or your explicit instruction, `/work` spawns a worktree at step 1.5. It uses the host's primitive: Claude Code's `EnterWorktree` or Antigravity's New-Worktree-Mode / `invoke_subagent`. The worktree lands at `.claude/worktrees/<name>` on branch `worktree-<name>`. `worktree_marker.py` writes the worktree-local `.harness/active-plan` marker to bind the plan. It also writes `.harness/worktree-for-<slug>` in the original root so a resumed session can find its way back. Worktrees require config opt-in or your instruction, triggered through `/work`. Full recipe: [Run a named plan](Run-A-Named-Plan).

4. **Execute the plan (`worker`).** The `worker` role runs this `/work` session. One worker operates per worktree and works through its plan's **full** task list autonomously. Each task passes a safety pre-check; the worker stops to ask only when a task is hard to reverse, ambiguous, out of scope, or unverifiable. It passes checks before marking `[x]`, makes one commit per task, and updates `PLAN-<name>.md` and `progress-<name>.md`. It stays single-threaded without parallel implementers so execution stays safe. Separate workers can run concurrently in their own worktrees without colliding.

5. **Close the loop on the final task.** `finalize_unit.py` pushes the branch, opens a PR with the plan's close-out summary, and arms `gh pr merge --auto --squash`. The PR merges automatically once the required checks pass under branch protection. A failed check blocks the merge without needing a manual rollback. `/work` then runs `ExitWorktree keep` because the PR is still open. A periodic sidecar, `worktree_shepherd.py`, reclaims worktrees left after their PR merges and rebases any PR GitHub marks as `BEHIND` its base.

6. **Look over the project's plans.** Run `/open <name>` at any time for a read-only view: agentm's brief for the project, every plan with its tracker status and step checklist, recent progress lines, and queued plans. It changes nothing on disk. Run the read-only `doctor_worktrees.py` probe to check worktree state. Merge order stays a human decision (LC-5), so you choose what to `/work` next. Full recipe: [Open a project by name](Open-A-Project-By-Name).

## Verify

- Each step uses its linked command's verify check; see the how-tos above.
- After step 2, `/plan --activate <slug>` leaves an active `PLAN-<slug>.md`. After step 3, the `worktree-<name>` worktree exists with `.harness/active-plan` holding the bare slug.
- The loop finishes when the PR merges (required gate checks passing) and `/open <name>` shows the plan's tracker as done.

## Troubleshooting

- **`/work` can't find a plan inside the worktree.** Confirm you are inside the worktree `/work` created rather than on `main`. Run `/work` bare without `--name` so it reads `.harness/active-plan`.
- **A resumed session runs in the main clone instead of the plan's worktree.** Run `/work --name <slug>` so step 1.5 reads `.harness/worktree-for-<slug>` and re-enters the worktree. On a **stale pointer** (missing, deregistered, or reassigned worktree), the session continues in the main clone; confirm the worktree is gone, then run `worktree_marker.py clear <slug>`. If no pointer exists, enter the worktree manually once so the next close-out aligns it.
- **The plan's PR won't merge.** A failed gate battery blocks the merge because it is a required status check. Fix the failure in the worktree and push again to re-run checks; nothing merged, so no rollback is needed.
- **A stale or orphaned worktree.** Run `doctor_worktrees.py` to spot one. `worktree_shepherd.py` reclaims old, provably safe worktrees automatically, or you can clean it up manually.
- Per-command failure modes live in each step's guide; this page covers the sequence.

## Related

- [Coordinator roles](Coordinator-Roles) — what `worker` wraps, and the three roles crickets plan 105 retired.
- [Run a named plan](Run-A-Named-Plan) — authoring, staging, and activating plans (step 2), plus auto-spawn and close-out (steps 3 and 5).
- [Open a project by name](Open-A-Project-By-Name) — read-only project plan view (step 6).
- [Named plans](Named-Plans) — the command surface behind this loop.
