# How to run a standalone code review

> [!NOTE]
> **Goal:** Adversarially review any diff or PR with the `/code-review` command — no `/work` cycle, no commit required.
> **Prereqs:** the `code-review` plugin installed ([Install crickets plugins](Install-Into-Project)); `git`. Optional: `gh` (for PR review) and `gemini` (for the cross-model pass).

`/code-review` is the standalone command from the `code-review` plugin. It dispatches the adversarial reviewers against a diff and **reports** — it never fixes. Run it on an open PR, a branch, a commit range, or your uncommitted working tree.

## Steps

1. Invoke the command with a target — or none, to review the working-tree diff:

   ```text
   /code-review                 # uncommitted working-tree diff (git diff HEAD)
   /code-review main...HEAD     # a commit range
   /code-review #123            # a PR by number (needs gh)
   /code-review <PR URL>        # a PR by URL (needs gh)
   ```

   If the resolved diff is empty, the command says so and stops.

2. It dispatches up to two reviewers against the diff (plus the spec / `.harness/PLAN.md` task when obvious, plus the relevant `AGENTS.md` slice):

   - **`adversarial-reviewer-cross`** — the cross-model reviewer. Runs first when `gemini` is on PATH; it escapes the same-model echo chamber.
   - **`adversarial-reviewer`** — the in-process reviewer (same model). It corroborates, or becomes the sole reviewer when the cross-model pass falls back.

3. Read the contract output. Each reviewer returns **exactly one** of:

   - a **failing test** in a fenced code block (first line a `//` or `#` path comment), or
   - a line `DEFECT: <path>:<line>` (with spec / actual / a minimal reproducer), or
   - `NO ISSUES FOUND` (with the files + categories it checked).

   Prose-only critiques are rejected. When the two reviewers disagree (one finds a defect, one says clean), **both are surfaced** — disagreement is signal. Any `file:line` or failing test is verified to reproduce before it's reported.

4. Act on the findings yourself — `/code-review` reports, it doesn't edit. Standalone, the fixes are yours. (Inside a `/work` loop, the same reviewers feed a follow-up `/work` task instead.)

## Cross-review privacy note

The cross-model pass sends your diff to the **Gemini CLI → Google**. Treat it as opt-in:

- It's **operator-opt-in per invocation** — the cross-model reviewer runs only when you invoke `/code-review` and `gemini` is present.
- The model is **editable** — point the cross-review reviewer at `claude` instead of Gemini to keep the diff inside your model boundary.
- It **graceful-skips** when `gemini` is absent or unauthed: `cross-review.sh` exits non-zero and the command falls back to the in-process `adversarial-reviewer` (same model, no external send).
- The in-process `adversarial-reviewer` always stays on the current model — it never sends the diff anywhere.

## See also

- [In-flight decision review — /doubt](Use-Doubt-Review) — use `/doubt` instead when you want to challenge a decision *before* you write the code.
- [Install crickets plugins](Install-Into-Project) — get the `code-review` plugin onto your host.
- [Installing and using the code-review plugin](01-First-Code-Review) — the hands-on first run, if you haven't done one.
- [Evaluator](Evaluator) — PASS / NEEDS_WORK grading against a rubric (a different reviewer role).
- [Compatibility](Compatibility) — the `evidence-tracker` hook (also in `code-review`) is Claude-only-effective.
- [Modify a crickets plugin](Modify-A-Plugin) — edit the reviewers / `cross-review.sh` and dogfood.
