<!-- mode: reference -->
# Development Lifecycle

## Architecture

Development Lifecycle is a set of opinionated workflows. It covers every phase of development. These phases range from ideation and design to implementation and deprecation. The agent saves its state to disk through AgentM's memory as it works. This lets you split a change across several agents. You can give different sessions different kinds of work. You might do research and design in one session. You can do implementation or cleanup in another. The agent always knows where it left off. Other crickets plugins enhance many of its steps when they are installed.

### Diagram

This diagram shows the workflow. It outlines the phase-gated loop. It includes the authoring feed. It displays the `/bugfix` track. It covers ship discipline.

![The development-lifecycle loop: /setup (once) then /plan -> /work -> /review -> /release, with authoring (/design, /spec) feeding /plan, the /bugfix defect track replacing plan+work, and ship discipline (/launch, /deprecate, /ci-cd, /observe) around /release](diagrams/development-lifecycle-loop.svg)

This diagram shows how the lifecycle composes. It details what enhances the loop. It lists what requires the loop. It illustrates the AgentM substrate it rests on.

![How development-lifecycle composes: code-review, developer-safety, and wiki-maintenance enhance it (soft); design-docs, github-ci, github-projects, releasing-conventions, and testing-conventions require it (hard); it composes one-way onto the AgentM substrate of memory, opinions, and personas](diagrams/development-lifecycle-composition.svg)

### How it works

Development Lifecycle moves a change from a rough **idea** to a shipped feature. It progresses one gated step at a time. Its commands map directly onto that flow.

You start with an **idea**. This can be a brief, a feature request, or a bug. **Research** then fills in what the agent hasn't seen. It performs a read-only sweep of the codebase. It searches the web when that helps. You move to **architecture and design** once the shape becomes clearer. The `/spec` command writes the anchor a task is graded against. It asks at most five questions, and only when the brief is ambiguous. The `/design` command takes a design doc to a human-approved final state. It then splits that design into parts. Those parts become **plans**. The `/plan` command turns a brief into a plan of steps with pass/fail criteria, and opens the plan's tracker. A larger design fans out into several ordered, named plans. You then start the **work**. The `/work` command runs a plan's steps one at a time, keeping its tracker current. It stops only when a safety check fails or it needs a decision. For bigger efforts, `/work` spawns its own isolated worktree for the plan. It uses the host's native worktree primitive for this. It closes the worktree out with an auto-merging pull request. This happens when you configure `isolation.mode: worktree-per-plan`. It also happens when you ask for one explicitly. You do not need to run a separate spawn or integrate command. Every change is **reviewed** adversarially at `/review`. Every change is shipped through the `/release` gate. The `/bugfix` command provides a shorter track for defects. This track follows a Report → Analyze → Fix → Verify flow.

The whole loop runs on disk instead of in the conversation. The plan lives in files. Its progress lives in files. Its tracker, written by agentm, says where the plan stands. The project's state lives in files. This on-disk storage lets one plan span many sessions.

### Composition

| Direction | Plugin | How |
|---|---|---|
| Enhances (soft) | — | None. Development Lifecycle is the base, not an enhancer. |
| Enhanced by (soft) | [Code Review](Code-Review) · [Developer Safety](Developer-Safety) · [Wiki Maintenance](Wiki-Maintenance) | Code Review runs the adversarial reviewers at `/review`; Developer Safety adds its recoverability control across the loop; Wiki Maintenance dispatches the documenter at phase boundaries — each only when installed alongside. |
| Requires (hard) | — | None. Development Lifecycle is fully standalone (`requires: []`). |
| Required by (hard) | [Design Docs](Design-Docs) · [GitHub CI](GitHub-CI) · [GitHub Projects](GitHub-Projects) · [Releasing Conventions](Releasing-Conventions) · [Testing Conventions](Testing-Conventions) | Each declares `requires: [development-lifecycle]` — they extend the phase loop and do not install without it. |

### Why not

