<!-- mode: reference -->
# Evaluator

A **read-only grader** sub-agent: it reads an artifact, applies an explicit rubric, and returns **PASS** or **NEEDS_WORK** with per-item reasoning. It runs in a fresh context that never saw the work, so it grades against the contract, not the author's intent. Tool allowlist `Read · Glob · Grep` only — no Bash, no writes, no network.

## How the infrastructure uses it

The evaluator is dispatched *for* you — you rarely invoke it by hand:

| Caller | How it uses the evaluator |
|---|---|
| **`/review` phase** (`developer-workflows`) | dispatches it alongside `adversarial-reviewer` — the reviewer finds bugs, the evaluator grades against the `PLAN.md` Verification clause; their outputs combine |
| **a skill / command / workflow** | wires a rubric-driven gate (e.g. grade an artifact before proceeding) |
| **you, directly** | dispatch it with a rubric to grade any artifact on disk |

It is **not** a defect finder (use `adversarial-reviewer`), a prose reviewer (it refuses prose-only critiques), or a test runner (no Bash — run tests first, supply the output file as an artifact).

## When it fits

| You have… | Evaluator? |
|---|---|
| A precise rubric — a numbered list of falsifiable claims | ✅ |
| A spec that doubles as a rubric (a `PLAN.md` Verification clause) | ✅ |
| An artifact on disk it can read (file / diff / test-output file) | ✅ |
| A vague brief ("is this good?") | ❌ — `adversarial-reviewer` |
| A need to *run* tests | ❌ — run them first, supply the output file |
| A need to *fix* what fails | ❌ — read-only; route NEEDS_WORK back to `/work` |

Mental model: the "did this match the contract?" check. If you can write the contract as a numbered list, the evaluator can grade it.

## Dispatch contract

A dispatch prompt has two mandatory labeled sections:

```
ARTIFACT:
- <path or glob>
- ...

RUBRIC:
1. <verifiable claim>
2. ...
```

A missing `ARTIFACT:` or `RUBRIC:` label halts with `Input contract violation`. Extra sections (e.g. `CONTEXT:`) are allowed, but only the rubric is graded.

**Rubric rules:**

- **Verifiable** — a fresh reader can check it from the artifact alone, without your context.
- **Falsifiable** — has a clear failure mode (not "the code is good").
- **Independent** — items don't reference each other.
- **Numbered** — the output mirrors the numbering 1:1.

**Worked example** — a `/review` code-change rubric:

```
ARTIFACT:
- src/parser.py
- tests/test_parser.py
- spec/parser-spec.md

RUBRIC:
1. Every acceptance criterion in spec/parser-spec.md §"Acceptance" has a matching test (criterion → test name).
2. The edge cases in §"Edge cases" are covered by tests with descriptive names.
3. No tests are skipped (no @skip / .skip() in the diff).
4. No print() / breakpoint() / debug-log remains in src/parser.py.
```

The same `ARTIFACT`/`RUBRIC` shape grades a docs-drift check, release readiness, or anything you can write as a numbered contract.

## Output contract

```
<PASS or NEEDS_WORK>

Rubric:
1. <item summary>: PASS|FAIL — <reasoning citing the artifact>
...

Verdict: <PASS or NEEDS_WORK> — <one-sentence framing>
```

- **PASS** iff every rubric item is PASS; otherwise **NEEDS_WORK**.
- Each line cites the artifact (file + section / line / quote); reasoning is one sentence.
- The final **Verdict** line restates the header — what callers grep for.

On NEEDS_WORK the FAIL lines name the failing items; route to `/work` (small fix), `/plan` (a spec gap), or re-dispatch with a corrected rubric (if the rubric was the problem).

## Failure modes

| Halt / FAIL | Cause | Fix |
|---|---|---|
| `rubric item not verifiable as written` | a prose-only / vague item ("well-structured") | rephrase as a falsifiable claim ("no function exceeds 50 lines") |
| `Artifact unreadable: <path>` | bad path / wrong cwd / uncommitted file | use a path that resolves from the evaluator's cwd (absolute, or repo-root-relative) |
| `Input contract violation` | missing `ARTIFACT:` / `RUBRIC:` label | re-dispatch with both labels |
| `cannot verify; required artifact not in ARTIFACT list` | a rubric item references a file not supplied | add the file to `ARTIFACT:`, or drop the item |

## Why the allowlist is tight

`Read · Glob · Grep` only — no Bash, Write, Edit, or network. The evaluator can't run tests (the caller supplies the output file), can't modify the artifact (reading is the whole job), and can't fetch external state. The "fresh context that never saw the build" framing only holds if it can't re-execute.

## Related

- [ADR 0002 — evaluator design](crickets-development-lifecycle) — why the tight allowlist, the caller-supplied rubric, and coexisting with `adversarial-reviewer`.
- [evaluator agent spec](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/agents/evaluator.md) — the canonical body (input/output contracts, full failure modes).
- [Customization types](Customization-Types) — what `kind: agent` is.
