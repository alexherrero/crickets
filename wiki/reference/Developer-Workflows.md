<!-- mode: reference -->
# Developer Workflows

## Architecture

Developer Workflows is a set of opinionated workflows covering every phase of development — from ideation and design to implementation, and even deprecation. As the agent works, it saves its state to disk through AgentM's memory, so you can split a change across several agents, or give different sessions different kinds of work: research and design in one, implementation or cleanup in another. The agent always knows where it left off, and many of its steps are enhanced by the other crickets plugins when they are installed.

### Diagram

The workflow — the phase-gated loop, its authoring feed, the `/bugfix` track, and ship discipline:

![The developer-workflows loop: /setup (once) then /plan -> /work -> /review -> /release, with authoring (/design, /spec, /interview-me) feeding /plan, the /bugfix defect track replacing plan+work, and ship discipline (/launch, /deprecate, /ci-cd, /observe) around /release](diagrams/dev-workflows-loop.svg)

How it composes — what enhances the loop, what requires it, and the AgentM substrate it rests on:

![How developer-workflows composes: code-review, developer-safety, and wiki-maintenance enhance it (soft); design-docs, github-ci, github-projects, releasing-conventions, and testing-conventions require it (hard); it composes one-way onto the AgentM substrate of memory, opinions, and personas](diagrams/dev-workflows-composition.svg)

### How it works

Developer Workflows moves a change from a rough **idea** to a shipped feature, one gated step at a time, and its commands map onto that flow.

You start with an **idea** — a brief, a feature request, a bug. When it is still fuzzy, `/interview-me` draws out what you actually want. **Research** then fills in what the agent hasn't seen: a read-only sweep of the codebase, and the web when it helps. With the shape clearer, you move to **architecture and design** — `/spec` writes a short PRD, and `/design` takes a design doc to a human-approved final and splits it into parts. Those parts become **plans**: `/plan` turns a brief into a task list with pass/fail criteria, and a larger design fans out into several ordered, named plans. Then the **work** — `/work` runs a plan's tasks one at a time, stopping only when a safety check fails or it needs a decision; for bigger efforts, `/work` itself spawns the plan its own isolated worktree via the host's native worktree primitive and closes it out with an auto-merging pull request, when `isolation.mode: worktree-per-plan` is configured or you ask for one explicitly — there's no separate spawn or integrate command to run. Every change is **reviewed** adversarially at `/review` and shipped through the `/release` gate, with `/bugfix` as the shorter Report → Analyze → Fix → Verify track for defects.

The whole loop runs on disk, not in the conversation: the plan, its progress, and the project's state live in files, which is what lets one plan span many sessions.

### Composition

| Direction | Plugin | How |
|---|---|---|
| Enhances (soft) | — | None. Developer Workflows is the base, not an enhancer. |
| Enhanced by (soft) | [Code Review](Code-Review) · [Developer Safety](Developer-Safety) · [Wiki Maintenance](Wiki-Maintenance) | Code Review runs the adversarial reviewers at `/review`; Developer Safety adds its recoverability control across the loop; Wiki Maintenance dispatches the documenter at phase boundaries — each only when installed alongside. |
| Requires (hard) | — | None. Developer Workflows is fully standalone (`requires: []`). |
| Required by (hard) | [Design Docs](Design-Docs) · [GitHub CI](GitHub-CI) · [GitHub Projects](GitHub-Projects) · [Releasing Conventions](Releasing-Conventions) · [Testing Conventions](Testing-Conventions) | Each declares `requires: [developer-workflows]` — they extend the phase loop and do not install without it. |

### Why not

Developer Workflows is opinionated about how a change should move from brief to merge. Reach for something else if:

- You already run a lifecycle you like — your own scripts, a CI-driven flow, or a different agent harness — and don't want a second set of phase commands layered on top.
- You prefer a freeform, single-pass style. The discrete `plan → work → review → release` gates are deliberate, and on a small or throwaway change they can feel heavier than the change warrants.
- You want the loop but not the on-disk state contract. This plugin writes `.harness/PLAN.md` and `progress.md` and treats them as the source of truth between sessions; if that convention doesn't fit your project, the phases won't either.

## Reference

### Commands & skills

