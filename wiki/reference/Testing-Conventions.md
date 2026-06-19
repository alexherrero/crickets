<!-- mode: reference -->
# Testing Conventions plugin

The `testing-conventions` plugin (`requires: developer-workflows`) ships two primitives that keep test discipline standing and visible throughout the dev loop: a **rule** that fires on skip/xfail markers and a **skill** that encodes the three day-to-day testing principles.

## ⚡ Quick Reference

| Aspect | Value |
|---|---|
| Plugin slug | `testing-conventions` |
| Version | 0.1.0 |
| Requires | `developer-workflows` |
| Primitives | `no-skip-tests` rule · `testing-conventions` skill |
| Hosts | Claude Code · Antigravity |

## Primitives

### `no-skip-tests` rule

Fires whenever you add or approve a skip/xfail/xit/pending marker without a compliant comment. The rule requires an inline comment immediately before the marker that states the **exact technical blocker** (not "TODO", not "flaky") and links a tracking issue or PR.

Covered markers: `@pytest.mark.skip` · `@pytest.mark.xfail` · `xit(` / `it.skip(` · `test.skip(` · `pending(` · `// SKIP` / `# SKIP`.

The required override shape:

```
# SKIP: <one-sentence technical blocker> — see <issue URL or PR>
@pytest.mark.skip
def test_foo():
    ...
```

### `testing-conventions` skill

Standing principles the agent applies every time it writes, changes, or reviews code with observable behavior. Three principles, each with concrete examples:

| Principle | What it enforces |
|---|---|
| **Tests are sacred** | Never delete or skip a test to make a build pass. A failing test is information, not an obstacle — fix the behavior, fix the test, or justify the skip explicitly. |
| **Verification first** | Write the scenario that can fail *before* the code that makes it pass. If you can't describe the observable behavior in one sentence before writing the implementation, the requirement is underspecified. |
| **3-layer pyramid** | Unit (< 1 ms, isolated), Integration (10 ms–1 s, real collaborators at the boundary), E2E (golden paths only, full stack). Don't collapse them; don't push integration failures down to unit mocks. |

> For **review-time gap auditing** — identifying missing test types across a diff — use the `code-review` plugin's `testing-strategy` skill. `testing-conventions` owns the *practice*; `testing-strategy` owns the *audit*.

## Install

```bash
claude plugin install testing-conventions@crickets
```

Requires `developer-workflows` as a base. Both plugins must be enabled for the skill to load.

## See also

- [code-review plugin](Code-Review) — the `testing-strategy` skill (review-time test gap audit) and `adversarial-reviewer` agent.
- [Customization Types](Customization-Types) — what `kind: rule` and `kind: skill` are.
- [Manifest Schema](Manifest-Schema) — the `requires:` and `enhances:` contract.
