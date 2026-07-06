---
name: testing-conventions
description: Day-to-day testing principles — tests-are-sacred, verification-first, and the 3-layer pyramid — for Developer-tier users.
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

Day-to-day testing practice for developers. These are standing principles, not one-off review rules — they apply every time you write, change, or touch code with observable behavior.

> For **review-time gap auditing** (identifying missing test types in a diff), use the `code-review` plugin's `testing-strategy` skill. This skill owns the *practice*; that skill owns the *audit*.

## Tests are sacred

A failing test is information, not an obstacle. It is telling you something true about the gap between what you intended and what you built. **Never delete or skip a test to make a build pass.**

Acceptable responses to a failing test:
1. **Fix the behavior** — the implementation is wrong; correct it.
2. **Fix the test** — the test's expectation was wrong (document why before changing it).
3. **Justify the skip explicitly** — if the test cannot run in the current environment, add a comment stating the exact technical blocker and a link to the tracking issue. "Flaky" is not a blocker; "requires network access, blocked on issue #42" is.

What is never acceptable: deleting a test because it is inconvenient, marking `@pytest.mark.skip` with only "TODO", or weakening an assertion so it always passes.

**Concrete example.** A test asserts `response.status_code == 201`. After a refactor it starts returning `200`. Acceptable: update the response contract and fix the assertion with a comment explaining the intent change. Not acceptable: change the assertion to `assert response.status_code in (200, 201)` to silence the failure without understanding it.

## Verification first

Write the scenario that can fail **before** the code that makes it pass. A test written after the fact verifies that the code does what you just wrote — it doesn't tell you whether the code does what you needed. That is a documentation exercise, not a safety net.

The practical constraint: if you cannot describe, in one sentence, what observable behavior the test is checking before you write the implementation, the requirement is underspecified. Clarify the requirement before writing code.

**Concrete example.** You're adding a `calculate_discount(price, tier)` function. Write `test_gold_tier_gets_20_percent_discount` with an explicit fixture and assertion first. Then write the function until the test passes. If the test was easy to write, the function's contract is clear. If the test was hard to write, the contract needs work.

Verification-first is not about test-driven development as a ritual — it is about forcing a moment of precision before you commit to an implementation path.

## 3-layer test pyramid

Each layer has a distinct purpose, scope, and speed contract. Do not collapse them.

| Layer | What it tests | Speed | Isolation |
|---|---|---|---|
| **Unit** | One function/module's behavior in isolation | < 1 ms per test | No network, no disk, no DB |
| **Integration** | Cross-boundary contracts (e.g. your code + a real DB, or two modules wired together) | 10 ms – 1 s | Real collaborators at the boundary |
| **E2E** | Golden user paths through the full system | Seconds | Full stack, real environment |

**Unit tests** check behavior, not implementation. A test that breaks whenever you rename a private method is testing implementation; rewrite it to test the observable output. Fast unit tests run on every save — if your unit suite takes > 5 seconds you have integration tests disguised as unit tests.

**Integration tests** verify the contract at a boundary your code doesn't control (a database schema, an external API contract, a message queue format). Mock the boundary in unit tests; prove the contract works at the integration layer.

**E2E tests** cover golden paths only — the two or three flows a real user must complete successfully. E2E tests are expensive to write, slow to run, and brittle to maintain. They are not a substitute for unit or integration coverage.

**Concrete example.** A `UserRepository.save(user)` function has three layers of coverage: a unit test that mocks the DB call and asserts the right SQL parameters are passed; an integration test that hits a real (test) database and asserts the record was persisted correctly; an E2E test that logs in, creates a user via the API, and asserts the user appears in the list view. Each layer is doing a job the others cannot.

**Do not push integration failures down.** If an integration test fails, fix the integration — do not add more unit mocks to paper over it.

## When to invoke this skill

- Writing any new behavior (the verification-first principle applies immediately).
- Refactoring existing behavior (tests must remain green, not weakened).
- Reviewing any diff that changes observable behavior (check that all three layers are represented and that no test was deleted or skipped without justification).
