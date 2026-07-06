---
name: no-skip-tests
description: Any skip/xfail/xit/pending marker requires an explanatory comment stating the technical blocker — not "TODO" or "flaky".
kind: rule
supported_hosts: [claude-code, antigravity]
version: 0.1.0
---

## Rule: no-skip-tests

When you see or write any of the following markers, a comment stating the **exact technical blocker** is required:

- `@pytest.mark.skip`
- `@pytest.mark.xfail`
- `xit(` / `it.skip(`
- `test.skip(`
- `pending(`
- `// SKIP` / `# SKIP`

### Required override shape

```
# SKIP: <one-sentence technical blocker> — see <issue URL or PR>
@pytest.mark.skip
def test_foo():
    ...
```

The comment must appear on the line immediately before the marker. It must name the specific technical reason the test cannot run, not a process state ("TODO", "investigate later", "will fix soon").

### What is NOT an acceptable reason

| Stated reason | Why it is not acceptable |
|---|---|
| "Flaky" | Flakiness is a symptom, not a blocker — diagnose and fix the non-determinism, or mark with the specific race condition / external dependency that causes it. |
| "TODO" | Not a reason. Name the blocker. |
| "investigate later" | Not a reason. Name the blocker, link a tracking issue. |
| "time pressure" | Time pressure is never a technical blocker for a test. Skip the feature, not the test. |

### Enforcement

This rule fires when you are about to add, approve, or merge a skip/xfail marker without a compliant comment. Before proceeding, check:

1. Does the skip comment name the **specific technical blocker** (missing dependency, environment constraint, known upstream bug)?
2. Does it link a tracking issue or PR where the blocker is being addressed?
3. Is the marker scoped to the minimum set of tests that actually cannot run?

If all three are yes, the skip is acceptable. If any is no, fix the comment or fix the test.
