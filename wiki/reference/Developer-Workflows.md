<!-- mode: reference -->
# Developer Workflows

## Architecture

Developer Workflows is the phase-gated loop your agent runs a change through — `/setup`, `/plan`, `/work`, `/review`, `/release`, and the separate `/bugfix` pipeline — plus the design, ship, and worktree commands that surround them. It is the base plugin the rest of the suite enhances: install it alone and you get the whole lifecycle; install the siblings alongside it and they hook into these phases.

### Diagram

The workflow — the phase-gated loop, its authoring feed, the `/bugfix` track, and ship discipline:

![The developer-workflows loop: /setup (once) then /plan -> /work -> /review -> /release, with authoring (/design, /spec, /interview-me) feeding /plan, the /bugfix defect track replacing plan+work, and ship discipline (/launch, /deprecate, /ci-cd, /observe) around /release](diagrams/dev-workflows-loop.svg)

How it composes — what enhances the loop, what requires it, and the AgentM substrate it rests on:

![How developer-workflows composes: code-review, developer-safety, and wiki-maintenance enhance it (soft); design-docs, github-ci, github-projects, releasing-conventions, and testing-conventions require it (hard); it composes one-way onto the AgentM substrate of memory, opinions, and personas](diagrams/dev-workflows-composition.svg)

### How it works

The loop turns a brief into working code through discrete gates rather than one freestyle pass. `/setup` scaffolds a project once; `/plan` turns a brief into `.harness/PLAN.md` with per-task verification criteria and writes no code; `/work` then works that task list autonomously, single-threaded, stopping only when a per-task safety pre-check fails or a clarification is needed; `/review` runs an adversarial pass that assumes the code has bugs; `/release` is the pre-merge gate. `/bugfix` is a different pipeline — Report, Analyze, Fix, Verify — used in place of plan-plus-work for defects. Around that core sit the authoring commands (`/design`, `/spec`, `/interview-me`), the ship-phase commands (`/observe`, `/deprecate`, `/launch`, `/ci-cd`, `/document-decision`), and the multi-plan and worktree surface (`/queue-status-lite`, `/spawn-worker`, `/integrate-worker`). Six role agents — `worker`, `tech-lead`, `researcher`, `project-manager`, `evaluator`, `explorer` — compose onto the loop as thin skins. State lives on disk between sessions, not in the conversation, which is what lets a plan span many sessions. The phase commands and agents are host-symmetric; the two session hooks are Claude-only.

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
| [`/spawn-worker`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/spawn-worker.md) | command | Operator-initiated — give a named plan its own `worker/<name>` worktree. |
| [`/integrate-worker`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/integrate-worker.md) | command | Land a finished worker branch on integration if the merged tree still passes the battery. |
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

No configuration — the plugin works out of the box. The phase commands read on-disk state under `.harness/` (`PLAN.md`, `progress.md`, and optional `project.json`/isolation settings), but those are project state written by the loop, not plugin settings you configure up front.

## See also

- [Named plans](Named-Plans) · [See every active plan](See-Every-Active-Plan) — the multi-plan surface.
- [Spawn a worker in a worktree](Spawn-A-Worker-In-A-Worktree) · [Run isolated tasks](Run-Isolated-Tasks) · [Integrate a worker](Integrate-A-Worker) — the worktree lifecycle.
- [Evaluator](Evaluator) — the `/review` grader's dispatch contract.
- [Code Review](Code-Review) · [Developer Safety](Developer-Safety) — the siblings that enhance the loop.
- [Why phase-gating](Why-Phase-Gating) · [Why adversarial review](Why-Adversarial-Review) — why the loop is shaped this way.
- [Development lifecycle design](crickets-development-lifecycle) · [Composition design](crickets-composition) — the deeper design.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)