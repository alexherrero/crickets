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

> **Recommended model for this phase:** Sonnet 4.6 (`claude-sonnet-4-6`) — lighter model for planning and review. Override with `/model` if needed.

> **Thin by design.** The adversarial reviewers themselves (e.g. crickets `code-review`: `adversarial-reviewer` + cross-model `adversarial-reviewer-cross`) live in a **separate plugin** so review can also run standalone outside any `/work` cycle. When that plugin is present, `/review` engages it; when absent, `/review` runs the deterministic gates and notes the lighter pass — a clean **graceful-skip, never an error**.

## Non-negotiable constraints

1. **Gates first.** Run typecheck, lint, tests, build. If any fail, **stop and report** — never review on a broken base.
2. **Deeper review only if available — deterministic probe.** Check availability with the bundled probe: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/capability_probe.py" code-review`. **Exit 0** (code-review installed + enabled) → dispatch its `adversarial-reviewer` (+ cross-model `adversarial-reviewer-cross` if present) in a **fresh context** with the diff + the `PLAN.md` task + `AGENTS.md` — **not** the implementer's reasoning trace. **Exit 1** (absent, or graceful-skip on a host that doesn't set `CLAUDE_PLUGIN_ROOT`) → skip the adversarial pass and note "deterministic gates only; no adversarial reviewer installed." The probe is a deterministic CLI check, not agent-judgment; any failure resolves to "unavailable" (gates-only) — never a hang.
3. **Framing is literal** (whenever a reviewer runs): "The code under review likely contains bugs. Find them." Do not soften.
4. **Executable artifact required** from any reviewer: a failing test, a specific `file:line` defect, or an explicit `NO ISSUES FOUND` with categories. Prose-only critiques are rejected.
5. **Verify findings reproduce** before reporting — run the failing test, open the line reference.
6. **Do not fix what you find.** `/review` reports; `/work` implements. Recommend a follow-up task.
7. **Do NOT dispatch the documenter.** Doc drift is `/release`'s concern; surfacing it as a finding is fine, acting on it is not.
8. **Log to the resolved `progress.md`** with the outcome (`NO ISSUES FOUND` or `N findings`) — the scoped `progress-<slug>.md` when a named plan is under review, the singleton otherwise.

## Process

1. **Run the gates** (from `.harness/init.sh` / package scripts / Makefile), in order, short-circuit on failure. A red gate ends the review — report it and stop.
2. **Identify the artifact** — the commit range / branch / uncommitted diff and its `PLAN.md` task (default: the most recently-completed task). **Named plan?** If `$ARGUMENTS` contains **`--name <slug>`**, resolve the pair with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" <slug>` (consume the resolver — never re-derive paths) and read the **resolved `PLAN-<slug>.md`** for task context; log to the scoped **`progress-<slug>.md`**. A non-zero exit is a **hard stop** (surface stderr; no singleton fallback on a dangling binding). Bare `/review` (no `--name`) uses the singleton, **byte-identical** to today. The remaining `$ARGUMENTS` (commit range / branch / `task N`) still scopes the review.
3. **Probe, then dispatch if available** (constraint 2). Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/capability_probe.py" code-review`; on **exit 0** dispatch `adversarial-reviewer-cross` (if `gemini` is available) then `adversarial-reviewer`; on **exit 1** run gates-only and note the lighter review. The probe is the **interim local fallback** — when agentm's V5-8 capability-discovery API lands, this becomes a host-API query (identical runtime contract: deterministic yes/no + graceful-skip).
4. **Triage findings** — verify each reproduces; group them; recommend follow-up `/work` tasks. Do not fix.
5. **Log + report.** Append to the resolved `progress.md`; return the outcome and any recommended follow-ups.

## When the deeper reviewer is absent

`/review` still earns its keep — gates are the floor. Report: *"gates green; no adversarial reviewer installed — add a code-review capability for a deeper pass."* This is the expected standalone behavior, not a failure.
