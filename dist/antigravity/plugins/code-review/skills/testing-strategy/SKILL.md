---
name: testing-strategy
description: "Test coverage audit via the Beyonce Rule (uncovered behavior is behavior you've agreed to change silently), DAMP over DRY (tests read like specs, not production code), and the Prove-It pattern (every behavioral claim needs a falsifying test). Use when reviewing a PR for test gaps or when a feature lands without coverage."
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

# testing-strategy

Test coverage audit and strategy review. The goal is to find behavior that is claimed but not proven — specifically, the behavior you care about that has no test that would fail if it broke.

## When to Invoke

- When reviewing a PR where the diff includes behavior changes but no test changes.
- When a feature lands and the test suite "looks fine" but no one has audited coverage explicitly.
- After the adversarial-reviewer surfaces a defect that wasn't caught by an existing test.
- When the test suite is growing but feels like it's testing implementation rather than behavior.

## Key Principles

### Beyonce Rule

> If you liked it, then you should have put a test on it.

Any behavior you care about must have a test that would fail if that behavior changed. Uncovered behavior is not "untested" — it is behavior you've agreed to change silently. The absence of a test is an explicit statement: "I don't care if this breaks."

Apply the Beyonce Rule by asking: "if this behavior were accidentally deleted tomorrow, would a test catch it?" If the answer is no, the behavior is uncovered.

### DAMP over DRY

Tests should be **Descriptive And Meaningful in Phrasing**. A test is not production code — it is a specification. The reader should be able to understand what behavior is being verified without reading the implementation.

DAMP explicitly permits duplication in tests when that duplication improves readability. A test that sets up its own data and makes its own assertions is easier to debug than a test that delegates to helpers that delegate to helpers. The failure of a DAMP test is self-contained; the failure of an over-DRY test requires tracing the call chain.

Signals of anti-DAMP:
- Test names are `testFoo_case1`, `testFoo_case2` (no behavior description).
- Setup is hidden in fixtures that a reader must look up to understand what the test starts with.
- Assertions are generic (`assert result is not None`) rather than behavioral (`assert result.status == "shipped"`).

### Prove-It Pattern

Every claim about behavior must be backed by a test that would fail if the claim were false.

If a commit message says "handles the empty-list case," there must be a test that passes an empty list and asserts the correct behavior. If there isn't, the claim is unverified. "Handles" is a confidence claim; the test is the proof.

## Process

### Step 1 — List the behavioral claims

From the diff and the PR description, list every behavioral claim: "handles X", "returns Y when Z", "ignores N", "raises on invalid input", etc. Include implicit claims — a function named `validateInput` implies it validates; that validation behavior needs coverage.

### Step 2 — Match claims to tests (Beyonce Rule audit)

For each behavioral claim: is there a test that would fail if this behavior changed? Yes / No. A test that calls the function but doesn't assert the specific behavior doesn't count — it must be a falsifying test.

### Step 3 — Assess test quality (DAMP check)

For each existing test that covers a behavioral claim: does the test read like a specification? Can the failure message be understood without reading the implementation? Flag tests that are over-DRY, use opaque fixtures, or have generic assertions.

### Step 4 — Report

For each uncovered claim: `MISSING-TEST <description>:<behavior>` — one sentence stating what behavior has no falsifying test. For each DAMP violation: one sentence describing what the reader cannot infer from the test alone. If all claims are covered and tests are DAMP: `COVERAGE ADEQUATE` — list the claims checked and the Beyonce Rule check performed.

## Common Rationalizations

| Excuse | Why it's wrong |
|---|---|
| "I'll add tests later." | Beyonce Rule: if you liked it you should have put a test on it. Uncovered behavior is behavior you've agreed to change silently. "Later" is a statement that you don't care if this breaks before then. |
| "The code is simple, it doesn't need tests." | Simple code breaks silently. The Beyonce Rule applies regardless of code complexity — it applies to the behavior you care about, not to the code complexity. |
| "I factored out the test helpers to keep things DRY." | DAMP over DRY: test readability matters more than test deduplication. A DAMP test is self-contained; the failure tells you exactly what broke without tracing helpers. |
| "The tests pass, coverage must be fine." | Passing tests prove the behavior didn't break given the inputs the tests used. The Beyonce Rule asks about the behavior you care about — if you didn't write a test for it, passing tests say nothing about it. |

## Verification checklist

Before reporting complete:

- [ ] Every behavioral claim in the diff was checked against the Beyonce Rule.
- [ ] Every `MISSING-TEST` finding names the specific behavior and why no existing test falsifies it.
- [ ] `COVERAGE ADEQUATE` includes an explicit list of what was checked, not just a conclusion.
- [ ] DAMP violations are named by the test name and what behavior cannot be inferred from the failure.
