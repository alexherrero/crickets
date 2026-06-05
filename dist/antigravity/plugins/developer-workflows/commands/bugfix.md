---
name: bugfix
description: Bug triage pipeline — Report → Analyze → Fix → Verify. Use instead of /plan + /work for defects.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: <bug report, issue link, or reproduction steps>
---

You are running the **bugfix** pipeline of the developer-workflows loop. Bugs have different failure modes than features — root cause vs. symptom, reproduction-is-half-the-work, mandatory regression tests — so they get a dedicated pipeline, **not** `/plan` + `/work` (which lets the discipline lapse).

**Bug report from user:** $ARGUMENTS

## Non-negotiables

- **Regression test is mandatory.** No test, no fix. If you can't write a failing test, you don't understand the bug yet — go back to Analyze.
- **Root cause before fix.** Ask "why" at least three times — the first suspicious line is usually the symptom, not the cause.
- **`/review` on every bugfix.** Bugs are evidence of code you already got wrong once — fresh skeptical eyes matter more, not less.
- **Minimal scope.** Fix the bug, not adjacent issues. "While I'm in here" turns a one-line fix into a regression.
- **Every `gh issue *` is preview-and-ask.** No silent automation — the issue is the bug's posterity record. Graceful-skip the whole issue track if `gh` is unavailable, the origin isn't GitHub, or the user opts out (then `.harness/PLAN.md` alone is the record; note the skip in `## Report`).

## Four phases, in order

### 1. Report

Capture the bug **verbatim** in `.harness/PLAN.md` under `## Report` — original text, source, reporter, date, reproduction steps, expected vs. actual, environment. Do not paraphrase; specifics matter for reproducing. If the report is unclear ("login is broken"), **interview** before moving on.

Then **open the tracking issue** (graceful-skip): preview a one-sentence title + body (verbatim quote + source/date + reproduction steps), then `gh issue create --label bug` on confirmation. Record `**Tracking:** #N` near the top of PLAN.md; reference `#N` in the fix commit.

### 2. Analyze

Find the **root cause**, not the first plausible one.
- **Reproduce locally.** Can't reproduce? Note whether it's environment-specific, flaky (investigate timing/state), or not real.
- **Read the code paths** — dispatch the `explorer` sub-agent for unfamiliar areas.
- **Ask "why" three times** — the function threw → why? → input malformed → why? → the validator's regex was wrong.
- **Note load-bearing assumptions** — what else depends on the broken behavior working as it currently does?

Write findings under `## Analysis` (Reproduction / Root cause `file:line` / Why it happened / Scope / Fix strategy). If the root cause is actually a **design flaw**, **stop** and escalate to `/plan` — patching a symptom of a design flaw creates two bugs. Post the Analysis to the tracking issue as a comment (preview-and-ask; skip silently if no issue).

### 3. Fix

Implement under `/work` discipline, plus two bugfix rules:
- **Regression test first** — it fails against the current code and passes after the fix.
- **Minimal scope** — adjacent issues go on the backlog, not in this fix.

Done when: the regression test passes, pre-existing tests still pass, deterministic gates are green. Post a Fix summary (commit SHA, regression test path + one-line description, files changed, gate results) to the issue (preview-and-ask).

### 4. Verify

Run **`/review`** on the fix (non-negotiable for bugs). Confirm: the regression test is committed and **actually exercises the root cause** (not just the symptom); the original reproduction steps from `## Report` now produce the expected behavior. Probe with `bash "${CLAUDE_PLUGIN_ROOT}/scripts/capability_probe.py" wiki-maintenance`; on **exit 0** dispatch the `documenter` (**lightweight** — most bugfixes get `NO CHANGES`; it updates a Known-Issues page or adds an ADR **only** if the fix reveals a durable gotcha — over-documentation is drift too); on **exit 1** skip silently.

Post a Verify summary to the issue, then propose `gh issue close --reason completed` with a one-line note referencing the fix SHA. Append to `progress.md`:

```
<YYYY-MM-DD HH:MM> /bugfix — fixed <one-line> (tracking: #N, root cause: <summary>, regression test: <path>)
```

## Output

```
Bug fixed: "<one-line summary>"
- Root cause: <file:line> — <one-sentence why>
- Fix: <one sentence, not the diff>
- Regression test: <path>, fails without the fix, passes with it
- /review outcome: <clean | N findings addressed>
- Original reproduction (from Report) no longer reproduces
Next: `/release` if this was the only thing in flight, else `/work` or `/plan` for what's next.
```

## Failure modes to avoid

- **Paraphrasing the report** — specifics get lost; copy verbatim.
- **Jumping to the fix without Analysis** — three "whys" minimum.
- **Fixing the symptom, leaving the cause** — a design flaw dressed as a bug comes back; escalate to `/plan`.
- **No regression test** — non-negotiable; if you can't write one, you don't understand the bug yet.
- **Expanding scope** — adjacent issues go on the backlog.
- **Skipping `/review`** — the area already produced one bug; it deserves more scrutiny, not less.
