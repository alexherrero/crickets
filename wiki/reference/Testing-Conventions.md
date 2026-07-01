<!-- mode: reference -->
# Testing Conventions

## Architecture

Testing Conventions keeps test discipline standing and visible throughout the dev loop. It is not a review pass you run at the end — it is a set of day-to-day principles the agent carries every time it writes, changes, or touches code with observable behavior, so the discipline is already in place before a review ever happens.

### Diagram

_None / not needed._

### How it works

The plugin ships two primitives that work at different moments. A **rule**, `no-skip-tests`, fires the instant the agent adds or approves a skip, xfail, xit, or pending marker without a compliant comment — it demands an inline note naming the exact technical blocker (a missing dependency, an environment constraint, a known upstream bug) and a link to a tracking issue, and rejects process states like "TODO" or "flaky." A **skill**, `testing-conventions`, encodes three standing principles the agent applies continuously: tests are sacred (never delete or weaken a test to make a build pass), verification first (write the failing scenario before the code that satisfies it), and the 3-layer pyramid (keep unit, integration, and E2E tests at their distinct scopes and speeds rather than collapsing them). Together they cover both the reflex — the moment you reach for a skip marker — and the practice — how you write and layer tests in the first place.

The plugin owns the *practice* of testing. For review-time gap auditing — spotting which test types a diff is missing — reach for the `code-review` plugin's `testing-strategy` skill instead; that one owns the *audit*.

### Composition

| Direction | Plugin | How |
|---|---|---|
| Enhances (soft) | — | None. |
| Enhanced by (soft) | — | None. |
| Requires (hard) | [Developer-Workflows](Developer-Workflows) | Testing Conventions builds on the developer-workflows base — both plugins must be enabled for the skill and rule to load. |
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