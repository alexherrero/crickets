# How to review an existing change with /build-it --check

> [!NOTE]
> **Goal:** Review an existing change (a PR, commit range or diff file) with `/build-it --check` for a report of real findings with cited lines. It never edits the code.
> **Prereqs:** `git`, the `development-lifecycle` plugin (ships `/build-it`) and the `code-review` plugin (ships its reviewers and `cross-review.sh`) ([Install crickets plugins](Install-Crickets-Plugins)). Optional: `gh` (for a PR) and the Antigravity CLI (`agy`, for the cross-model reviewer).

`/build-it --check` runs the same review passes `/work` runs on each step, against finished work. It reports; the fixes are yours. Without the `code-review` plugin, it still runs and says so: each pass goes to a plain read-only reviewer on Sonnet.

## Steps

1. Run it on the change:

   ```text
   /build-it --check 123             # a PR by number (needs gh)
   /build-it --check main..HEAD      # a commit range
   /build-it --check change.diff     # a diff file
   ```

   To review uncommitted work, write it to a file first: `git diff HEAD > change.diff`.

2. Check what it held the change to. It uses a spec beside the plan when there is one. Otherwise the PR description or commit messages are the contract, and the repo's `AGENTS.md` supplies the rules. The report says which. With neither, the rules block is empty and the report says why.

3. Check the size it picked, and override it for more passes. It sizes the change from the diff:

   | Size | Passes |
   |---|---|
   | `small` | none — free checks only |
   | `medium` | correctness |
   | `large` | correctness, then simplicity |

   Add `--size large` to get the simplicity pass on a smaller change. A security pass (`security-auditor`) joins when the change touches auth, secrets, shell execution or network input.

4. Read the report. The repo's own checks run first, at that revision; whatever could not run is listed under **Not checked**. Each pass runs one round. Every finding is sorted as real, tradeoff, misread or noise, with a cited `path:LINE`. A real finding stays **OPEN**: check mode has no fix loop. The correctness pass also counts a behaviour change with no test that would catch its regression as a real finding.

5. Fix the real findings yourself, then run `/build-it --check` again on the new range.

## Cross-review privacy note

The cross-model reviewer sends the review material (diff, contract and rules) to **Gemini, via `agy`, to Google**:

- It runs whenever `agy` is on your PATH. Without `agy`, each pass falls back to a Sonnet reviewer and the material goes to no outside model.
- It **degrades visibly**. If `agy` is missing, fails, or times out (180 seconds on the `default` tier, 300 on `high`; see [Code Review](Code-Review#cross-review-tiers)), or if the material exceeds `cross-review.sh`'s size ceiling, the script prints `CROSS-REVIEW-DEGRADED: <reason>`. `/build-it` says so in one line and runs that pass on a Sonnet reviewer.

## See also

- [Your first code review](01-First-Code-Review) — the hands-on first run.
- [Development Lifecycle](Development-Lifecycle) — `/build-it` and the rest of the loop.
- [Code Review](Code-Review) — reviewers, tiers and `review_material.py`.
- [Evaluator](Evaluator) — the done-check grader (optional in check mode).
- For a quick ad hoc look, Claude Code's built-in `/code-review` and `/simplify` remain available; they are not part of crickets.
