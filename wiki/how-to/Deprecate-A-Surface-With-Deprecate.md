# How to deprecate or remove code with /deprecate

> [!IMPORTANT]
> **Status: implemented** — shipped in `src/developer-workflows/commands/deprecate.md` (v0.1.0).

> [!NOTE]
> **Goal:** Walk a code surface (API, module, flag, or internal abstraction) through the full deprecation lifecycle — classify compulsory vs advisory, execute removal or write a migration path, and delete zombie code — using the `/deprecate` command.
> **Prereqs:** the `developer-workflows` plugin installed at a version that ships `/deprecate` ([Install crickets plugins](Install-Into-Project)); a named target surface to deprecate (the argument is required; `/deprecate` without a target is an error).

`/deprecate` encodes a code-as-liability mindset. It first classifies the deprecation:

- **Compulsory** — you control all callers; remove now, no migration path needed.
- **Advisory** — external or unknown callers; write a migration path first, then schedule removal.

Zombie code removal (code that is dead but never explicitly removed) is enforced via the Beyonce Rule: if it would break on removal, it should have had a test.

## Steps

1. Invoke the command with the surface to deprecate. The argument is required — `/deprecate` without a target is an error:

   ```text
   /deprecate <interface-or-module-or-function>
   ```

   The command begins by classifying the deprecation before touching anything ([`deprecate.md` lines 53–54](../src/developer-workflows/commands/deprecate.md)).

2. Classify: run a grep and type-check to enumerate every caller. If all callers are in the same repo and under your control, the deprecation is **compulsory** — remove now, no migration path needed. If any caller is external (published API, downstream service, open-source consumer), it is **advisory** — a migration path and removal date are required before you touch the interface ([`deprecate.md` lines 37–43](../src/developer-workflows/commands/deprecate.md)).

3. For **compulsory** deprecations — update or remove every caller, delete the deprecated interface, run the full test suite. If a test fails, it found a caller you missed; fix it, do not skip it. Confirm no remaining references with `grep -r "deprecated_symbol" .` ([`deprecate.md` lines 58–64](../src/developer-workflows/commands/deprecate.md)).

4. For **advisory** deprecations — add a deprecation notice to the interface using the language's canonical mechanism (`@deprecated`, `DeprecationWarning`, etc.), add a log warning on each invocation so callers see the notice in production, set a published removal date (no date = infinite maintenance commitment), and update the public changelog ([`deprecate.md` lines 66–73](../src/developer-workflows/commands/deprecate.md)).

5. Apply the Beyonce Rule before removing any code ([`deprecate.md` lines 44–48](../src/developer-workflows/commands/deprecate.md)):

   ```bash
   grep -r "function_name" .           # are there callers you missed?
   # temporarily remove the code locally, then:
   # run the full test suite
   ```

   If tests pass and no callers exist, the code is confirmed dead — remove it. If tests fail, the code has real callers — return to step 3.

## Verify

Confirm the five-item checklist from [`deprecate.md` lines 106–111](../src/developer-workflows/commands/deprecate.md) before committing:

- Deprecation classified: compulsory or advisory.
- Compulsory: every caller updated or removed; full grep confirms no remaining references; tests green.
- Advisory: deprecation notice on the interface; log warning on each invocation; removal date published; changelog updated.
- Beyonce Rule applied before any deletion: grep for callers and test suite run confirm dead code is actually dead.
- No code removed on intuition — every removal is verified by an executable check.

## Troubleshooting

The command flags common rationalizations as red flags ([`deprecate.md` lines 97–103](../src/developer-workflows/commands/deprecate.md)):

| Symptom | Cause | Fix |
|---|---|---|
| Downstream service breaks after merge | Treated advisory deprecation as compulsory | Classify first — if the interface is published, it is advisory until you have affirmative evidence of all callers |
| Deprecated interface still in production a year later | No removal date was set | Set a concrete removal date now; a deprecation without a date is a permanent maintenance commitment |
| Zombie code removed but tests still pass (unexpectedly) | Behavior was uncovered | The Beyonce Rule: if tests pass after removing it, the behavior had no test — confirm intent before deleting |

## See also

- [Developer Workflows plugin](Developer-Workflows) — the plugin that ships `/deprecate`.
- [How to document a decision with /document-decision](Record-An-Architectural-Decision) — if the deprecation implies a design decision, record it.
