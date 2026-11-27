---
name: build-it
description: "Build a piece of code against its anchor and prove it is done: anchor, size, direction check, make, the repo's own checks, correctness then simplicity review passes, a done-report. `--check <PR, range or diff>` runs the passes and report on a change someone already made. Use for any code task, or let /work call it."
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.1
argument-hint: <task, or a plan step>  |  --spec <file>  |  --size small|medium|large  |  --check <PR number | A..B | diff file>
---

You are running **build-it**: the whole loop for code, in one place. `/work` calls it for each step; you can also run it on a task by hand. The loop is: **anchor → size → direction → make → free checks → focused passes → done-report.**

**Task from the user:** $ARGUMENTS

> **Recommended model:** Sonnet 5.5 (`claude-sonnet-5-5`) for the making. The reviewers below pick their own models; you never choose them by hand.

Judgment is yours: what the task needs, how big it is, what a finding means, what to fix. Everything a script can settle is one of these helpers, and you call them rather than redo them:

| Helper | Where | Does |
|---|---|---|
| `spec_doc.py` | this plugin's `scripts/` | where a spec goes, whether it is well formed |
| `loop_record.py` | this plugin's `scripts/` | the passes to run, each round's findings, when a pass stops, the done-report |
| `review_material.py`, `cross-review.sh` | the `code-review` plugin | what a reviewer is shown; the cross-model review itself |

Reach the `code-review` scripts with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sibling_plugin.py" code-review scripts/review_material.py` and the same call for `scripts/cross-review.sh`; each prints the path to run. **Exit 1** means `code-review` is not installed: carry on with the fallback in step 6, and say so. None of this needs agentm or a vault.

## Process

### 0. Set up

Slug: a short name for the task. The record lives beside the spec: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spec_doc.py" place --slug <slug> --plan <plan.md>` prints where the spec goes (add `--project-root <repo>` when there is no plan); the record is `loop-<slug>.json` in that same folder. Scratch files (review material, the approach note) go in `${TMPDIR:-/tmp}/build-it-<slug>/`.

**The design.** `review_material.py` finds the repo's own governing designs (`wiki/designs/`, by their `governs:`) by itself. A living design kept in the vault is passed in: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vault_designs.py" find <a path the task changes> --cwd <repo>`; on exit 0, add `--design <the path it prints>` to every `review_material.py` call. On exit 1 or 3 there is none to add.

With `--check`, jump to **Check mode** at the end.

### 1. Anchor

The anchor is what the work is graded against. In order: `--spec <file>`; the spec the plan step links or that sits beside the plan; otherwise run **`/spec`** and let the operator approve it once. In a run with no human (a spawned worker, `/loop`), `/spec` cannot ask: use the plan step and the plan's Locked design calls as the anchor, and say that you did. Run `spec_doc.py check <spec>` first; a spec that does not pass is fixed before anything is built.

### 2. Size

Decide it and state it in one line, with the reason. **small**: a few lines in one place, no new behaviour (a typo, a rename, a config value). **medium**: one feature or fix across a few files. **large**: a new module, a changed contract, data or migration work, or roughly 300 changed lines or 8 files. `--size` overrides you. Then:

`loop_record.py init --record <record> --profile build --size <size> [--security]`

Add `--security` when the task touches auth, secrets, shell execution or network input. `loop_record.py passes --profile build --size <size>` shows the order it will run: small runs no review at all.

### 3. Direction check (medium and large)

Before writing code, write the approach in at most 10 lines: the files you will change and what each change does. Write what you will do, not why you think it is right. Save it as `approach.md` in the scratch folder, then:

`review_material.py --files approach.md --contract-file <spec> --anchor <spec> --tier high` piped into `cross-review.sh --tier high`

