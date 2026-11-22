---
name: recoverability
description: Autonomy doctrine — classify every action as recoverable or unrecoverable, proceed on the former, stop on the latter. The stop-gate is reversibility, not destructiveness or blast-radius. The one home of the doctrine `/work`, `/bugfix` and `/release` summarize.
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.2.0
---

You are applying the `recoverability` skill. It governs every action with side effects outside the working tree, in every session. `/work`, `/bugfix` and `/release` carry a short summary of it and point here; this is the full doctrine.

## The doctrine

Invoking a phase **is** the authorization to run it to completion. The stop-gate is **recoverability, not destructiveness or blast-radius**: a recoverable action proceeds (announced); only a genuinely unrecoverable one stops for confirmation. A large, fully reversible action proceeds; a small one that cannot be undone stops.

| Class | Examples | Behavior |
|---|---|---|
| **Recoverable** | `git push` / `-u` / `HEAD:`; create + push a tag; `gh release create` (deletable); `gh pr create` (closeable); `gh pr merge` (revertable); `gh issue create` / `close`; force-push to your **own un-shared** worker branch; delete a branch whose tip is still reachable | **Announce + proceed** — no confirmation wait. |
| **Unrecoverable** | force-push rewriting **published shared** history; sole-ref delete of unmerged work; **published-tag** overwrite; immutable publish / deploy / migration | **Stop + confirm** — pre-announce (state, don't ask), then wait. |
| **Unresolved decision** | a genuine question the design or plan never settled | **Stop + ask** — and log it as a design/plan gap (an upstream phase missed it). |

**When uncertain, treat as unrecoverable** (conservative default). Any summary a phase produces is a **record of what the autonomous run did**, not a stop-and-wait barrier.

## Pre-announce, don't ask

For a recoverable action that may surprise the operator (a push to a branch they haven't named, closing an issue, merging a PR), state what is about to happen, then do it.

- ✅ "Pushing `worktree-104-…` and opening its PR."
- ❌ "Should I push `worktree-104-…`?"

The operator can interrupt through the `kill-switch` hook or redirect through `steer`; `commit-on-stop` keeps in-progress work if a session ends.

## Close-out is autonomous

Close-out bookkeeping is **recoverable → autonomous**: appending `progress.md`, moving a ROADMAP item to Completed/SHIPPED, updating staging notes, archiving a repo-local plan. Never stop to ask approval for it.

A task directory (`tasks/<name>/`) never moves at close-out: its `done` tracker says it is over, and agentm's nightly job moves its finished records. Only a repo-local plan archives: in a repo with no vault, a plan in `.harness/` moves to `.harness/archive/PLAN.archive.YYYYMMDD-<slug>.md`, and its tracker stays in `.harness/` at `done`.

## Carve-outs — unchanged by this doctrine

- **Worktree initiation requires operator authority** — a durable `isolation.mode: worktree-per-plan` config opt-in (`/work`'s own auto-spawn) or an explicit operator instruction to use a worktree; silent authority-free auto-spawn stays forbidden. Integration lands via the plan's own PR and required-check gate, armed for auto-merge.
- **The PII pre-push hook + `pii-scrubber` invocation stay mandatory.** A leaked commit is reversible only by a history rewrite, after a window of exposure.
- **The no-`Co-Authored-By` commit rule is untouched.** It is an authorship rule, not a recoverability question.

## Classifying a push

Whether a push is a fast-forward is a git fact; whether the history it discards is "shared" is a judgment. `scripts/recoverability_classifier.py` (bundled with this plugin, under `${CLAUDE_PLUGIN_ROOT}/scripts/`) answers the fact:

```bash
python3 <path>/scripts/recoverability_classifier.py push [--repo <root>] [--branch <name>] [--remote origin] [--remote-branch <name>]
```

| Exit | Verdict | Do |
|---|---|---|
| `0` | `recoverable` | Fast-forward or a new remote tip: **announce + proceed**. |
| `2` | `needs-judgment` | Not a fast-forward. Does anyone else's work depend on this branch? If unsure, treat as unrecoverable. |
| `3` | usage / git error | The check could not run: stop and confirm. |
| `1` | `unrecoverable` | Reserved; never emitted today. Stop and confirm. |

Ref deletes and tag overwrites stay judgment calls: the script has library functions for both, with no CLI yet.

## Examples

| Action | Class | Why |
|---|---|---|
| `git push origin main` | Recoverable | A revert or a reset puts it back |
| `git push --force origin main` | **Unrecoverable** | Rewrites published shared history |
| `git push origin --delete <branch>`, tip reachable elsewhere | Recoverable | Restore it from the SHA |
| `git push origin --delete <branch>`, the only ref | **Unrecoverable** | Only the reflog holds it, for a while |
| Overwriting a published tag | **Unrecoverable** | Downstream installs pin it |
| A database migration | **Unrecoverable** | Not automatically reversible |
