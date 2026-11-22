---
name: spec
description: "Write the anchor a task is graded against: Goal, Done when, Rules (each with its source), Not doing, Open questions; create-it adds a reference folder and a likeness list. Run by /plan, /build-it and /create-it; you approve it once. Use when starting any task that has no spec yet."
---

**Usage:** `/spec <brief>  |  --plan <plan.md> [--multi] <brief>  |  --check <spec file>`

You are running **spec**: write the one file a task is graded against. Everything later (the direction check, the review passes, the done-report) compares the work to this file, so it is written once, approved once, and kept short.

**Brief from the user:** <what the user typed after /spec>

> **Recommended model for this phase:** Sonnet 5 (`claude-sonnet-5`) — authoring. Override with `/model` if needed.

The shape, placement and checks are `spec_doc.py`'s, not yours: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spec_doc.py"` (`place`, `check`, `render`). Your part is the judgment: what the goal is, which rules apply, what to ask.

## Process

### 1. Find the place and any spec already there

Ask the helper where the spec goes: `spec_doc.py place --slug <slug> --plan <plan.md>` (beside the task's plan), add `--multi` when one spec covers several tasks (it then sits in the project, and each plan links it), or `spec_doc.py place --slug <slug> --project-root <repo root>` when there is no vault (`.harness/spec-<slug>.md`). `/plan` passes its plan path. Propose a short slug from the brief and let the operator change it. It computes a path and creates nothing.

If a spec is already there, ask **Resume / Replace / Cancel**. Never overwrite silently.

### 2. Read what the rules come from

Read the brief, the repo's `AGENTS.md` / `CLAUDE.md`, and the project's living design note: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/project_homes.py" home designs` prints its folder; on exit 3 (no agentm, no vault) skip it and read `wiki/designs/` if the repo has one. Pull only the rules this task touches, and quote each with where it came from. A rule you cannot source is not a rule; leave it out.

### 3. Ask only what blocks the spec

If the brief is clear, ask nothing. If not, ask **at most 5 questions, batched in one message**, each with your best guess so the operator can answer "yes" or correct it. In a non-interactive run (`/loop`, a spawned worker with no human), ask nothing: write the unanswered questions under Open questions and stop.

### 4. Write the spec

Profile `build` (code), `create` (art, sound, UI look, prose) or `both`. Sections, in order:

- **Goal** — what is true when this is done, in a sentence or two.
- **Done when** — lines a person or a script can check: a command that exits 0, a file that exists, a number, what the output says. "Works well" and "is clean" are not checkable; name what shows it.
- **Rules** — `- <rule> — source: <file or section>`, or `none`.
- **Not doing** — what the brief might imply and you are leaving out, or `none`.
- **Open questions** — `none`, or blocking questions only, each ending in `?`.
- create / both only: **Reference** (the `reference/` folder the work is graded against) and **Likeness list** (5–10 lines: what must look, sound or read like the reference).

Size scales how much you write, never whether the file exists. A one-line fix gets a four-line spec.

Write it to the placed path (`spec_doc.py render` takes JSON if that is easier), then run `spec_doc.py check <file>` and fix every line it prints until it exits 0.

### 5. Propose a line for the design, if the task settled something

When this task decides something the living design does not yet say, propose one line for its amendment log and say where it would go. You propose; the operator decides. Never edit the design here.

### 6. One approval

Show the spec and ask once: **Approve / Revise**. That approval is the anchor approval: `/work`, `/build-it` and `/create-it` do not ask again unless Done when changes. Then hand back to the caller (`/plan` links the spec in the step; `/build-it` and `/create-it` carry on).

`--check <file>` runs step 4's check on an existing spec and reports the lines; it writes nothing.

## Verification

- [ ] The spec exists at the path `place` printed, and `check` exits 0.
- [ ] Every rule has a source; every Done-when line names something to look at.
- [ ] No more than 5 questions were asked, in one message.
- [ ] The operator approved it once.