The reviewer says whether the approach would satisfy the anchor. Sort each finding (step 6's classes), record it (`open-round`, `add`) under the pass `direction`. Then tell the two kinds of real finding apart:

- **A wrong direction** says the approach would not meet the anchor: the wrong files, the wrong mechanism, a Done-when line it cannot reach. **Stop and ask the operator**, even in the middle of `/work`: revise the approach, go ahead anyway, or stop.
- **A detail** is a mistake inside an approach that otherwise stands: an edge case it misses, two steps in the wrong order. Correct the approach, dispose the finding, and open the next direction round. No stop.

Do not start making until the direction is settled. `loop_record.py stop --pass direction` says when this check is done; at `escalate` the operator decides. When the operator goes ahead with a real finding still standing, record their words with `loop_record.py decide --record <record> --pass direction --decision "<what they decided>"`.

### 4. Make

Build it. Stay inside the spec: its Not doing is a hard edge, and an Open question that blocks you is a stop, not a guess. Tests first when the repo works that way. If the change grows past the size you stated, say so and re-size before going on.

When the diff exists, look at it once for security triggers. If it touches auth, secrets, shell execution or network input and the record has no security pass, `loop_record.py add-security --record <record>`.

### 5. Free checks

Run the repo's own checks (the commands in `AGENTS.md`, `init.sh`, or the CI config): tests, linters, type checks, build. **They pass before any reviewer is called.** A reviewer's time is never spent on something a script would have caught. For each Done-when line in the spec, once you have seen it hold, record it with the evidence you saw (a test name, a command and its exit code, a line number):

`loop_record.py requirement --record <record> --text "<the Done-when line>" --status met --evidence "<what you saw>"`

A line that does not hold is recorded `--status not-met` with what you saw, not hidden. Anything you could not run goes in with `loop_record.py not-checked --record <record> --text "<what and why>"`.

A small task stops here: skip to step 7.

### 6. Focused passes

Run each pass in the order `loop_record.py passes` printed after `direction`: `correctness`, then `simplicity`, and `security` when it is in the record. **One at a time, never in parallel.**

For one pass, a round is:

1. `loop_record.py open-round --record <record> --pass <name>`.
2. Build the material: `review_material.py --worktree --contract-file <spec> --anchor <spec> --tier <tier>` (use `--range <base>..HEAD` once the work is committed). The tier is the one `passes` gave: `high` for correctness on a large task, `default` otherwise. The material is the change, what it was for and the rules it is held to; never your reasoning, and never your guess at the bug.
3. Pipe it into `cross-review.sh --tier <tier>`. The answer is a failing test, a `DEFECT file:line`, or `NO ISSUES FOUND`.
4. Sort every finding and record it with its cited line: `loop_record.py add --record <record> --pass <name> --class <class> --line <path:LINE> --text "<finding>"`. **real** is a defect you can show with a case that fails; **tradeoff** is a real cost the spec accepts (its Rules or Not doing say so); **misread** is a reviewer that misunderstood the code or the rule (check the line before saying so); **noise** is true and not worth acting on. A finding you cannot tie to a line is not recorded as real.
   In the correctness pass, a behaviour change with no test that would catch its regression is a real finding, whether or not the reviewer named it.
5. Fix every real finding, re-run the free checks, and note what you did: `loop_record.py dispose ...`.
6. `loop_record.py stop --record <record> --pass <name>`: **done** moves to the next pass; **continue** opens another round; **escalate** (exit 3, a real finding still standing in round 3) stops everything and hands the operator the open findings to decide. When they decide (accept the round-3 fix, say, or go on without one), record it with `loop_record.py decide --record <record> --pass <name> --decision "<what they decided>"`; the pass then reads `decided` and the done-check accepts it.

If `cross-review.sh` prints a `CROSS-REVIEW-DEGRADED:` line, or the `code-review` scripts are absent, say so in one line, then run that pass with a fresh read-only reviewer on model sonnet, given the same material: the `adversarial-reviewer` agent when installed, otherwise a plain read-only agent told to find defects and to answer with a failing test, a `DEFECT file:line` or `NO ISSUES FOUND`. Use model opus only for a large task's direction check. The same rounds apply.

The `security` pass is a dispatch of the `security-auditor` agent (model sonnet) over the diff and the spec's Rules; record its findings the same way. If that agent is not installed, record `not-checked` for it.

If `loop_record.py status` flags doubt theater (two or more rounds brought findings and none was real), say so in the report rather than running more rounds.

### 7. Done-report

`loop_record.py report --record <record>` prints the report: requirements met or not with evidence, every finding with what was done about it, and a Not checked list. Then the done-check: dispatch the `evaluator` agent (it runs on model sonnet) with the changed files under `ARTIFACT:`, the spec under `ANCHOR:` and the record or the printed report under `RECORD:`. It grades PASS or NEEDS_WORK. On NEEDS_WORK, fix what it names, record it as a round of `done-check`, and ask again; the same three-round limit applies.

Show the operator the report and the verdict. State plainly what was not checked. Never write "done" over a NOT MET requirement or an OPEN finding.

## Check mode: `--check <PR number | A..B | diff file>`

Reviews a change someone already made. It never edits the code and never fixes: it only reports. Skip steps 3 and 4; there is no direction check and no make.

1. **Anchor.** A spec beside the plan if one exists; else the PR description or commit messages are the contract and the anchor is the repo's own `AGENTS.md` rules. Say which. A missing anchor gives an empty RULES block with the reason, and that is stated in the report.
2. **Size** from the diff, as in step 2, then `loop_record.py init`.
3. **Free checks.** Run what can be run at that revision; what cannot goes in `not-checked`.
4. **Passes**, one round each, material from `review_material.py --pr <N>`, `--range <A..B>` or `--files <diff file>`. Sort and record every finding. No fix loop: a real finding stays OPEN in the report.
5. **Report** (step 7's `report`; the done-check is optional here).

## Verification

- [ ] `spec_doc.py check` passes on the anchor, or the report says there was no spec.
- [ ] Free checks passed before the first reviewer ran.
- [ ] Each pass ran one round at least, sequentially, and ended `done` or was handed to the operator.
- [ ] Every finding has a class and a cited line; every real one has a disposition.
- [ ] The report lists what was not checked, and the done-check verdict is shown with it.
