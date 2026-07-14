<!-- mode: explanation -->
# Testing Conventions

## Architecture

Testing Conventions gives your agent a steady stance on how to test — one it carries the whole time it writes code, not a pass you bolt on at the end. It holds the line on the habits that keep a suite trustworthy: write the failing test before the code, never weaken or delete a test to get a build green, and keep fast unit tests, integration tests, and end-to-end tests at their own distinct scopes. When the agent reaches for a shortcut like a skip marker, it makes sure there's a real, documented reason rather than a quiet "we'll get to it later." So by the time a change reaches review, the tests already reflect what the code actually does. It builds on Development Lifecycle, extending that phase loop with test discipline rather than standing on its own.

### Diagram

How it composes — the plugin's two primitives, the development-lifecycle base it requires, and the AgentM substrate it rests on:

![How testing-conventions composes: the testing-conventions skill and the no-skip-tests rule sit inside the plugin, which requires (solid slate, hard) the development-lifecycle phase loop — both must be enabled to load — and composes one-way onto the AgentM substrate of memory, opinions, and personas](diagrams/testing-conventions-composition.svg)

### How it works

Two pieces work at two different moments. The first is a set of standing principles the agent keeps in mind as it writes: tests are sacred, so it never guts one to make a build pass; verification comes first, so it writes the failing scenario before the code that answers it; and the test pyramid stays intact, so quick unit tests, integration tests, and slower end-to-end tests each keep their own job instead of blurring together. The second watches for the moment the agent goes to skip a test. Skipping isn't banned — but the agent has to say why in the test itself, naming the actual blocker (a missing dependency, an environment it can't reach, a known upstream bug) and pointing at where it's tracked. A vague "TODO" or "flaky" won't do; the reason has to be real and checkable later.

Together they cover both the reflex and the practice — the split-second you reach for a skip, and the way you write and layer tests in the first place. This plugin owns that day-to-day *practice*. Auditing a finished change for missing test types is a different job, and lives in the Code Review plugin.

### Composition

| Direction | Plugin | How |
|---|---|---|
| Enhances (soft) | — | None. |
| Enhanced by (soft) | — | None. |
| Requires (hard) | [Development Lifecycle](Development-Lifecycle) | Testing Conventions builds on the development-lifecycle base — both plugins must be enabled for the skill and rule to load. |
| Required by (hard) | — | None. |

### Why not

Testing Conventions is opinionated, and it will not fit every workflow. Reach for something else if:

- Your team already has its own testing doctrine — a different pyramid shape, a different stance on skip markers — and you don't want a second opinion layered on top.
- You want review-time gap auditing rather than standing practice; that's the `code-review` plugin's `testing-strategy` skill, not this one.
- The change is small or throwaway. The verification-first and never-skip principles are deliberately firm, and on a spike or a one-off script they can feel heavier than the work warrants.

## Reference

### Commands & skills

Each primitive links to the source that implements it.

| Primitive | Kind | What it does |
|---|---|---|
| [`testing-conventions`](https://github.com/alexherrero/crickets/blob/main/src/testing-conventions/skills/testing-conventions/SKILL.md) | skill | Standing testing principles — tests are sacred, verification first, the 3-layer pyramid. |
| [`no-skip-tests`](https://github.com/alexherrero/crickets/blob/main/src/testing-conventions/rules/no-skip-tests.md) | rule | Fires on a skip/xfail/xit/pending marker; requires a comment naming the technical blocker plus a tracking link. |

### Configuration

No configuration — the plugin works out of the box.

## See also

- [Testing strategy audit](https://github.com/alexherrero/crickets/blob/main/src/code-review/skills/testing-strategy/SKILL.md) — the `code-review` companion that audits a diff for missing test types.
- [Code Review](Code-Review) — the adversarial review plugin this pairs with at review time.
- [Conventions design](crickets-conventions) — the deeper design, including the planned merge of `testing-conventions` and `releasing-conventions` into a single `conventions` plugin.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)