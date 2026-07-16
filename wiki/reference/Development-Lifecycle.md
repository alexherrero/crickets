<!-- mode: reference -->
# Development Lifecycle

## Architecture

Development Lifecycle is a set of opinionated workflows. It covers every phase of development. These phases range from ideation and design to implementation and deprecation. The agent saves its state to disk through AgentM's memory as it works. This lets you split a change across several agents. You can give different sessions different kinds of work. You might do research and design in one session. You can do implementation or cleanup in another. The agent always knows where it left off. Other crickets plugins enhance many of its steps when they are installed.

### Diagram

This diagram shows the workflow. It outlines the phase-gated loop. It includes the authoring feed. It displays the `/bugfix` track. It covers ship discipline.

![The development-lifecycle loop: /setup (once) then /plan -> /work -> /review -> /release, with authoring (/design, /spec, /interview-me) feeding /plan, the /bugfix defect track replacing plan+work, and ship discipline (/launch, /deprecate, /ci-cd, /observe) around /release](diagrams/development-lifecycle-loop.svg)

This diagram shows how the lifecycle composes. It details what enhances the loop. It lists what requires the loop. It illustrates the AgentM substrate it rests on.

![How development-lifecycle composes: code-review, developer-safety, and wiki-maintenance enhance it (soft); design-docs, github-ci, github-projects, releasing-conventions, and testing-conventions require it (hard); it composes one-way onto the AgentM substrate of memory, opinions, and personas](diagrams/development-lifecycle-composition.svg)

### How it works

Development Lifecycle moves a change from a rough **idea** to a shipped feature. It progresses one gated step at a time. Its commands map directly onto that flow.

You start with an **idea**. This can be a brief, a feature request, or a bug. You run `/interview-me` when the idea is still fuzzy. This command draws out what you actually want. **Research** then fills in what the agent hasn't seen. It performs a read-only sweep of the codebase. It searches the web when that helps. You move to **architecture and design** once the shape becomes clearer. The `/spec` command writes a short PRD. The `/design` command takes a design doc to a human-approved final state. It then splits that design into parts. Those parts become **plans**. The `/plan` command turns a brief into a task list with pass/fail criteria. A larger design fans out into several ordered, named plans. You then start the **work**. The `/work` command runs a plan's tasks one at a time. It stops only when a safety check fails or it needs a decision. For bigger efforts, `/work` spawns its own isolated worktree for the plan. It uses the host's native worktree primitive for this. It closes the worktree out with an auto-merging pull request. This happens when you configure `isolation.mode: worktree-per-plan`. It also happens when you ask for one explicitly. You do not need to run a separate spawn or integrate command. Every change is **reviewed** adversarially at `/review`. Every change is shipped through the `/release` gate. The `/bugfix` command provides a shorter track for defects. This track follows a Report → Analyze → Fix → Verify flow.

The whole loop runs on disk instead of in the conversation. The plan lives in files. Its progress lives in files. The project's state lives in files. This on-disk storage lets one plan span many sessions.

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
- You want the loop but not the on-disk state contract. This plugin writes `.harness/PLAN.md` and `progress.md`. It treats them as the source of truth between sessions. The phases will not fit your project if that convention does not fit.

## Reference

### Commands & skills

Each primitive links to the source that implements it. The phase and ship commands are host-symmetric. The six agents are host-symmetric. The two hooks are Claude-only ([Antigravity limitations](Antigravity-Limitations)).

