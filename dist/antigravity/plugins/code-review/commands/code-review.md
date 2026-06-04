---
name: code-review
description: Adversarial review of any diff or PR — standalone, no /work cycle. Dispatches the cross-model + in-process adversarial reviewers; reports a failing test, a DEFECT file:line, or NO ISSUES FOUND. Never fixes.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: <diff range | branch | PR number/URL — defaults to the working-tree diff>
---

You are running **/code-review** — adversarial review of a diff or PR, **standalone** (no `/work` cycle needed). You **report**; you never fix.

**Target (if any):** $ARGUMENTS — a commit range (`main...HEAD`), a branch, a PR (`#123` / URL), or empty (review the uncommitted working-tree diff).

## Process

### 1. Resolve the diff

- **PR** (`#N` or URL): `gh pr diff <N>` (graceful-skip if `gh` absent — ask for a range instead).
- **Range / branch**: `git diff <range>` (default base = merge-base with the default branch).
- **Empty**: the uncommitted working-tree diff (`git diff HEAD`); if the tree is clean, the last commit (`git show HEAD`).

If the resolved diff is empty, say so and stop.

### 2. Gather context (light)

- The relevant spec if obvious (a `.harness/PLAN.md` task when one exists) — otherwise **the diff is the spec**.
- `AGENTS.md` / `CLAUDE.md` conventions that bear on the diff — a tight slice, not the whole file.

### 3. Gates first (if present + local)

If the repo has deterministic gates (from `.harness/init.sh` / package scripts / Makefile) and the change is checked out locally, you MAY run them and note any red gate — **never review on a base you can tell is broken**. For a pure diff/PR review with no checkout, skip.

### 4. Dispatch the reviewers

- If the cross-model reviewer is available (the `adversarial-reviewer-cross` agent + `gemini` on PATH), dispatch **`adversarial-reviewer-cross`** first — cross-model review escapes the same-model echo chamber. On its exit-1 fallback (no gemini), it falls back to the in-process reviewer.
- Then dispatch **`adversarial-reviewer`** (in-process) — corroboration, or sole reviewer if cross-model fell back.
- Pass each the diff + the spec/PLAN-task + `AGENTS.md`. Do **NOT** pass an implementer reasoning trace — fresh context only.

### 5. Surface findings (the contract)

Each reviewer returns exactly one of: a **failing test** (fenced), a **`DEFECT: path:line`** (spec / actual / minimal reproducer), or **`NO ISSUES FOUND`** (files + categories checked). Prose-only critiques are rejected. If the two reviewers disagree (one finds a defect, one says clean), **surface both** — disagreement is signal, not noise. **Verify** any `file:line` / failing test reproduces before reporting it.

### 6. Report — never fix

Summarize the findings + recommend follow-ups. `/code-review` **reports**; it does not edit. (Inside a `/work` loop the fixes become a follow-up `/work` task; standalone, they're the operator's to act on.)

## Privacy

`adversarial-reviewer-cross` sends the diff to the Gemini CLI (→ Google) via `cross-review.sh` — **operator-opt-in per invocation**, editable to `claude`. The in-process `adversarial-reviewer` stays on the current model.

## Composition

Standalone, this reviews any diff/PR with no `/work` cycle. Installed alongside **developer-workflows**, it enhances the `review` capability — developer-workflows' thin `/review` dispatches these same reviewers (the conditional-dispatch wiring is the separate `auto-enable-runtime` part).
