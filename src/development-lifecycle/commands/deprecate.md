---
name: deprecate
description: "Deprecation lifecycle — code-as-liability mindset. Compulsory vs advisory deprecation (compulsory: you control all callers, remove now; advisory: external callers exist, migration path required first). Zombie code removal via the Beyonce Rule. Triggered when removing old systems or migrating callers off an interface."
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: <interface, module, or function being deprecated — required>
---

You are running **/deprecate** — the deprecation lifecycle pipeline for code you are removing or migrating callers away from.

**Target:** $ARGUMENTS — the interface, function, module, or system being deprecated. Required.

## When to Use

Run `/deprecate`:

- When removing a function, endpoint, module, or service that has callers.
- When migrating callers from an old interface to a new one.
- When a feature is being sunset and existing users need a removal path.
- When cleaning up dead code that silently exists but is no longer used.

**Do NOT use** for live, actively-used interfaces you have no intention of removing. Deprecation is a commitment: you are either removing now or providing a migration path with a removal date.

## Key Principles

### Code as Liability

Every line of code is a liability — it must be tested, understood, maintained, and debugged. Code that is no longer serving a user need is pure liability. The goal of deprecation is not to mark code as old; it is to remove it.

A deprecated interface with no removal date is an interface you have agreed to maintain forever.

### Compulsory vs Advisory Deprecation

Before starting, classify the deprecation:

**Compulsory** — you control every caller. You can find them all (grep, type checker, test suite), update them, and remove the interface in a single operation. There is no external consumer you cannot reach. Do it now.

**Advisory** — external callers exist that you cannot update (public API consumers, downstream services, third-party integrations). You cannot remove the interface until you have provided a migration path, notified callers, and waited a deprecation window. A published removal date is required.

If a deprecation is advisory but you treat it as compulsory, you break callers you did not know about. Classify first.

### Zombie Code Removal

Zombie code is dead code that passes all tests because no test covers it. The test suite cannot catch a zombie's removal because nothing asserts on its behavior. The Beyonce Rule: "if you liked it, you should have put a test on it." If you are about to delete a function and no test would fail, the function is either truly dead or its behavior is uncovered.

Before removing, apply the Beyonce Rule: grep for callers, check the test suite, confirm the function's behavior is either genuinely unused or covered by an existing test. Do not delete on "I think it's dead" — verify.

## The Process

### Step 1 — Classify the deprecation

Determine: compulsory or advisory? Run a grep and type-check to enumerate every caller. If all callers are in the same repo and under your control: compulsory. If any caller is external (published API, downstream service, open-source consumer): advisory.

### Step 2 — Compulsory: migrate and remove

For compulsory deprecations:

1. Update every caller to the new interface or remove the call entirely.
2. Apply the Beyonce Rule **before deleting**: `grep -r "deprecated_symbol" .` — are there callers beyond those in step 1? Run the test suite with the code temporarily removed (local change only, do not commit). If tests fail, there are callers you missed — fix them and return to step 1.
3. Delete the deprecated interface (confirmed dead by the check in step 2).
4. Run the full test suite. If a test fails, it found a caller you missed — fix it, do not skip it.
5. Confirm no remaining references: `grep -r "deprecated_symbol" .` returns nothing.

### Step 3 — Advisory: mark, notify, date

For advisory deprecations:

1. Add a deprecation notice to the interface: what it is, what to use instead, when it will be removed. Use the language's canonical deprecation mechanism (`@deprecated` annotation, `DeprecationWarning`, documentation flag).
2. Add a log warning on each invocation so callers see the notice in production.
3. Set a published removal date. Without a date, the deprecation window is infinite.
4. Update the public changelog and notify downstream consumers through your standard communication channel.

### Step 4 — Zombie check (advisory removal)

For advisory deprecations, before removing the code at the end of the deprecation window:

1. `grep -r "function_name" .` — are there callers that adopted the interface during the deprecation window?
2. Run the test suite with the code removed (in a temporary local change). If tests pass, the code is truly dead.
3. If tests pass and no callers exist: remove the code and proceed to Step 5. If tests fail: new callers exist — extend the deprecation window, notify the callers you found, and do not remove yet.

### Step 5 — Verify and commit

- Full test suite green with the deprecated code removed (compulsory) or with the deprecation notice in place (advisory).
- No remaining references to the removed symbol (compulsory only).
- Removal date is published (advisory only).
- CHANGELOG entry for the deprecation or removal.

## Common Rationalizations

| Excuse | Why it's wrong |
|---|---|
| "I'll add a removal date later." | A deprecation without a removal date is a permanent commitment to maintain the interface. "Later" is not a date. Set the date now or do not call it a deprecation. |
| "I think this code is dead — I'll just remove it." | "I think" is not a Beyonce Rule audit. Grep for callers, remove the code temporarily, run the tests. If nothing fails and no callers exist, then you know. |
| "It's advisory but I'll treat it as compulsory — I can't find any external callers." | Not finding external callers is not the same as there being none. If the interface is published, treat it as advisory until you have affirmative evidence otherwise. |

## Red Flags

- A deprecated interface with no removal date.
- Code removed without a full test run on the removal (green tests are the Beyonce Rule check).
- An advisory deprecation with no changelog entry and no consumer notification.
- A "compulsory" deprecation that breaks a downstream service after merge — a caller you thought you controlled turned out to be external.
- Zombie code removed on intuition rather than a grep + test verification.

## Verification checklist

- [ ] Deprecation classified: compulsory or advisory.
- [ ] Compulsory: every caller updated or removed; full grep confirms no remaining references; tests green.
- [ ] Advisory: deprecation notice on the interface; log warning on each invocation; removal date published; changelog updated.
- [ ] Beyonce Rule applied before any deletion: grep for callers + test suite run confirms dead code is actually dead.
- [ ] No code removed on intuition — every removal is verified by an executable check.
