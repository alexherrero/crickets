---
name: bugfix
description: "Bug triage pipeline — Report → Analyze → Fix → Verify. Use instead of /plan + /work for defects."
---

**Usage:** `/bugfix <bug report, issue link, or reproduction steps>`

You are running the **bugfix** pipeline of the developer-workflows loop. Bugs have different failure modes than features — root cause vs. symptom, reproduction-is-half-the-work, mandatory regression tests — so they get a dedicated pipeline, **not** `/plan` + `/work` (which lets the discipline lapse).

**Bug report from user:** <what the user typed after /bugfix>

> **Recommended model for this phase:** `opusplan` — Opus 5.5 plans, Sonnet 5.5 executes the long autonomous stretch. Override with `/model` if needed.

## Recoverability gate

Invoking this phase **authorizes** finishing it. The stop-gate is **recoverability, not destructiveness or blast-radius**: recoverable actions (push, tag, release, PR merge, close-out) are **announced and proceed**; unrecoverable ones (force-push over published shared history, sole-ref delete of unmerged work, published-tag overwrite, immutable deploy or migration) **stop and confirm**; an unresolved decision stops and asks. When uncertain, treat as unrecoverable. Unchanged: worktree spawns need operator authority, the PII hook and `pii-scrubber` stay mandatory, the no-`Co-Authored-By` rule holds. Full doctrine: the `recoverability` skill.

## Non-negotiables

- **Regression test is mandatory.** No test, no fix. If you can't write a failing test, you don't understand the bug yet — go back to Analyze.
- **Root cause before fix.** Ask "why" at least three times — the first suspicious line is usually the symptom, not the cause.
- **`/build-it --check` on every bugfix.** Bugs are evidence of code you already got wrong once — fresh skeptical eyes matter more, not less.
- **Minimal scope.** Fix the bug, not adjacent issues. "While I'm in here" turns a one-line fix into a regression.
- **`gh issue *` runs under the recoverability gate.** `gh issue create` / `comment` / `close` are recoverable (editable, reopenable) → **announce + proceed**, no preview-and-ask wait; the issue is still the bug's posterity record. Graceful-skip the whole issue track if `gh` is unavailable, the origin isn't GitHub, or the user opts out (then the resolved plan alone is the record; note the skip in `## Report`).
- **Do not create tags.** Tag creation is reserved for `/release` — the sole tag writer that tags `main` HEAD after CI-green. Creating a tag during `/bugfix` would point to a branch tip, not a main commit, violating the tag-reachability guarantee and the concurrent-release serialization model.

## Four phases, in order

### 1. Report

**Resolve the plan first**, never re-deriving its path: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py"` with no name gives, inside a plan's worktree, the plan its `.harness/active-plan` marker binds, and in a repo with no vault the repo-local singleton agentm keeps in `.harness/`. It prints `<plan>\t<progress>\t<tracker>`. Where it exits **4** (a project that keeps its plans in numbered tasks, so there is no singleton), propose a verb-first task name for the bug (e.g. `fix-login-redirect`), confirm it with the operator, and resolve again with that name, as `/plan` does. Any other non-zero exit is a hard stop.

**Before writing, check the plan isn't in flight:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/plan_tracker.py" status --plan <plan> --tracker <tracker>`. `queued`, `active` or `parked` means work is in flight in that plan, so ask the operator before adding a bug report to it.

Then capture the bug **verbatim** in the resolved plan under `## Report` — original text, source, reporter, date, reproduction steps, expected vs. actual, environment. Do not paraphrase; specifics matter for reproducing. If the report is unclear ("login is broken"), **interview** before moving on.

Then **open the tracking issue** (graceful-skip): announce a one-sentence title + body (verbatim quote + source/date + reproduction steps), then run `gh issue create --label bug` (recoverable → announce + proceed). Record `**Tracking:** #N` near the top of the plan; reference `#N` in the fix commit.

### 2. Analyze

Find the **root cause**, not the first plausible one.
- **Reproduce locally.** Can't reproduce? Note whether it's environment-specific, flaky (investigate timing/state), or not real.
- **Seed a starting hypothesis set from the shared `/diagnose` engine (additive, mechanized, runs before the explorer dispatch below).** Check availability: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agentm_bridge.py" capability diagnostics`. **Exit 0** → run `python3 "$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sibling_plugin.py" diagnostics scripts/diagnose.py)" --project <slug> <reproduction-traceback-file>` against the reproduction traceback captured above. On `outcome == "layer1_hit"`, fold the returned `path` + `namespace` into `## Analysis` as a starting hypothesis — a prior matching failure-incident is already on file. On `outcome == "written"` (cold start — no prior incident), fold the returned `hypotheses` in instead; this is a graceful no-op, never an error, and never blocks the manual flow below. **Exit 1** (diagnostics unavailable) → skip silently, proceed with an empty hypothesis seed. **`/diagnose` ranks hypotheses; it does not conclude root cause** — this seed is additive context for the passes below, never a replacement for them.
- **Read the code paths** — dispatch the `explorer` sub-agent on model `sonnet` for unfamiliar areas.
- **Ask "why" three times** — the function threw → why? → input malformed → why? → the validator's regex was wrong.
- **Note load-bearing assumptions** — what else depends on the broken behavior working as it currently does?

