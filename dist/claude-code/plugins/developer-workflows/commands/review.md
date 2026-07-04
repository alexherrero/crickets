---
name: review
description: Adversarial review — gates first, then dispatch a deeper adversarial pass if available. Reports, never fixes.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: [optional — "--name <plan-name>" to target a named plan, plus a commit range, branch, or task number to scope the review]
---

You are running the **review** phase of the developer-workflows loop. Review is **deliberately thin** here: it runs the deterministic gates and orchestrates a deeper adversarial pass *only if a code-review capability is installed*. It **reports**; it never fixes.

**Scope (if any):** $ARGUMENTS — if empty, review the most recently-completed task.

> **Recommended model for this phase:** Sonnet 5 (`claude-sonnet-5`) — lighter model for planning and review. Override with `/model` if needed.

> **Thin by design.** The adversarial reviewers themselves (e.g. crickets `code-review`: `adversarial-reviewer` + cross-model `adversarial-reviewer-cross`) live in a **separate plugin** so review can also run standalone outside any `/work` cycle. When that plugin is present, `/review` engages it; when absent, `/review` runs the deterministic gates and notes the lighter pass — a clean **graceful-skip, never an error**.

## Non-negotiable constraints

1. **Gates first.** Run typecheck, lint, tests, build. If any fail, **stop and report** — never review on a broken base.
2. **Deeper review only if available — deterministic capability check.** Check availability: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_capability.py" adversarial-review`. **Exit 0** (adversarial-review capability available) → dispatch the `adversarial-reviewer` (+ cross-model `adversarial-reviewer-cross` if present) in a **fresh context** with the diff + the `PLAN.md` task + `AGENTS.md` — **not** the implementer's reasoning trace. **Exit 1** (unavailable, or graceful-skip when agentm is absent or `CLAUDE_PLUGIN_ROOT` unset) → skip the adversarial pass and note "deterministic gates only; no adversarial reviewer installed." The capability check is deterministic, not agent-judgment; any failure resolves to "unavailable" (gates-only) — never a hang. **Routed dispatch (separate graceful-skip):** additionally check `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_capability.py" token-audit`; on exit 0, resolve `classify_work_type('adversarial-reviewer')` / `classify_work_type('cross-model-reviewer')` + `agent_tool_alias(...)` and pass the result as each dispatch's `model` param; on exit 1, dispatch with no `model` override — today's behavior, unchanged.
3. **Framing is literal** (whenever a reviewer runs): "The code under review likely contains bugs. Find them." Do not soften.
4. **Executable artifact required** from any reviewer: a failing test, a specific `file:line` defect, or an explicit `NO ISSUES FOUND` with categories. Prose-only critiques are rejected.
5. **Verify findings reproduce** before reporting — run the failing test, open the line reference.
6. **Do not fix what you find.** `/review` reports; `/work` implements. Recommend a follow-up task.
7. **Do NOT dispatch the documenter.** Doc drift is `/release`'s concern; surfacing it as a finding is fine, acting on it is not.
8. **Log to the resolved `progress.md`** with the outcome (`NO ISSUES FOUND` or `N findings`) — the scoped `progress-<slug>.md` when a named plan is under review, the singleton otherwise.
9. **Design-conformance dimension (Hook 1, design-doc §6).** When a governing design resolves for the changed files, hand the reviewer its path and treat `design-conformance` as a first-class finding category — a `file:line` where the code diverges from a *locked design call*. Greenfield / agentm-absent → skip the dimension silently (gates + bug-hunt unchanged). See step 3b.

## Process

1. **Run the gates** (from `.harness/init.sh` / package scripts / Makefile), in order, short-circuit on failure. A red gate ends the review — report it and stop.
2. **Identify the artifact** — the commit range / branch / uncommitted diff and its `PLAN.md` task (default: the most recently-completed task). **Named plan?** If `$ARGUMENTS` contains **`--name <slug>`**, resolve the pair with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" <slug>` (consume the resolver — never re-derive paths) and read the **resolved `PLAN-<slug>.md`** for task context; log to the scoped **`progress-<slug>.md`**. A non-zero exit is a **hard stop** (surface stderr; no singleton fallback on a dangling binding). Bare `/review` (no `--name`) uses the singleton, **byte-identical** to today. The remaining `$ARGUMENTS` (commit range / branch / `task N`) still scopes the review.
3. **Probe, then dispatch if available** (constraint 2). Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_capability.py" adversarial-review`; on **exit 0** dispatch `adversarial-reviewer-cross` (if `gemini` is available) then `adversarial-reviewer`; on **exit 1** run gates-only and note the lighter review. The capability check queries the agentm capability resolver (V5-8, capability-keyed) via best-effort discovery — when agentm is absent the script exits 1 (unavailable) rather than hanging.
3b. **Resolve the governing design (Hook 1 · design-doc §6).** Resolve the living design that governs the changed files: prefer the plan's `parent_design_doc:` frontmatter; else run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_governing_design.py" <changed-file>` (**exit 0** → its repo-relative path; **exit 1** → greenfield / agentm absent → skip this dimension). When a design resolves, hand the reviewer **the design path** alongside the diff + task + `AGENTS.md`, and instruct it to add **`design-conformance`** findings — each a `file:line` where the change diverges from a *locked design call* in that design. This is the fresh-context home for the un-mechanizable "does this conform?" judgment: the worker rationalizes, the cold reviewer doubts. The resolve is deterministic — any failure resolves to greenfield (dimension skipped), never a hang.
4. **Triage findings** — verify each reproduces; group them; recommend follow-up `/work` tasks. Do not fix.
5. **Log + report.** Append to the resolved `progress.md`; return the outcome and any recommended follow-ups.

## When the deeper reviewer is absent

`/review` still earns its keep — gates are the floor. Report: *"gates green; no adversarial reviewer installed — add a code-review capability for a deeper pass."* This is the expected standalone behavior, not a failure.

## Common Rationalizations

| Excuse | Why it's wrong |
|---|---|
| "The code looks fine, no defect found" | Correct output is 'NO ISSUES FOUND after thorough examination', not 'looks fine'. Examine, don't glance. |
| "I'll write prose feedback instead of a file:line defect" | Prose-only critiques are rejected. Return a failing test, DEFECT file:line, or explicit NO ISSUES FOUND. |
