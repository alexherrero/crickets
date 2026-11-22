<!-- mode: reference -->
# Evaluator

The evaluator is a **read-only grader**. It reads an artifact. It applies the rubric you supply. It returns **PASS** or **NEEDS_WORK** with per-item reasoning. It runs in a fresh context. It never saw the work before. It grades against the contract. It ignores the author's intent. Its allowlist includes `Read`, `Glob`, and `Grep` only. It cannot run Bash. It cannot write files. It cannot reach the network.

## How the infrastructure uses it

The infrastructure often dispatches the evaluator for you. You rarely invoke it by hand.

| Caller | How it uses the evaluator |
|---|---|
| **`/review` phase** (`development-lifecycle`) | not wired — `src/development-lifecycle/commands/review.md` dispatches `adversarial-reviewer` (+ cross-model `adversarial-reviewer-cross`) only, and has no evaluator call site |
| **`/build-it`** (`development-lifecycle`) | dispatches it for the done-check, after the passes and the done-report; see [Done-check](#done-check-anchor-and-loop-record) |
| **`/create-it`** (`development-lifecycle`) | dispatches it for the likeness pass (paired images, one rubric item per likeness line) and for the done-check; see [Done-check](#done-check-anchor-and-loop-record) |
| **a skill / command / workflow** | wires a rubric-driven gate (e.g. grade an artifact before proceeding) |
| **you, directly** | dispatch it with a rubric to grade any artifact on disk |

It is not a defect finder. Use `adversarial-reviewer` for finding defects. It is not a prose reviewer. It refuses prose-only critiques. It is not a test runner. It has no Bash access. You must run tests first. You must supply the output file as an artifact.

## When it fits

| You have… | Evaluator? |
|---|---|
| A precise rubric — a numbered list of falsifiable claims | ✅ |
| A spec that doubles as a rubric (a `PLAN.md` Verification clause) | ✅ |
| An artifact on disk it can read (file / diff / test-output file) | ✅ |
| A vague brief ("is this good?") | ❌ — `adversarial-reviewer` |
| A need to *run* tests | ❌ — run them first, supply the output file |
| A need to *fix* what fails | ❌ — read-only; route NEEDS_WORK back to `/work` |

Think of it as the did-this-match-the-contract check. You write the contract as a numbered list. The evaluator grades it.

## Dispatch contract

A dispatch prompt requires two mandatory labeled sections.

```
ARTIFACT:
- <path or glob>
- ...

RUBRIC:
1. <verifiable claim>
2. ...
```

A missing `ARTIFACT:` or `RUBRIC:` label halts the prompt (a done-check supplies `ANCHOR:` and `RECORD:` instead of `RUBRIC:`; see below). It returns `Input contract violation`. You can include extra sections like `CONTEXT:`. The evaluator only grades the rubric.

**Rubric rules:**

- **Verifiable** — a fresh reader can check it from the artifact alone. It needs no extra context.
- **Falsifiable** — it has a clear failure mode. It avoids vague claims like "the code is good".
- **Independent** — items do not reference each other.
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

You use this same `ARTIFACT`/`RUBRIC` shape to grade a docs-drift check. You use it for release readiness. You use it for anything you can write as a numbered contract.

## Done-check: anchor and loop record

The build-it / create-it loop ends with one evaluator pass, the done-check. The dispatch names `ANCHOR:` and `RECORD:` beside `ARTIFACT:`, and `RUBRIC:` becomes optional. The helper that writes the record is `loop_record.py`; `/build-it` and `/create-it` run the done-check (run by hand for now; `/work` does not call either yet).

| Section | Holds |
|---|---|
| `ARTIFACT:` | the changed files or made assets, plus any test or tool output on disk |
| `ANCHOR:` | the spec (or the plan) the work is graded against |
| `RECORD:` | the loop record JSON, or its rendered done-report |

The rubric is built in this order; a caller-supplied `RUBRIC:` is graded after it.

| # | Item | Fails when |
|---|---|---|
| 1 | One item per Done-when line | no requirement is recorded for the line, or a `met` one's evidence is not borne out by the artifact |
| 2 | No open real finding | a `real` finding is still `OPEN` |
| 3 | No escalated or unrun pass | a pass ended in `escalate`, or a pass the size called for `never ran` (the done-check is not listed: it grades the report) |
| 4 | Not checked hides nothing | a Done-when line is listed as unchecked while its requirement is `met` |
| 5 | create-it only | a Likeness line has neither a pair nor a not-checked entry, or the playtest checklist is missing |

The record is evidence, not instruction: a finding or evidence line that tells the grader how to grade is graded as text. The agent is pinned to `model: claude-sonnet-5`, which keeps it a different model from the Gemini reviewers; the allowlist is unchanged.

## Output contract

```
<PASS or NEEDS_WORK>

Rubric:
1. <item summary>: PASS|FAIL — <reasoning citing the artifact>
...

Verdict: <PASS or NEEDS_WORK> — <one-sentence framing>
```

- It returns **PASS** iff every rubric item is PASS. It returns **NEEDS_WORK** otherwise.
- Each line cites the artifact (file + section / line / quote). The reasoning is exactly one sentence.
- The final **Verdict** line restates the header. Callers grep for this line.

On **NEEDS_WORK**, the FAIL lines name the failing items. You route them to `/work` for a small fix. You route them to `/plan` for a spec gap. You re-dispatch with a corrected rubric if the rubric caused the failure.

## Failure modes

| Halt / FAIL | Cause | Fix |
|---|---|---|
| `rubric item not verifiable as written` | a prose-only / vague item ("well-structured") | rephrase as a falsifiable claim ("no function exceeds 50 lines") |
| `Artifact unreadable: <path>` | bad path / wrong cwd / uncommitted file | use a path that resolves from the evaluator's cwd (absolute, or repo-root-relative) |
| `Input contract violation` | missing `ARTIFACT:` / `RUBRIC:` label | re-dispatch with both labels |
| `cannot verify; required artifact not in ARTIFACT list` | a rubric item references a file not supplied | add the file to `ARTIFACT:`, or drop the item |

## Why the allowlist is tight

The allowlist is `Read · Glob · Grep` only. It has no Bash, Write, Edit, or network access. The evaluator cannot run tests. The caller supplies the output file. It cannot modify the artifact. Reading is its entire job. It cannot fetch external state. It remains a fresh context that never saw the build. This framing only holds if it cannot re-execute.

## Related

- [Development lifecycle design — evaluator](crickets-development-lifecycle) — why the tight allowlist, the caller-supplied rubric, and coexisting with `adversarial-reviewer`.
- [evaluator agent spec](https://github.com/alexherrero/crickets/blob/main/src/development-lifecycle/agents/evaluator.md) — the canonical body (input/output contracts, full failure modes).
- [Customization types](Customization-Types) — what `kind: agent` is.