Write findings under `## Analysis` (Reproduction / Root cause `file:line` / Why it happened / Scope / Fix strategy) — the `/diagnose` hypothesis seed and the explorer's read informs this, but the "why three times" root-cause narrative is still a human/LLM reasoning pass, not a mechanized conclusion. If the root cause is actually a **design flaw**, **stop** and escalate to `/plan` — patching a symptom of a design flaw creates two bugs. Post the Analysis to the tracking issue as a comment (announce + proceed; skip silently if no issue).

### 3. Fix

**Isolation check (operator-authority-gated):** if `.harness/project.json` has `isolation.mode: worktree-per-plan` (durable operator opt-in), run:
```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/isolation_config.py" check [--project-root <root>]
```
Exit 0 → auto-spawn a worktree via the host's own primitive (`EnterWorktree` on Claude Code, name = the bug's slug; Antigravity: New-Worktree-Mode / `invoke_subagent`), then bind it — `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/worktree_marker.py" write <worktree-path> <slug> <plan-path> --project-root <original-root>` — announce the spawn, proceed from inside the new worktree (exit 3 from the bind step: already shipped, exit the worktree and stop; exit 2: surface stderr, exit the worktree, stop). Exit 1 → no worktree needed (single-owner guard or mode=direct). Silently skip this check when `CLAUDE_PLUGIN_ROOT` is unset.

Implement under `/work` discipline, plus two bugfix rules:
- **Regression test first** — it fails against the current code and passes after the fix.
- **Minimal scope** — adjacent issues go on the backlog, not in this fix.

Done when: the regression test passes, pre-existing tests still pass, deterministic gates are green. Post a Fix summary (commit SHA, regression test path + one-line description, files changed, gate results) to the issue (announce + proceed).

### 4. Verify

Run **`/build-it --check <the fix's commit range>`** on the fix (non-negotiable for bugs): its correctness pass reviews the change from a fresh context and reports; it never fixes. Confirm: the regression test is committed and **actually exercises the root cause** (not just the symptom); the original reproduction steps from `## Report` now produce the expected behavior. Docs are not part of the fix: when it reveals a durable gotcha, run `wiki-author` to record it.

Post a Verify summary to the issue, then run `gh issue close --reason completed` with a one-line note referencing the fix SHA (recoverable — a closed issue reopens; announce + proceed). The closed issue is the bug's record; nothing is posted to a project board. Append to the resolved `progress.md`:

```
<YYYY-MM-DD HH:MM> /bugfix — fixed <one-line> (tracking: #N, root cause: <summary>, regression test: <path>)
```

## Output

```
Bug fixed: "<one-line summary>"
- Root cause: <file:line> — <one-sentence why>
- Fix: <one sentence, not the diff>
- Regression test: <path>, fails without the fix, passes with it
- /build-it --check outcome: <clean | N findings addressed>
- Original reproduction (from Report) no longer reproduces
Next: `/release` if this was the only thing in flight, else `/work` or `/plan` for what's next.
```

## Failure modes to avoid

- **Paraphrasing the report** — specifics get lost; copy verbatim.
- **Jumping to the fix without Analysis** — three "whys" minimum.
- **Fixing the symptom, leaving the cause** — a design flaw dressed as a bug comes back; escalate to `/plan`.
- **No regression test** — non-negotiable; if you can't write one, you don't understand the bug yet.
- **Expanding scope** — adjacent issues go on the backlog.
- **Skipping `/build-it --check`** — the area already produced one bug; it deserves more scrutiny, not less.

## Common Rationalizations

| Excuse | Why it's wrong |
|---|---|
| "I'll add the regression test later" | Later never comes; the regression test is the proof the bug is fixed, not an optional add-on. |
| "The test was too strict, I loosened the assertion" | A looser assertion is not a fix — it is a hidden failure. Fix the implementation. |
| "I understand the root cause, I'll skip root-cause analysis" | Write it down; unstated assumptions become the next bug. |
