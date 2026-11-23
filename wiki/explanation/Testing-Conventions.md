<!-- mode: explanation -->
# Testing Conventions

## Architecture

Testing Conventions is crickets' test discipline, currently one rule. The `no-skip-tests` rule lives in the `conventions` plugin. When the agent adds a skip marker, the rule requires a written reason. Reviewers check whether tests prove their claims in `/build-it`'s correctness pass. The plugin builds on Development Lifecycle and does not stand alone.

### Diagram

How `no-skip-tests` inside `conventions` composes with the `development-lifecycle` base it requires and the AgentM substrate:

![How the testing rule composes: the no-skip-tests rule sits inside the conventions plugin, which requires (solid slate, hard) the development-lifecycle phase loop — both must be enabled to load — and composes one-way onto the AgentM substrate of memory, opinions, and personas](../reference/diagrams/testing-conventions-composition.svg)

### How it works

The rule fires when the agent skips a test. Skipping is allowed if the agent explains why in the test. The comment names the technical blocker (a missing dependency, an unreachable environment, or a known upstream bug) and links where it is tracked. A vague "TODO" or "flaky" fails the rule; the blocker must be checkable.

Review handles the rest of test discipline. Crickets plan 105 retired the `testing-conventions` skill, which held the standing principles (tests are sacred, verify first, the three-layer pyramid). It also retired `code-review`'s `testing-strategy` audit. Its checks now sit in the correctness pass that `adversarial-reviewer` and `cross-review.sh` run inside `/build-it`. That pass flags missing tests and unproven tests. A missing test is a behaviour change with no test that would catch its regression. An unproven test is a claim no test would fail on, a regression test never shown to fail on the pre-fix code, or an assertion too generic to name the behaviour. The rule against weakening a test to get a build green lives in agentm's `AGENTS.md`.

### Composition

| Direction | Plugin | How |
|---|---|---|
| Enhances (soft) | — | None. |
| Enhanced by (soft) | — | None. |
| Requires (hard) | [Development Lifecycle](Development-Lifecycle) | Builds on `development-lifecycle`; both plugins must be enabled to load. |
| Required by (hard) | — | None. |

### Why not

This rule will not fit every workflow. Use another approach if:

- Your team already enforces its own skip-marker policy.
- You only want review-time test auditing via `/build-it`'s correctness pass in `code-review`.
- You are writing a spike or throwaway script where documenting every skip adds overhead.

## Reference

### Commands & skills

Each primitive links to the source that implements it.

| Primitive | Kind | What it does |
|---|---|---|
| [`no-skip-tests`](https://github.com/alexherrero/crickets/blob/main/src/conventions/rules/no-skip-tests.md) | rule | Fires on skip/xfail/xit/pending markers; requires a comment naming the technical blocker and a tracking link. |

### Configuration

No configuration needed.

## See also

- [Code Review](Code-Review) — runs the correctness pass for missing and unproven tests.
- [Conventions design](crickets-conventions) — design note for `conventions`.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)
