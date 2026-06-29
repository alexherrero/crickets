<!-- mode: index -->
# Developer Workflows

_The phase-gated developer loop — `/setup` · `/plan` · `/work` · `/review` · `/release` · `/bugfix` — extracted from agentm as a standalone native plugin. The base the other plugins enhance._

Full primitive and hook detail: [development-lifecycle design](crickets-development-lifecycle).

## How it composes

- **Standalone** — installs and works on its own; `requires: []`.
- **The base others enhance** — `developer-safety`'s control hooks and `code-review`'s reviewer engage across the phase loop when installed alongside it.
- **Hosts** — phase commands, agents, output-style, and rule are host-symmetric; `harness-context-session-start` and `compact-nudge-resume` hooks are Claude-only ([Antigravity limitations](Antigravity-Limitations)).

## Why it works

Discrete `plan → work → review → release` gates beat freestyling the whole lifecycle in one pass: context is ephemeral so state lives on disk; `/work` runs the task list autonomously, single-threaded and gated by a per-task safety check; `/review` is adversarial by design — a reviewer primed to assume bugs finds real ones. See [Why phase-gating](Why-Phase-Gating) and [Why adversarial review](Why-Adversarial-Review).

## Related

- [Evaluator](Evaluator) — the `/review` rubric grader's dispatch contract.
- [Named plans](Named-Plans) · [See every active plan](See-Every-Active-Plan) — the multi-plan surface.
- [Spawn a worker in a worktree](Spawn-A-Worker-In-A-Worktree) · [Run isolated tasks](Run-Isolated-Tasks) · [Integrate a worker](Integrate-A-Worker) — the worktree lifecycle.
- [Developer Safety](Developer-Safety) · [Plugin anatomy](Plugin-Anatomy) — the sibling safety plugin + the shared plugin structure.
- [Why phase-gating](Why-Phase-Gating) — why the loop is gated.
- [Development lifecycle design](crickets-development-lifecycle) — the full design, including hooks and `find_process_seam.py`.
- [Composition design](crickets-composition) — the developer-workflows / safety / code-review split.

[Architecture](Architecture) · [Plugins](Plugins) · [Home](Home)
