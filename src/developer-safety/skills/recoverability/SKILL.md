---
name: recoverability
description: Autonomy doctrine — classify every action as recoverable or unrecoverable, proceed on the former, stop on the latter. The stop-gate is reversibility, not destructiveness or blast-radius.
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

You are applying the `recoverability` skill. This is a standing principle — it governs every action in every session, not just code changes. Apply it before any action that has side effects outside the current working tree.

## The doctrine

The stop-gate is **recoverability, not destructiveness or blast-radius.** A recoverable action proceeds (announced); only a genuinely unrecoverable one stops for confirmation. Blast radius is not the criterion — a large-blast-radius action that is fully reversible proceeds; a small-blast-radius action that cannot be undone stops.

| Class | What it looks like | Behavior |
|---|---|---|
| **Recoverable** | `git push` / `-u` / `HEAD:`; create + push a tag; `gh release create` (deletable); `gh pr create` (closeable); `gh pr merge` (revertable); `gh issue create` / `close`; force-push to your **own un-shared** worker branch; delete a branch whose tip is still reachable | **Announce + proceed** — no confirmation wait |
| **Unrecoverable** | force-push rewriting **published shared** history; sole-ref delete of unmerged work; **published-tag** overwrite; immutable publish / deploy / migration | **Stop + confirm** — pre-announce (state what is about to happen, don't ask), then wait for operator approval |
| **Unresolved decision** | a genuine question the design or plan never settled | **Stop + ask** — and flag it as a design/plan gap so the upstream phase can address it |

**When uncertain, treat as unrecoverable** — the conservative default. Forcing the operator to micromanage routine recoverable actions is the bigger cost; silently executing a genuinely unrecoverable one is the failure mode to avoid.

## Push classification mechanism

The push row of the doctrine table above splits into a git *fact* (would this push discard any commit the remote currently holds — is it a fast-forward?) and a *judgment call* no git command can answer (if it isn't a fast-forward, is the discarded history genuinely "shared," or just your own un-shared branch?). `scripts/recoverability_classifier.py` (bundled with this plugin) answers the fact mechanically instead of leaving it to prose guesswork; it never resolves the judgment call, and it doesn't try to.

Before treating a `git push` as recoverable-vs-unrecoverable, run it:

```bash
python3 <path>/scripts/recoverability_classifier.py push [--repo <repo-root>] [--branch <name>] [--remote origin] [--remote-branch <name>]
```

Locate `<path>` the same way `pii-scrubber` locates its own bundled script: `${CLAUDE_PLUGIN_ROOT}/scripts/` first (resolves whenever this plugin is installed), then `$AGENT_TOOLKIT_PATH/scripts/` if set, then a sibling checkout convention (`../crickets/scripts/`, `~/Antigravity/crickets/scripts/`). `--branch`/`--remote`/`--remote-branch` default to the current branch / `origin` / the same name as `--branch` — the common case (`git push`, `git push origin main`) needs no flags.

Read the exit code, not just the printed word:

| Exit | Verdict | What it means for this doctrine |
|---|---|---|
| `0` | `recoverable` | Fast-forward (or a brand-new/unchanged remote tip) — nothing the remote holds gets discarded. **Announce + proceed**, per the table above. |
| `2` | `needs-judgment` | Not a fast-forward. The script can't tell "your own un-shared branch" from "published shared history" from git state alone — that's exactly the judgment call this SKILL.md's own table names. Fall back to that judgment: is another contributor's work known to depend on this branch? If genuinely unsure, **treat as unrecoverable** (the doctrine's own conservative default) — stop and confirm. |
| `3` | (usage/git error) | The script couldn't resolve a branch or SHA (detached HEAD, bad repo path, unreachable remote). Don't silently skip the check — fall back to the conservative default and stop and confirm. |
| `1` | `unrecoverable` | Reserved for a future verdict kind; `classify_push` itself never emits it today (a push is either a fast-forward or a judgment call — never a case the script itself is certain is unrecoverable). Treat it as stop and confirm if it ever appears. |

This mechanism covers pushes only. `recoverability_classifier.py` also implements `classify_ref_delete` (ref-delete reachability) and `classify_tag_overwrite` (tag-publication status) as library functions — proven correct by `scripts/test_recoverability_classifier.py` — but neither is wired to a CLI yet; the ref-delete and tag-overwrite rows of the doctrine table above stay prose-judgment-only until a future task wires them the same way.

## Pre-announcing, not permission-asking

For actions that are recoverable-but-surprising (a push to a remote branch the operator hasn't explicitly mentioned, closing an issue, merging a PR): **state what is about to happen, then do it.** Do not frame it as a question. The distinction:

- ✅ "Pushing to `worker/probe-retirement` — announce + proceed."
- ❌ "Should I push to `worker/probe-retirement`?"

Pre-announcing keeps the operator informed without requiring them to approve every routine action. The operator can always interrupt (via the kill-switch hook) if they want to redirect.

## Autonomy during close-out

Close-out bookkeeping is **recoverable → autonomous** — never stop to ask approval for:

- Archiving a completed plan (`PLAN.md` → `PLAN.archive.YYYYMMDD-<slug>.md`)
- Appending a close-out entry to `progress.md`
- Moving a ROADMAP item to Completed/SHIPPED
- Updating staging notes

These actions are all reversible (files can be moved back, entries deleted) and are standard close-out steps that do not require per-instance approval once a plan is confirmed done.

## Carve-outs — unchanged by this doctrine

These constraints hold regardless of the recoverability classification:

- **Worker-tree initiation requires operator authority.** A worktree spawn is not a recoverable action the agent can self-authorize — it requires either an explicit `/spawn-worker` command or a durable `isolation.mode: worktree-per-plan` config opt-in. Silent auto-spawn stays forbidden.
- **`/integrate-worker` stays operator-initiated.** Merging a worker branch is a consequential action even though it is technically reversible — it requires explicit operator invocation.
- **PII pre-push hook + `pii-scrubber` invocation stay mandatory.** Never bypass them as "recoverable" — a leaked PII commit, while technically reversible with a history rewrite, creates a window of exposure that the probe is designed to prevent.
- **No `Co-Authored-By: Claude` trailer in commit messages.** This is an authorship convention, not a recoverability question; it is not subject to the proceed-vs-stop calculus.

## Interaction with the phase hooks

The `kill-switch`, `steer`, and `commit-on-stop` hooks in this plugin are the **runtime enforcement layer** for this doctrine:

- `kill-switch` — lets the operator halt tool execution when they see the agent about to cross a line.
- `steer` — lets the operator redirect mid-run without a full session restart.
- `commit-on-stop` — preserves in-progress work when the session ends unexpectedly, so the "stop" in an unrecoverable situation doesn't also lose the work.

The skill is the **pre-action discipline**; the hooks are the **in-flight controls**.

## Concrete classification examples

| Action | Class | Why |
|---|---|---|
| `git push origin main` | Recoverable | Remote tip can be reset; a bad push can be force-pushed back or a revert commit pushed |
| `git push --force origin main` | **Unrecoverable** | Rewrites published shared history — other checkouts diverge, tags may become orphaned |
| `gh pr merge --squash` | Recoverable | Merge can be reverted with a revert commit |
| `git push origin --delete feature-branch` (branch still in a PR, tip reachable) | Recoverable | Tip is reachable; branch can be restored with `git push origin <sha>:refs/heads/feature-branch` |
| `git push origin --delete feature-branch` (branch's only ref, tip not in any other ref) | **Unrecoverable** | Sole reference; SHA is only reachable from reflog (time-limited) — treat as unrecoverable |
| `gh release create v1.0.0` | Recoverable | GitHub releases are deletable via `gh release delete` |
| Overwriting an already-published tag | **Unrecoverable** | Published tags are consumed by downstream tools; overwriting silently breaks pinned installs |
| Archiving a completed `PLAN.md` | Recoverable (autonomous) | File rename; the archive can be renamed back at any time |
| Editing a `.github/workflows/` CI file | Recoverable | File change on a branch; reversible with a revert commit before merge |
| Running a database migration | **Unrecoverable** | Schema changes are not automatically reversible; stop and confirm |

## See also

- [`recoverability_classifier.py`](../../scripts/recoverability_classifier.py) — the mechanical push-classification check the section above wires in.
- [`kill-switch` hook](../../hooks/kill-switch/hook.md) — halt tool execution when an unrecoverable action approaches.
- [`steer` hook](../../hooks/steer/hook.md) — redirect mid-run without session restart.
- [`commit-on-stop` hook](../../hooks/commit-on-stop/hook.md) — preserve in-progress work on stop.
- [developer-workflows recoverability gate](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/work.md) — the phase-specific encoding of this doctrine (byte-identical table across `/work`, `/bugfix`, `/release`).
