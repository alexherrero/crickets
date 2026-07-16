<!-- mode: reference -->
# Code Review

## Architecture

Code Review gives your agent a skeptical second pair of eyes on any change. It does not confirm your code looks fine. It assumes there is a bug. It tries to prove the bug exists. It catches real problems that a rubber-stamp review misses.

### Diagram

![How code-review plugs into development-lifecycle — at /review it dispatches the adversarial reviewers, and the evidence-tracker hook guards /work's checkbox flips](diagrams/code-review-composition.svg)

### How it works

You point it at a diff or a PR. It runs an adversarial review. A reviewer reads the change. It assumes the change contains a bug. When Gemini is available, a second reviewer does the same from a different model. The two reviewers do not share one model's blind spots. Each reviewer returns an actionable result. It returns a failing test, a `DEFECT: file:line`, or `NO ISSUES FOUND`. It never returns loose prose.

When you install `development-lifecycle`, these reviewers run automatically at the `/review` phase. An `evidence-tracker` hook stops a task from being ticked off. The agent must read the spec and test files first.

### Composition

| Direction | Plugin | How |
|---|---|---|
| Enhances (soft) | [Development Lifecycle](Development-Lifecycle) | Runs the adversarial reviewers at `/review` and guards `/work`'s checkbox flips — only when both are installed. |
| Enhanced by (soft) | — | None. |
| Requires (hard) | — | None. Code Review is fully standalone. |
| Required by (hard) | — | None. |

### Why not

Code Review is opinionated. It does not fit every workflow. Choose something else if:

- You trust another review pass. This pass could be a human reviewer, a linter suite, or a different AI reviewer. You do not want a second opinion on every change.
- You want a reviewer that explains its reasoning. This reviewer deliberately answers only with a failing test, a `DEFECT: file:line`, or `NO ISSUES FOUND`.
- You want the reviewer to assume the code is fine. The assume-a-bug framing is adversarial. It feels like overkill on small or throwaway changes.

## Reference

### Commands & skills

Each primitive links to the source that implements it.

| Primitive | Kind | What it does |
|---|---|---|
| [`/code-review`](https://github.com/alexherrero/crickets/blob/main/src/code-review/commands/code-review.md) | command | Adversarial review of a diff or PR. |
| [`/doubt`](https://github.com/alexherrero/crickets/blob/main/src/code-review/commands/doubt.md) | command | Fresh-context review of a decision before it stands. |
| [`/simplify`](https://github.com/alexherrero/crickets/blob/main/src/code-review/commands/simplify.md) | command | Cut accidental complexity from a change. |
| [`security-review`](https://github.com/alexherrero/crickets/blob/main/src/code-review/skills/security-review/SKILL.md) | skill | Three-tier boundary security review. |
| [`testing-strategy`](https://github.com/alexherrero/crickets/blob/main/src/code-review/skills/testing-strategy/SKILL.md) | skill | Coverage audit — the Beyoncé Rule, DAMP, Prove-It. |
| [`adversarial-reviewer`](https://github.com/alexherrero/crickets/blob/main/src/code-review/agents/adversarial-reviewer.md) | sub-agent | Assume-bugs critic; returns a failing test or a `DEFECT`. |
| [`adversarial-reviewer-cross`](https://github.com/alexherrero/crickets/blob/main/src/code-review/agents/adversarial-reviewer-cross.md) | sub-agent | The same, cross-model via Gemini; degrades visibly — a `CROSS-REVIEW-DEGRADED: ...` line, never a silent same-model swap, when Gemini is unavailable or breaks its output contract. |
| [`security-auditor`](https://github.com/alexherrero/crickets/blob/main/src/code-review/agents/security-auditor.md) | sub-agent | Finds the unvalidated boundary crossing. |
| [`test-engineer`](https://github.com/alexherrero/crickets/blob/main/src/code-review/agents/test-engineer.md) | sub-agent | Finds the behavior with no test. |
| [`evidence-tracker`](https://github.com/alexherrero/crickets/blob/main/src/code-review/hooks/evidence-tracker/hook.md) | hook | Blocks a `[ ] → [x]` flip until specs and tests are read (Claude-only). |

### Configuration

You do not need to configure anything. The plugin works out of the box.

## See also

- [First code review](01-First-Code-Review) — the tutorial.
- [Review a change](Use-Code-Review) · [Simplify a diff](Simplify-A-Diff) · [In-flight decision review](Use-Doubt-Review) — the how-tos.
- [Why adversarial review](Why-Adversarial-Review) — why the assume-bugs framing works.
- [Code-review design](crickets-code-review) · [Composition design](crickets-composition) — the deeper design.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)
