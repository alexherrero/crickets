---
name: ci-cd
description: "CI/CD pipeline authoring discipline. Shift Left (move quality gates earlier, not later), Faster is Safer (faster pipeline = smaller diffs = less risk), quality gate pipeline (lint → typecheck → test → build → deploy — each gate blocks the next), failure feedback loops (CI failure → notification → fix → re-run, no 'ship anyway' bypass). Triggered when authoring or modifying a CI/CD pipeline."
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: <pipeline file, workflow, or CI config being authored or modified — required>
---

You are running **/ci-cd** — the pipeline authoring discipline for any CI/CD configuration you are writing or modifying.

**Target:** $ARGUMENTS — the pipeline file, workflow, or CI config. Required.

## When to Use

Run `/ci-cd`:

- When authoring a new CI/CD pipeline from scratch.
- When adding a new job, step, or gate to an existing pipeline.
- When modifying a quality gate (changing when it runs, what it checks, or what blocks it).
- When a pipeline is consistently slow and you are deciding what to cut or parallelize.

**Do NOT use** for routine app code changes that happen to touch a CI-related file (a test file, a build script). `/ci-cd` is for changes *to* the pipeline structure — what gates exist, what they check, and what order they run.

## Key Principles

### Shift Left

Move quality gates earlier in the pipeline, not later. A lint failure caught before a 10-minute test run wastes 10 minutes. A type error caught before a 30-minute build wastes 30 minutes. Every gate you move earlier reduces the cost of the failure it catches.

The ordering is: lint → typecheck → test → build → deploy. Each stage costs more than the one before it. Run cheap checks first.

### Faster Is Safer

A faster pipeline is not just more convenient — it is safer. A pipeline that takes 45 minutes encourages batching commits to amortize the wait. Batched commits mean larger diffs. Larger diffs are harder to review, harder to roll back, and more likely to contain multiple interacting failures.

A pipeline that takes 5 minutes encourages frequent, small commits. Small commits are easier to review, easier to roll back, and fail in isolation. Speed is a safety property, not a comfort feature. When pipeline speed degrades, treat it as a correctness issue.

### Quality Gates Block

Every gate in the pipeline must block the next stage on failure. A gate that reports a failure but lets the pipeline continue is not a gate — it is a log entry. If lint failures do not block the typecheck stage, and typecheck failures do not block the test stage, you are running a reporting pipeline, not a quality gate pipeline.

Gates in order: **lint → typecheck → test → build → deploy**. Each blocks the next. Nothing reaches deploy that has not cleared every earlier gate.

### Failure Feedback Loops

A CI failure must be fixed before anything else merges. The loop is: CI failure → notification to the committer → fix committed → re-run → green → merge unblocked. There is no "ship anyway" bypass. A red pipeline is not a speed bump; it is a stop sign.

A pipeline that allows merging on failure is a pipeline that will be ignored.

## The Process

### Step 1 — Read the existing pipeline

Read the full pipeline config before changing any part of it. Understand: what gates currently exist, what order they run, what each gate does, and what currently blocks the deploy. Do not add to a pipeline you have not fully read.

### Step 2 — Identify the gate order

Map the current gate order. If the pipeline does not run in lint → typecheck → test → build → deploy order, that is a Shift Left finding. Note what is out of order and what would move.

### Step 3 — Apply Shift Left

For each gate that is not in order:

1. Identify the gate's actual cost (approximate run time).
2. Identify the gate that should precede it by cost (cheaper gates run first).
3. Move the gate earlier. Confirm the earlier stage does not need artifacts the later stage produces — gates should be independent by design.

If two gates cannot be ordered by cost because they are independent, parallelize them (run them in the same stage). Parallelization reduces wall-clock time without reordering.

### Step 4 — Wire blocking

Confirm that every gate's failure blocks the next stage. In CI systems that use `continue-on-error` or `--no-fail-fast`, explicitly audit those flags. A gate with `continue-on-error: true` is a reporting step; treat it as one. Remove `continue-on-error` from quality gates unless you have an explicit, documented reason (e.g. an informational lint pass that is not yet required).

### Step 5 — Wire the failure feedback loop

Confirm the pipeline notifies the committer on failure. The notification must:

1. Identify the failing gate by name.
2. Link to the full log (not just the summary).
3. Reach the committer — not just a channel that gets ignored.

If the feedback loop is a Slack channel that nobody reads, it is not a feedback loop. The loop is closed only when the committer sees the failure and commits a fix.

### Step 6 — Measure pipeline speed

Time the pipeline on the current change. If the wall-clock time is over 10 minutes, identify the slowest gate. Ask: can this gate be parallelized? Can expensive integration tests move to a nightly run? Can the test suite be split? Speed targets: lint + typecheck under 2 minutes; unit tests under 5 minutes; full build + integration under 15 minutes. These are soft ceilings, not hard rules — but if you are significantly over them, treat it as a Shift Left issue: the slow gate is probably running after faster ones.

### Step 7 — Verify the pipeline

After any change:

1. Run the pipeline locally (or trigger a dry run) against a failing input — confirm the modified gate actually fails.
2. Run against a passing input — confirm the pipeline completes end-to-end.
3. Confirm the failure notification reaches the right place.
4. Confirm no gate has `continue-on-error: true` that should block.
5. Close the feedback loop end-to-end: commit a fix for the failure you triggered in step 1, re-run the pipeline, and confirm that the pipeline goes green and merge becomes unblocked. A loop that fires notifications but never unblocks on a fix is a broken loop.

## Common Rationalizations

| Excuse | Why it's wrong |
|---|---|
| "We'll speed up the pipeline later — it works now." | Every minute of pipeline time is friction on every commit. Slowness compounds: as the team grows, 45-minute pipelines cause batching, which causes larger diffs, which causes more failures. Fix it now, before it becomes load-bearing. |
| "We use `continue-on-error` because the gate is flaky, not because it's optional." | A flaky gate is a broken gate. Fix the flakiness, do not route around it. A gate that sometimes fails and sometimes passes without a code change is producing noise, not signal — remove it or fix it; do not mark it `continue-on-error` indefinitely. |
| "The failing test doesn't block merge because it's in a separate job." | Separate jobs are not exempt from the blocking rule. If the job finds real failures and does not block merge, it is a reporting step. Decide: does this job's output block merge? If yes, wire it to block. If no, remove it from the quality gate pipeline. |
| "We can't shift left — the expensive test is the first signal we have." | That means you have no cheaper signal. Add one: a fast unit test, a type check, a lint pass. The expensive test is not a first gate by design — it is a first gate by default because no faster gate exists yet. Build the faster gate. |

## Red Flags

- Lint runs after tests (Shift Left violation — lint should run first).
- Any gate has `continue-on-error: true` without a documented exception.
- Pipeline wall-clock time over 15 minutes without a parallelization plan.
- A CI failure notification that goes to a channel with no owner.
- A pipeline that can complete with a failing gate (blocking is not wired).
- A "ship anyway" merge path that bypasses a red gate.
- No gate exists between `git push` and deploy for the production branch.

## Verification checklist

- [ ] Gates run in order: lint → typecheck → test → build → deploy.
- [ ] Every gate blocks the next stage on failure — no `continue-on-error` on quality gates.
- [ ] CI failure notification reaches the committer (name + log link, not just a summary).
- [ ] Pipeline wall-clock time measured; gates parallelized where independent.
- [ ] No "ship anyway" bypass exists for a red gate.
- [ ] Failure feedback loop verified: triggered a failure, confirmed notification, confirmed re-run unblocked merge.
- [ ] Each gate verified on both a failing and a passing input.
