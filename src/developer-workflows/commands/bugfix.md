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

> **Recommended model for this phase:** Opus 4.8 (`claude-opus-4-8`) — strong model for autonomous task execution. Override with `/model` if needed.

<!-- BEGIN recoverability-gate · canonical · byte-identical across work.md · bugfix.md · release.md (scripts/ drift test enforces) -->
## Recoverability gate (autonomy doctrine)

Invoking this phase **is** the authorization to run it to completion. The stop-gate is **recoverability, not destructiveness or blast-radius**: a recoverable action proceeds (announced); only a genuinely unrecoverable one stops for confirmation.

| Class | Examples | Behavior |
|---|---|---|
| **Recoverable** | `git push` / `-u` / `HEAD:`; create + push a tag; `gh release create` (deletable); `gh pr merge` (revertable); `gh issue create` / `close`; force-push to your **own un-shared** worker branch; delete a branch whose tip is still reachable | **Announce + proceed** — no confirmation wait. |
| **Unrecoverable** | force-push rewriting **published shared** history; sole-ref delete of unmerged work; **published-tag** overwrite; immutable publish / deploy / migration | **Stop + confirm** — pre-announce (state, don't ask), then wait. |
| **Unresolved decision** | a genuine question the design/plan never settled | **Stop + ask** — and log it as a design/plan gap (an upstream phase missed it). |

**When uncertain, treat as unrecoverable** (conservative default). Pre-announcing a recoverable-but-destructive action — state what is about to happen; do not ask permission — carries over verbatim. Any summary this phase produces is a **record of what the autonomous run did**, not a stop-and-wait barrier.

**Close-out autonomy.** Archiving a completed plan (`PLAN.md` → `PLAN.archive.YYYYMMDD-<slug>.md`) and the rest of close-out bookkeeping (append `progress.md`, move the ROADMAP item to Completed/SHIPPED, update staging notes) is **recoverable → autonomous** — never stop to ask approval to archive or to do close-out bookkeeping.

**Carve-outs — unchanged by this doctrine.** Worker-tree initiation stays operator-initiated (`/spawn-worker` + `/integrate-worker`); the PII pre-push hook + `pii-scrubber` invocation stay mandatory; the no-`Co-Authored-By` commit rule is untouched.
<!-- END recoverability-gate -->

## Non-negotiables

- **Regression test is mandatory.** No test, no fix. If you can't write a failing test, you don't understand the bug yet — go back to Analyze.
- **Root cause before fix.** Ask "why" at least three times — the first suspicious line is usually the symptom, not the cause.
- **`/review` on every bugfix.** Bugs are evidence of code you already got wrong once — fresh skeptical eyes matter more, not less.
- **Minimal scope.** Fix the bug, not adjacent issues. "While I'm in here" turns a one-line fix into a regression.
- **`gh issue *` runs under the recoverability gate.** `gh issue create` / `comment` / `close` are recoverable (editable, reopenable) → **announce + proceed**, no preview-and-ask wait; the issue is still the bug's posterity record. Graceful-skip the whole issue track if `gh` is unavailable, the origin isn't GitHub, or the user opts out (then `.harness/PLAN.md` alone is the record; note the skip in `## Report`).

## Four phases, in order

### 1. Report

Capture the bug **verbatim** in `.harness/PLAN.md` under `## Report` — original text, source, reporter, date, reproduction steps, expected vs. actual, environment. Do not paraphrase; specifics matter for reproducing. If the report is unclear ("login is broken"), **interview** before moving on.

Then **open the tracking issue** (graceful-skip): announce a one-sentence title + body (verbatim quote + source/date + reproduction steps), then run `gh issue create --label bug` (recoverable → announce + proceed). Record `**Tracking:** #N` near the top of PLAN.md; reference `#N` in the fix commit.

### 2. Analyze

Find the **root cause**, not the first plausible one.
- **Reproduce locally.** Can't reproduce? Note whether it's environment-specific, flaky (investigate timing/state), or not real.
- **Read the code paths** — dispatch the `explorer` sub-agent for unfamiliar areas.
- **Ask "why" three times** — the function threw → why? → input malformed → why? → the validator's regex was wrong.
- **Note load-bearing assumptions** — what else depends on the broken behavior working as it currently does?

Write findings under `## Analysis` (Reproduction / Root cause `file:line` / Why it happened / Scope / Fix strategy). If the root cause is actually a **design flaw**, **stop** and escalate to `/plan` — patching a symptom of a design flaw creates two bugs. Post the Analysis to the tracking issue as a comment (announce + proceed; skip silently if no issue).

### 3. Fix

**Isolation check (operator-authority-gated):** if `.harness/project.json` has `isolation.mode: worktree-per-plan` (durable operator opt-in), run:
```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/isolation_config.py" check [--project-root <root>]
```
Exit 0 → auto-spawn a worktree: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spawn_worker.py" <slug>`, announce the spawn, proceed from inside the new worktree. Exit 1 → no worktree needed (single-owner guard or mode=direct). Silently skip this check when `CLAUDE_PLUGIN_ROOT` is unset.

Implement under `/work` discipline, plus two bugfix rules:
- **Regression test first** — it fails against the current code and passes after the fix.
- **Minimal scope** — adjacent issues go on the backlog, not in this fix.

Done when: the regression test passes, pre-existing tests still pass, deterministic gates are green. Post a Fix summary (commit SHA, regression test path + one-line description, files changed, gate results) to the issue (announce + proceed).

### 4. Verify

Run **`/review`** on the fix (non-negotiable for bugs). Confirm: the regression test is committed and **actually exercises the root cause** (not just the symptom); the original reproduction steps from `## Report` now produce the expected behavior. Probe with `bash "${CLAUDE_PLUGIN_ROOT}/scripts/capability_probe.py" wiki-maintenance`; on **exit 0** dispatch the `documenter` (**lightweight** — most bugfixes get `NO CHANGES`; it updates a Known-Issues page or adds an ADR **only** if the fix reveals a durable gotcha — over-documentation is drift too); on **exit 1** skip silently.

Post a Verify summary to the issue, then run `gh issue close --reason completed` with a one-line note referencing the fix SHA (recoverable — a closed issue reopens; announce + proceed).

**Sync the GitHub Project board** (graceful-skip): probe `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/capability_probe.py" github-projects`; on **exit 1** (plugin absent, or no `CLAUDE_PLUGIN_ROOT`) skip silently. On **exit 0** with `.harness/project.json` + `gh` present, the `gh issue` close above stays the bug's posterity record — `Bug` has **no locked board template this cycle** (the renderer raises on `bug`), so direct bug board-emission is deferred. If the fix's closeout belongs to a *materialized* Task/Plan, emit it via the github-projects plugin's `project_sync.py post` (deterministic + idempotent → announce + proceed); otherwise nothing to sync. Append to `progress.md`:

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