| Primitive | Kind | What it does |
|---|---|---|
| [`/setup`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/setup.md) | command | First-time project scaffold — writes the `.harness/` files. Run once. |
| [`/plan`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/plan.md) | command | Turn a brief into `PLAN.md` with per-task verification criteria. No code. |
| [`/work`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/work.md) | command | Work the task list autonomously, single-threaded, safety-gated per task. |
| [`/review`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/review.md) | command | Adversarial review — gates first, then the deeper pass if available. Reports, never fixes. |
| [`/release`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/release.md) | command | Pre-merge gate — plan done, gates green, run to completion under the recoverability gate. |
| [`/bugfix`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/bugfix.md) | command | Defect pipeline — Report → Analyze → Fix → Verify. Used instead of plan-plus-work. |
| [`/design`](https://github.com/alexherrero/crickets/blob/main/src/design/commands/design.md) | command | Author a design doc, translate it into parts, sequence them into named plans. |
| [`/spec`](https://github.com/alexherrero/crickets/blob/main/src/design/commands/spec.md) | command | Write a PRD (objectives, UX, structure, tests, out-of-scope) before any code. |
| [`/interview-me`](https://github.com/alexherrero/crickets/blob/main/src/design/commands/interview-me.md) | command | One-question interview loop to extract what an underspecified ask really wants. |
| [`/queue-status-lite`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/queue-status-lite.md) | command | Read-only glance at every active plan and its latest progress line. |
| [`/observe`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/observe.md) | command | Instrumentation discipline — structured logging, RED metrics, tracing, symptom alerts. |
| [`/deprecate`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/deprecate.md) | command | Deprecation lifecycle — compulsory vs advisory, zombie-code removal. |
| [`/launch`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/launch.md) | command | Pre-launch readiness gate — checklist, feature-flag lifecycle, monitoring first. |
| [`/ci-cd`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/commands/ci-cd.md) | command | CI/CD authoring discipline — Shift Left, quality-gate pipeline, failure feedback loops. |
| [`/document-decision`](https://github.com/alexherrero/crickets/blob/main/src/design/commands/document-decision.md) | command | ADR trigger workflow — when to write a decision record and how to execute it. |
| [`worker`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/agents/worker.md) | sub-agent | The autonomous executor of a named plan, one per worktree (Sonnet tier). |
| [`tech-lead`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/agents/tech-lead.md) | sub-agent | The `/design` → `/plan` author. |
| [`researcher`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/agents/researcher.md) | sub-agent | Read-only context gatherer — a thin skin over `explorer` plus light web fetch. |
| [`project-manager`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/agents/project-manager.md) | sub-agent | Read-only glance over the active plans via `/queue-status-lite`. |
| [`evaluator`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/agents/evaluator.md) | sub-agent | The `/review` rubric grader. |
| [`explorer`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/agents/explorer.md) | sub-agent | Read-only codebase fan-out for gathering context. |
| [`harness-context-session-start`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/hooks/harness-context-session-start/hook.md) | hook | Injects harness context at session start (Claude-only). |
| [`compact-nudge-resume`](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/hooks/compact-nudge-resume/hook.md) | hook | Nudges a resumed session to pick the loop back up from disk state (Claude-only). |

### Configuration

There is no configuration. The plugin works out of the box. The phase commands read and write the harness's on-disk state. This state includes the plan, progress, and feature files. It includes optional project settings. This is project state the loop maintains. It is not a set of plugin settings you configure up front. The project's **state mode** dictates where those files live. This plugin does not dictate their location. They sit repo-local under `.harness/`. They can alternatively sit inside your synced memory vault. This depends on how you configure the harness.

## See also

- [Named plans](Named-Plans) · [See every active plan](See-Every-Active-Plan) — These documents cover the multi-plan surface.
- [Run a named plan](Run-A-Named-Plan) · [Run isolated tasks](Run-Isolated-Tasks) — These documents detail the worktree lifecycle. They include `/work`'s own auto-spawn and auto-close-out.
- [Evaluator](Evaluator) — This document explains the `/review` grader's dispatch contract.
- [Code Review](Code-Review) · [Developer Safety](Developer-Safety) — These are the sibling plugins that enhance the loop.
- [Why phase-gating](Why-Phase-Gating) · [Why adversarial review](Why-Adversarial-Review) — These documents explain why the loop is shaped this way.
- [Development lifecycle design](crickets-development-lifecycle) · [Composition design](crickets-composition) — These documents detail the deeper design.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)