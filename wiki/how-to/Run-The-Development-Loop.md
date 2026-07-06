# How to run the development loop

> [!NOTE]
> **Goal:** Take a change from a rough brief to a shipped feature by running it through the phase loop — `/plan` → `/work` → `/review` → `/release` — one gated step at a time, with the plan and its progress kept on disk so the change can span several sessions.
> **Prereqs:** the `developer-workflows` plugin installed ([Install crickets plugins](Install-Into-Project)). Optional: agentm as the memory layer, for vault-backed state.

This is the core loop the `developer-workflows` plugin gives you. Each phase does one job and then stops, and the plan, its progress, and the project's state live in files rather than in the conversation — which is what lets you pick a change back up in a later session. Run the phases in order; for a bug, take the shorter `/bugfix` track instead.

## Prerequisites

- The `developer-workflows` plugin installed on your host ([Install crickets plugins](Install-Into-Project)).
- A change to make — a feature, a refactor, or a bug report.

## Steps

1. **Plan.** Run `/plan <brief>` to turn your brief into a task list with pass/fail criteria, written to `PLAN.md`. No code is written in this phase — it's just the plan. (When you have more than one change in flight at once, give each its own name — see [Run a named plan](Run-A-Named-Plan).)

2. **Work.** Run `/work` to implement the plan. It works the tasks in order, one at a time, updating `progress.md` as it goes, and it stops only when a safety check fails or it needs a decision from you — otherwise it runs to the end of the plan. For a larger change, `/work` itself spawns the plan its own isolated worktree (via the host's native worktree primitive) and closes it out with an auto-merging pull request, when [`isolation.mode: worktree-per-plan`](Run-A-Named-Plan) is configured or you ask for a worktree explicitly — you don't run a separate spawn or integrate command.

3. **Review.** Run `/review` to put the change through an adversarial pass. The reviewer assumes the code has bugs and has to produce a failing test or a specific line-number defect, not a "looks good to me." Deterministic checks — typecheck, lint, tests — come first; the review adds to them.

4. **Release.** Run `/release` as the pre-merge gate: a clean working tree, every check green, and the changelog updated before the change ships.

## Start from an idea, not a brief

When the change is still fuzzy, do the authoring steps first — they feed into `/plan`:

- `/interview-me` draws out what you actually want when the idea isn't clear yet.
- `/spec` writes a short PRD from the shaped idea.
- `/design` takes a design doc to a human-approved final and splits it into parts, which become the plans you hand to `/work`.

## Fixing a bug

For a defect, use `/bugfix <report>` instead of `/plan` + `/work`. It runs a shorter, different track — Report → Analyze → Fix → Verify — aimed at a single fix rather than a feature.

## Related

- [Developer Workflows](Developer-Workflows) — the plugin these phase commands belong to, and how it composes with the rest.
- [Run a named plan](Run-A-Named-Plan) — run the loop against a named plan when several are in flight at once.
- [Author a design](Author-A-Design) — the design step upstream of `/plan`.
- [Why phase-gating](Why-Phase-Gating) — why the loop is gated and its state lives on disk.
- [Install crickets plugins](Install-Into-Project) — get `developer-workflows` onto your host.