Each primitive links to the source that implements it. The phase and ship commands, plus the six agents, are host-symmetric; the two hooks are Claude-only ([Antigravity limitations](Antigravity-Limitations)).

| Primitive | Kind | What it does |
|---|---|---|
| [`/setup`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/setup.md) | command | First-time project scaffold — writes the `.harness/` files. Run once. |
| [`/plan`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/plan.md) | command | Turn a brief into `PLAN.md` with per-task verification criteria. No code. |
| [`/work`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/work.md) | command | Work the task list autonomously, single-threaded, safety-gated per task. |
| [`/review`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/review.md) | command | Adversarial review — gates first, then the deeper pass if available. Reports, never fixes. |
| [`/release`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/release.md) | command | Pre-merge gate — plan done, gates green, run to completion under the recoverability gate. |
| [`/bugfix`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/bugfix.md) | command | Defect pipeline — Report → Analyze → Fix → Verify. Used instead of plan-plus-work. |
| [`/design`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/design.md) | command | Author a design doc, translate it into parts, sequence them into named plans. |
| [`/spec`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/spec.md) | command | Write a PRD (objectives, UX, structure, tests, out-of-scope) before any code. |
| [`/interview-me`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/interview-me.md) | command | One-question interview loop to extract what an underspecified ask really wants. |
| [`/queue-status-lite`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/queue-status-lite.md) | command | Read-only glance at every active plan and its latest progress line. |
| [`/observe`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/observe.md) | command | Instrumentation discipline — structured logging, RED metrics, tracing, symptom alerts. |
| [`/deprecate`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/deprecate.md) | command | Deprecation lifecycle — compulsory vs advisory, zombie-code removal. |
| [`/launch`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/launch.md) | command | Pre-launch readiness gate — checklist, feature-flag lifecycle, monitoring first. |
| [`/ci-cd`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/ci-cd.md) | command | CI/CD authoring discipline — Shift Left, quality-gate pipeline, failure feedback loops. |
| [`/document-decision`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/document-decision.md) | command | ADR trigger workflow — when to write a decision record and how to execute it. |
| [`worker`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/agents/worker.md) | sub-agent | The autonomous executor of a named plan, one per worktree (Sonnet tier). |
| [`tech-lead`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/agents/tech-lead.md) | sub-agent | The `/design` → `/plan` author. |
| [`researcher`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/agents/researcher.md) | sub-agent | Read-only context gatherer — a thin skin over `explorer` plus light web fetch. |
| [`project-manager`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/agents/project-manager.md) | sub-agent | Read-only glance over the active plans via `/queue-status-lite`. |
| [`evaluator`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/agents/evaluator.md) | sub-agent | The `/review` rubric grader. |
| [`explorer`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/agents/explorer.md) | sub-agent | Read-only codebase fan-out for gathering context. |
| [`harness-context-session-start`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/hooks/harness-context-session-start/hook.md) | hook | Injects harness context at session start (Claude-only). |
| [`compact-nudge-resume`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/hooks/compact-nudge-resume/hook.md) | hook | Nudges a resumed session to pick the loop back up from disk state (Claude-only). |

### Configuration

No configuration — the plugin works out of the box. The phase commands read and write the harness's on-disk state (the plan, progress, and feature files, plus optional project settings), but that is project state the loop maintains, not plugin settings you set up front. Where those files live is set by the project's **state mode**, not by this plugin: they sit either repo-local under `.harness/` or inside your synced memory vault, whichever the harness is configured for.

## See also

- [Named plans](Named-Plans) · [See every active plan](See-Every-Active-Plan) — the multi-plan surface.
- [Run a named plan](Run-A-Named-Plan) · [Run isolated tasks](Run-Isolated-Tasks) — the worktree lifecycle, including `/work`'s own auto-spawn + auto-close-out.
- [Evaluator](Evaluator) — the `/review` grader's dispatch contract.
- [Code Review](Code-Review) · [Developer Safety](Developer-Safety) — the siblings that enhance the loop.
- [Why phase-gating](Why-Phase-Gating) · [Why adversarial review](Why-Adversarial-Review) — why the loop is shaped this way.
- [Development lifecycle design](crickets-development-lifecycle) · [Composition design](crickets-composition) — the deeper design.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)