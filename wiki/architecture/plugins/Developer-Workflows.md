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
| **`/plan`** | command | turn a brief into `PLAN.md` tasks + verification criteria (no code written) |
| **`/work`** | command | implement **one** task from the plan, update `progress.md`, stop |
| **`/review`** | command | adversarial critique — a failing test or a line-number defect, not prose |
| **`/release`** | command | pre-merge gate — clean tree, gates green, changelog updated |
| **`/bugfix`** | command | the Report → Analyze → Fix → Verify pipeline (used instead of plan+work for bugs) |
| **`/queue-status-lite`** | command | read-only glance over the plan queue — lists every active plan in `_harness/` with its `Status:` + last progress line; surfaces, never mutates ([Named plans](Named-Plans)) |
| **`explorer`** | agent | read-only codebase fan-out — answers "where does this live / how does it work" without spending main-loop context |
| **`evaluator`** | agent | read-only rubric grader — `PASS` / `NEEDS_WORK` from a fresh context that never saw the build ([Evaluator](Evaluator)) |
| **`harness-context-session-start`** | hook · `SessionStart` | surfaces `.harness/PLAN.md` + `progress.md` at session boot so the agent reads the plan first (Claude-only — `SessionStart` has no Antigravity event) |

The six phase commands run the loop; the canonical phase **methodology** (what each phase must and must not do) lives in agentm's [phase specs](https://github.com/alexherrero/agentm/tree/main/harness/phases). `/queue-status-lite` is the odd one out — a read-only **status** command, not a phase gate: it surfaces the plan queue and decides nothing, leaving the operator to choose what to `/work` next. `capability_probe.py` is the internal helper that lets sibling plugins detect this one for graceful-skip.

## How it composes

- **Standalone** — installs and works on its own; `requires: []`.
- **The base others enhance** — `developer-safety`'s control hooks and `code-review`'s reviewer engage across `/plan` · `/work` · `/review` · `/release` when installed alongside it. They detect it via the capability probe and graceful-skip when it's absent.
- **Hosts** — both. The six phase commands + `/queue-status-lite` + two agents are host-symmetric; only the `harness-context` hook is Claude-only ([Antigravity limitations](Antigravity-Limitations)).

## Why it works

Discrete `plan → work → review → release` gates beat freestyling the whole lifecycle in one pass: context is ephemeral, so state lives on disk (`PLAN.md` / `progress.md`); `/work` runs the plan's task list autonomously, single-threaded and gated by a per-task safety check, so changes stay coherent; and `/review` is adversarial by design — a reviewer primed to assume bugs finds real ones. See [Why phase-gating](Why-Phase-Gating) and [Why adversarial review](Why-Adversarial-Review).

## Related

- [agentm phase specs](https://github.com/alexherrero/agentm/tree/main/harness/phases) — the canonical methodology behind each command.
- [Evaluator](Evaluator) — the `/review` rubric grader's dispatch contract.
- [Named plans](Named-Plans) · [See every active plan](See-Every-Active-Plan) — the multi-plan surface: the `--name` writers + the `/queue-status-lite` read-side glance.
- [Developer Safety](Developer-Safety) · [Plugin anatomy](Plugin-Anatomy) — the sibling safety plugin + the shared plugin structure.
- [Why phase-gating](Why-Phase-Gating) — why the loop is gated.
- [Developer Plugin Suite design](developer-plugin-suite) — the developer-workflows / safety / code-review split.
