<!-- mode: index -->
# Developer Workflows

The phase-gated developer loop — `/setup` · `/plan` · `/work` · `/review` · `/release` · `/bugfix` — extracted from agentm as a standalone native plugin, plus the read-only `/queue-status-lite` glance over the plan queue. It's the **base** of the developer suite: `developer-safety` and `code-review` enhance its phase loop when installed alongside it.

## Install

```bash
claude plugin install developer-workflows@crickets
```

On Antigravity, install by path (see [Install crickets plugins](Install-Into-Project)). The phase commands + sub-agents work on both hosts; the one `SessionStart` hook is Claude-only ([Compatibility](Compatibility)).

## What it ships

| Primitive | Kind | What it does |
|---|---|---|
| **`/setup`** | command | first-time scaffold — feature list + `init.sh`, once per project |
| **`/interview-me`** | command | hypothesis-driven one-Q-at-a-time brief extraction; stops at ≥95% confidence; non-interactive contexts excluded |
| **`/spec`** | command | writes a 6-section PRD (Objectives, Commands/UX, Structure, Code Style, Testing Plan, Out-of-Scope Boundaries) to `.harness/SPEC.md` before any planning; `/plan` reads it as structured input |
| **`/plan`** | command | turn a brief into `PLAN.md` tasks + verification criteria (no code written); reads `SPEC.md` when present; appends `/clear`-not-`/compact` reminder |
| **`/work`** | command | implement the plan's task list autonomously, gated by a per-task safety check, update `progress.md` |
| **`/review`** | command | adversarial critique — a failing test or a line-number defect, not prose |
| **`/release`** | command | pre-merge gate — clean tree, gates green, changelog updated; appends `/clear`-not-`/compact` reminder |
| **`/bugfix`** | command | the Report → Analyze → Fix → Verify pipeline (used instead of plan+work for bugs) |
| **`/queue-status-lite`** | command | read-only glance over the plan queue — lists every active plan in `_harness/` with its `Status:` + last progress line; surfaces, never mutates ([Named plans](Named-Plans)) |
| **`/observe`** | command | "instrument as you build" gate: structured logging (events not strings), RED metrics, OpenTelemetry tracing, symptom-based alerting; triggered when adding telemetry or shipping to production ([how-to](Add-Observability-With-Observe)) |
| **`/deprecate`** | command | deprecation lifecycle: classify compulsory vs advisory (compulsory = remove now; advisory = migration path first), zombie-code sweep via Beyonce Rule; triggered when removing old systems or migrating callers ([how-to](Deprecate-A-Surface-With-Deprecate)) |
| **`/launch`** | command | pre-launch readiness gate: observability wired, rollback tested, feature flag off-switch confirmed, staged rollout plan written; triggered on first production rollout of a feature ([how-to](Add-Launch-Readiness-Gate)) |
| **`/ci-cd`** | command | CI/CD pipeline authoring: Shift Left (gates earlier), Faster is Safer (smaller diffs), canonical lint→typecheck→test→build→deploy order, no-bypass enforcement; triggered when authoring or modifying CI/CD configs ([how-to](Author-A-CICD-Pipeline)) |
| **`/document-decision`** | command | ADR trigger workflow: when to write (architectural decision, public API change, non-obvious behavior), how to execute (draft before implementing, "why not the alternative", link from CHANGELOG); references adr-shape convention ([how-to](Record-An-Architectural-Decision)) |
| **`worker`** | agent · `model: claude-opus-4-8` | active executor role — the autonomous `/work` persona, one per worktree; binds to its named plan via the worktree-local `.harness/active-plan` marker |
| **`explorer`** | agent | read-only codebase fan-out — answers "where does this live / how does it work" without spending main-loop context |
| **`researcher`** | agent · `model: claude-sonnet-4-6` | research sub-agent — cheaper model by default; delegates deep research tasks from worker or plan |
| **`tech-lead`** | agent · `model: claude-sonnet-4-6` | tech-lead sub-agent — cheaper model by default; handles architecture review tasks from worker |
| **`evaluator`** | agent | read-only rubric grader — `PASS` / `NEEDS_WORK` from a fresh context that never saw the build ([Evaluator](Evaluator)) |
| **`harness-context-session-start`** | hook · `SessionStart` | surfaces `.harness/PLAN.md` + `progress.md` at session boot so the agent reads the plan first (Claude-only) |
| **`compact-nudge-resume`** | hook · `UserPromptSubmit` | on every user prompt, injects a `/clear`-over-`/compact` nudge when context ≥ 60% or > 400 assistant turns; silent no-op below threshold or on a fresh session (Claude-only) |
| **`terse`** | output-style | silence inter-tool narration; preserve the full end-of-task status report — the end-of-task summary is never trimmed |
| **`edit-over-write`** | rule | prefer `Edit` to `Write` for existing files (5× billed-output rationale); `Write` only for new files or near-total rewrites |

The six phase commands run the loop; the canonical phase **methodology** (what each phase must and must not do) lives in agentm's [phase specs](https://github.com/alexherrero/agentm/tree/main/harness/phases). `/queue-status-lite` is the odd one out — a read-only **status** command, not a phase gate: it surfaces the plan queue and decides nothing, leaving the operator to choose what to `/work` next. `capability_probe.py` is the internal helper that lets sibling plugins detect this one for graceful-skip. The five Ship-phase commands (`/observe`, `/deprecate`, `/launch`, `/ci-cd`, `/document-decision`) are shipped; each has a companion how-to page with complete steps and a verify checklist.

The three typed agents (`worker`, `researcher`, `tech-lead`) carry explicit `model:` defaults as token-efficiency levers — Opus for the autonomous executor, Sonnet for the research and review sub-agents. The `terse` output-style and `edit-over-write` rule ship as named primitives so any session can opt in without repeating the instruction text.

## How it composes

- **Standalone** — installs and works on its own; `requires: []`.
- **The base others enhance** — `developer-safety`'s control hooks and `code-review`'s reviewer engage across `/plan` · `/work` · `/review` · `/release` when installed alongside it. They detect it via the capability probe and graceful-skip when it's absent.
- **Hosts** — both. The six phase commands + `/queue-status-lite` + agents + output-style + rule are host-symmetric; `harness-context` and `compact-nudge-resume` hooks are Claude-only ([Antigravity limitations](Antigravity-Limitations)).

## Why it works

Discrete `plan → work → review → release` gates beat freestyling the whole lifecycle in one pass: context is ephemeral, so state lives on disk (`PLAN.md` / `progress.md`); `/work` runs the plan's task list autonomously, single-threaded and gated by a per-task safety check, so changes stay coherent; and `/review` is adversarial by design — a reviewer primed to assume bugs finds real ones. See [Why phase-gating](Why-Phase-Gating) and [Why adversarial review](Why-Adversarial-Review).

## Related

- [agentm phase specs](https://github.com/alexherrero/agentm/tree/main/harness/phases) — the canonical methodology behind each command.
- [Evaluator](Evaluator) — the `/review` rubric grader's dispatch contract.
- [Named plans](Named-Plans) · [See every active plan](See-Every-Active-Plan) — the multi-plan surface: the `--name` writers + the `/queue-status-lite` read-side glance.
- [Developer Safety](Developer-Safety) · [Plugin anatomy](Plugin-Anatomy) — the sibling safety plugin + the shared plugin structure.
- [Why phase-gating](Why-Phase-Gating) — why the loop is gated.
- [Developer Plugin Suite design](developer-plugin-suite) — the developer-workflows / safety / code-review split.