Development Lifecycle is opinionated about how a change should move from brief to merge. You should reach for something else if any of these apply:

- You already run a lifecycle you like. This could be your own scripts. It could be a CI-driven flow. It could be a different agent harness. You do not want a second set of phase commands layered on top.
- You prefer a freeform, single-pass style. The discrete `plan → work → review → release` gates are deliberate. They can feel heavier than the change warrants on a small or throwaway change.
- You want the loop without agentm, or without its on-disk state contract. The plugin keeps each plan, its progress log and its tracker where agentm puts them, and treats them as the source of truth between sessions. With no agentm there is no plan, and the phases have nothing to run on.

## Reference

### Commands & skills

Each primitive links to the source that implements it. The phase and ship commands are host-symmetric. The six agents are host-symmetric. The two hooks are Claude-only ([Antigravity limitations](Antigravity-Limitations)).

| Primitive | Kind | What it does |
|---|---|---|
| [`/setup`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/setup.md) | command | First-time project scaffold — writes the repo's `.harness/` tools, and seeds a plan only where agentm gives a path back. Run once. |
| [`/plan`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/plan.md) | command | Turn a brief into `PLAN.md` with per-step verification criteria, and open its tracker. No code. |
| [`/work`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/work.md) | command | Work the plan's steps autonomously, single-threaded, safety-gated per step, keeping its tracker current. |
| [`/review`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/review.md) | command | Adversarial review — gates first, then the deeper pass if available. Reports, never fixes. |
| [`/release`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/release.md) | command | Pre-merge gate — the plan's status is done, gates green, run to completion under the recoverability gate. When a release's plan sets `touches_architecture: true`, close-out also asks whether the governing design needs its body and amendment log reconciled in the same landing. |
| [`/bugfix`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/bugfix.md) | command | Defect pipeline — Report → Analyze → Fix → Verify. Used instead of plan-plus-work. |
| [`/spec`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/spec.md) | command | Write the anchor a task is graded against, one file per task: Goal, Done when, Rules (each with its source), Not doing, Open questions; a create-profile spec adds a Reference folder and a 5–10 line Likeness list. Asks at most 5 batched questions, only when the brief is ambiguous; one operator approval. `/plan` sends a task with no spec here. Helper: `scripts/spec_doc.py` (`place`, `check`, `render`). |
| [`loop_record.py`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/scripts/loop_record.py) | script | The bookkeeping helper the build-it / create-it loop commands will call; no command uses it yet. `passes --profile build\|create\|both --size small\|medium\|large [--security] [--prose] [--no-voice]` prints the reviews to run, in order, as JSON: small none; medium direction, the profile's first pass and a done-check; large every pass. Each entry carries its cross-review tier (direction `high`; correctness `default` at medium, `high` at large; voice `wording`; the rest `default`). `init`, `open-round`, `add`, `stop` and `status` keep a JSON record at a path you supply. `add` takes a class (`real`, `tradeoff`, `misread`, `noise`) and a cited `path:LINE`, and refuses a finding without one. `stop` says done when the latest round has no `real` finding, and escalates (exit 3) when round 3 still has one; a fourth round is refused. `status` flags doubt theater: two or more rounds with findings and no `real` one. `dispose` records what was done with a finding (`add` also takes `--disposition`); `requirement` records a Done-when line as `met` or `not-met`, and refuses either without evidence; `not-checked` lists what the run did not look at; `pair` and `playtest` (create-it) record a reference beside what was made, and a playtest checklist line. `report` prints the done-report as markdown: Requirements with evidence; Reviews with every finding, its cited line and its disposition (a `real` finding nobody dealt with reads `OPEN`); a Not checked section that is always present, and lists every review the size called for that never ran; for create-it, Paired images and a Playtest checklist. The done-check is not listed as unrun, since it grades this report. Standard library only. |
| [`/design`](https://github.com/alexherrero/crickets/blob/main/src/design/commands/design.md) | command | Author a design doc, translate it into parts, sequence them into named plans. |
| [`/queue-status-lite`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/queue-status-lite.md) | command | Read-only glance at every active plan and its latest progress line. |
| [`/open`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/open.md) (alias [`/orient`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/orient.md)) | command | LOCATE a project by name (registered repos, vault `projects/` tree, agentm recall), CONFIRM the match, then ORIENT: agentm's opening brief, the project's plans with their tracker status, recent progress, queued plans and board state. Read-only, same posture as `/queue-status-lite`. See [Open a project by name](Open-A-Project-By-Name). |
| [`/observe`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/observe.md) | command | Instrumentation discipline — structured logging, RED metrics, tracing, symptom alerts. |
| [`/deprecate`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/deprecate.md) | command | Deprecation lifecycle — compulsory vs advisory, zombie-code removal. |
| [`/launch`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/launch.md) | command | Pre-launch readiness gate — checklist, feature-flag lifecycle, monitoring first. |
| [`/ci-cd`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/ci-cd.md) | command | CI/CD authoring discipline — Shift Left, quality-gate pipeline, failure feedback loops. |
| [`/document-decision`](https://github.com/alexherrero/crickets/blob/main/src/design/commands/document-decision.md) | command | ADR trigger workflow — when to write a decision record and how to execute it. |
| [`worker`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/agents/worker.md) | sub-agent | The autonomous executor of a named plan, one per worktree (Sonnet tier). |
| [`tech-lead`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/agents/tech-lead.md) | sub-agent | The `/design` → `/plan` author. |
| [`researcher`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/agents/researcher.md) | sub-agent | Read-only context gatherer — a thin skin over `explorer` plus light web fetch. |
| [`project-manager`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/agents/project-manager.md) | sub-agent | Read-only glance over the active plans via `/queue-status-lite`. |
| [`evaluator`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/agents/evaluator.md) | sub-agent | Read-only rubric grader (`Read`, `Glob`, `Grep`), pinned to `claude-sonnet-5`. Also runs the build-it / create-it done-check: grades the anchor and the `loop_record.py report` against fixed checks. No command dispatches it yet. See [Evaluator](Evaluator). |
| [`explorer`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/agents/explorer.md) | sub-agent | Read-only codebase fan-out for gathering context. |
| [`harness-context-session-start`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/hooks/harness-context-session-start/hook.md) | hook | Injects harness context at session start (Claude-only). |
| [`compact-nudge-resume`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/hooks/compact-nudge-resume/hook.md) | hook | Nudges a resumed session to pick the loop back up from disk state (Claude-only). |

### Configuration

There is no plugin configuration. The phase commands read and write the project's on-disk state: the plan, progress, tracker and feature files, plus optional project settings. That is project state the loop maintains, not settings you configure up front. agentm decides where it lives, and the plugin asks. In a project bound to your vault, each plan is a numbered task (`tasks/NNN-<slug>/`) and `features.json` sits in the project's `desk/`. A repo with no vault keeps its plans and `features.json` repo-local under `.harness/`. The repo's own tools (`init.sh`, `verify.sh`, `project.json`) stay in `.harness/` either way.

## See also

- [Named plans](Named-Plans) · [See every active plan](See-Every-Active-Plan) — These documents cover the multi-plan surface.
- [Run a named plan](Run-A-Named-Plan) · [Run isolated tasks](Run-Isolated-Tasks) — These documents detail the worktree lifecycle. They include `/work`'s own auto-spawn and auto-close-out.
- [Evaluator](Evaluator) — This document explains the `/review` grader's dispatch contract.
- [Code Review](Code-Review) · [Developer Safety](Developer-Safety) — These are the sibling plugins that enhance the loop.
- [Why phase-gating](Why-Phase-Gating) · [Why adversarial review](Why-Adversarial-Review) — These documents explain why the loop is shaped this way.
- [Development lifecycle design](crickets-development-lifecycle) · [Composition design](crickets-composition) — These documents detail the deeper design.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)