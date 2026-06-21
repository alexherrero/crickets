# ADR 0003: Base operator-control hooks — kill-switch, steer, commit-on-stop

> [!NOTE]
> **Status:** accepted
> **Date:** 2026-05-14
> **Amended:** 2026-05-30 — decision §3 (commit-on-stop branch strategy) superseded by the **branch → snapshot redesign** ([crickets v2.2.0](https://github.com/alexherrero/crickets/releases/tag/v2.2.0)). See the [Amendment](#amendment-2026-05-30) at the bottom.

## Context

The cwc-long-running-agents pattern (`~/ContextVault/domains/anthropic-patterns/cwc-long-running-agents.md`) identifies three operator-precision primitives that any long-running agent workflow benefits from but the harness's existing surface area doesn't provide:

1. **Precise halt** — today, the only way to halt a runaway iteration loop in a Claude Code session is to close the session. That loses in-flight context the agent had built up; restarting is expensive (tokens, time, mental re-loading by the operator).
2. **Mid-run redirect** — today, the only way to redirect an agent that's heading the wrong direction is to interrupt-and-restart. Same cost as above. The operator-typed correction is unreliable mid-stream because the agent has to acknowledge + apply it in the same response that may be already mid-action.
3. **Crash recovery** — today, a crashed Claude Code session (or one closed mid-task) loses any uncommitted work. Recovery is "hope you committed recently."

The harness's existing hook surface (`PostToolUse` for verify, `PreCompact` for compact, `SessionStart` for state-load) is harness-shape-specific. The three operator-control primitives are host-cross-cutting and consumer-cross-cutting: they're useful for the harness's `/work` + `/release` phases, the future design skill (#6), the quality-gates bundle (#10), and any long-running custom skill. The natural home is `crickets`.

Open design questions at planning time:

1. **File location** — per-repo (`.harness/STOP` inside the project) or device-scope (`~/.harness/STOP` halting all sessions)?
2. **STEER.md semantics** — delete after consumption, or rename for audit trail?
3. **commit-on-stop branch strategy** — commit on the current branch, or create a safety branch?
4. **commit-on-stop triggers** — Stop event only, or also fire after N consecutive tool errors?
5. **Hook ordering** — kill-switch must fire before steer in PreToolUse; what enforces it?
6. **Host scope** — claude-code only, or include Antigravity / Gemini CLI?
7. **Settings.json merge semantics** — how does the toolkit installer register hooks without clobbering existing user content in `.claude/settings.json`?

This ADR resolves all seven.

## Decision

### 1. File location: per-repo only (v0.7.0)

`.harness/STOP`, `.harness/STEER.md`, and `auto-save/<iso-ts>` all scope to the target git repository:

- `<repo>/.harness/STOP` — operator touches; halts only the session running in this repo.
- `<repo>/.harness/STEER.md` — operator writes; consumed by the session in this repo.
- `<repo>/auto-save/<iso-ts>` — branch in this repo's git, holds safety commits.

**Why not device-scope:** a device-scope `~/.harness/STOP` would halt every Claude Code session on the machine — useful as a panic button, but blunt. Per-repo is precise and matches how most operators run: one project at a time. Device-scope is deferred to a future `dev-machine-setup` plan once both repos grow PATH-CLI sugar and a clear "halt everything" use case surfaces.

### 2. STEER.md semantics: rename for audit trail, don't delete

After the hook reads `.harness/STEER.md`'s contents, it renames the file to `.harness/STEER.consumed-<iso-ts>.md`. The original file disappears (so the hook doesn't fire on the next tool call with stale contents); the renamed file preserves the history.

**Why audit trail beats delete:**

- **Forensics.** "What did I tell the agent and when?" becomes answerable from local filesystem state.
- **Pattern detection.** If you steer the same way three sessions in a row, that's a signal to update `AGENTS.md` / `CLAUDE.md` with the pattern — but only if the steer history is recoverable.
- **Cost of accumulation is low.** STEER.consumed files are tiny (the original instruction) and operator can `rm` them whenever.

### 3. commit-on-stop branch strategy: safety branch, not current branch

> [!WARNING]
> **Superseded 2026-05-30** by the [branch → snapshot redesign](#amendment-2026-05-30) (crickets v2.2.0). The hook no longer creates a branch, switches HEAD, or touches the working tree — it records a snapshot on the hidden side ref `refs/auto-save/<ts>` via `commit-tree` + `update-ref`. The decision below is preserved as the v0.7.0 rationale-of-record; read the Amendment for what the hook does now and why the branch model was unsafe under multi-agent use.

The hook creates `auto-save/<iso-timestamp>` and commits dirty-tree changes there, then returns HEAD to the original branch with a clean working tree. The current branch is **never** modified.

**Why a safety branch:**

- **Preserves operator history.** The current branch's commit graph isn't polluted with auto-save commits the operator didn't intend.
- **Recovery is explicit.** `git checkout auto-save/<ts>` is an operator decision, not an automatic merge.
- **Safe to cherry-pick.** Saving as a new branch means the operator can choose to apply it to a different branch entirely (e.g. they realize the work belongs on a feature branch they hadn't created yet).

Trade-off: safety branches accumulate. v0.7.0 ships the hook + documents the cleanup pattern in the how-to (`git branch -D`). Auto-cleanup is a future improvement.

### 4. commit-on-stop triggers: Stop event only (v0.7.0)

The hook registers on Claude Code's `Stop` event (matcher `.*`) — fires at the end of each agent turn. If the working tree is dirty at turn-end, the hook creates the safety branch + commit.

**Scope reduction from the original plan:** the plan listed a second trigger — `PostToolUse` with an "N consecutive tool errors" condition (configurable via `COMMIT_ON_STOP_ERROR_THRESHOLD` env var). v0.7.0 ships **only the Stop trigger**. Rationale:

- **Stop covers the load-bearing case.** Session-end with uncommitted work is the most common crash-recovery scenario.
- **N-errors trigger requires state.** Counting consecutive errors across tool calls requires per-session state (written to disk between hook invocations) which is significantly more machinery than v0.7.0's pure-filesystem hooks.
- **Better to ship and iterate.** Shipping the Stop trigger now and observing real-world usage before adding complexity is the right sequencing.

The N-errors trigger is deferred to a follow-up plan if/when real usage surfaces the need.

### 5. Hook ordering: alphabetical install order

Within `PreToolUse`, `kill-switch` must fire before `steer` — a halt must take precedence over a redirect. The enforcement mechanism: the toolkit installer registers hooks in alphabetical order from `hooks/*/`, which means `commit-on-stop` < `kill-switch` < `steer`. Within `PreToolUse` (which only `kill-switch` and `steer` share), this puts `kill-switch` first.

**Why this enforcement works (today):**

- Claude Code runs hooks within an event in registration order (the order they appear in `.claude/settings.json`'s array).
- The toolkit installer walks `hooks/*/hook.md` in alphabetical sort order and merges fragments into settings.json in that order.
- Net result: alphabetical hook-dir name → alphabetical event-array position → alphabetical execution order.

**Re-audit triggers** — this invariant breaks if any of the following change:

- Claude Code changes hook event semantics from "registration order" to something else (concurrent execution, priority-field-based, last-registered-wins).
- The toolkit installer's discovery walk changes to non-alphabetical (e.g. filesystem-order-dependent).
- A future plan introduces a different way to register hooks (e.g. dynamic-priority).

All three are documented in the how-to + this ADR; revisit on every Claude Code release and every toolkit installer change.

### 6. Host scope: claude-code only (v0.7.0)

`supported_hosts: [claude-code]` on all three hooks. The toolkit installer warns-and-skips for Antigravity and Gemini CLI per the existing pattern (same as `kind: agent` was claude-code-plus-antigravity-via-skill-wrap in v0.6.0 — different skip pattern for different reasons).

**Why claude-code only:**

- **Antigravity** has no first-class hook surface. Sub-agents and rules are the closest analogs but they don't fire on every tool call.
- **Gemini CLI** has no first-class hook surface either. Slash commands and sub-agents don't have pre/post tool-call semantics.

The how-to documents manual equivalents for both hosts (always-on rules / operator prompts that ask the agent to check the trigger files on every step). These are best-effort — the agent has to remember to check — and don't have the precision of a host-level hook.

When (if) Antigravity or Gemini grow hook primitives, a future plan extends `supported_hosts` and ships per-host script + settings-fragment variants.

### 7. Settings.json merge semantics: idempotent deep-merge via Python helper

The toolkit installer (v0.7.0+) calls `scripts/merge-settings-fragment.py` to merge each hook's `settings-fragment-{bash,pwsh}.json` into the target's `.claude/settings.json`. The merge:

- Reads existing settings.json (or `{}` if missing).
- For each `hooks.<event>` in the fragment, appends entries that aren't already present (dedup on first inner hook's `command` field).
- Preserves all other top-level keys (user's `permissions`, third-party hooks, etc.).
- Idempotent: re-running the merge with the same fragment is a no-op.

`.claude/settings.json` is NOT a managed parent — it's preserved across `--update`; the toolkit re-merges its own fragments idempotently each run. The toolkit's hook scripts under `.claude/hooks/` ARE managed parents and get wipe-and-recreate on `--update` per the existing pattern.

Rationale for Python (not jq, which the harness uses): python3 is already a hard prereq of the toolkit installer (pyyaml + manifest-info.py). Adding jq would be a new dependency. The merge logic is short (one file, ~120 lines including docstring and edge-case handling). Future plan can converge harness + toolkit on a shared implementation if drift surfaces; until then, two short copies in two codebases is acceptable.

## Consequences

**Positive**

- **Precise operator control.** Three operator-precision primitives that didn't exist before. Halt, redirect, and crash-recovery each become a routine motion rather than a session-restart event.
- **Crash recovery becomes routine.** Every Claude Code session with dirty-tree work automatically creates a safety branch on session end. The worst case for an interrupted session goes from "lost work" to "stale branch you can recover from."
- **Composable across consumers.** Harness `/work` + `/release` augment with these hooks (graceful-skip). Design skill (#6) consumes them for its per-step execution loop. Quality-gates bundle (#10) packages them. Long-running custom skills consume them. One set of primitives, many call sites.
- **Settings.json merge capability lands.** v0.7.0 is the first time the toolkit installer can register host-level hooks alongside the host's own settings. Future kinds that need settings.json merge (e.g. `mcp-server`, `status-line`, `output-style`) can reuse the same helper.
- **First-class `kind: hook` support.** Same dogfood-the-pattern shape as `kind: agent` in v0.6.0 — building real hooks forces the installer + validator + per-host paths machinery end-to-end.

**Negative**

- **Claude-Code-only.** Antigravity + Gemini CLI users get manual-equivalent docs only. Reduces portability of the operator-control story. Mitigation: Claude Code is the most-used host in this personal-dev-env; the docs cover the alternatives.
- **Per-repo scope means no global halt.** Operators with many sessions across many repos can't halt all of them at once with a single `~/.harness/STOP`. Mitigation: device-scope deferred to future `dev-machine-setup` plan when PATH-CLI sugar lands.
- **Safety-branch sprawl.** Without cleanup, `auto-save/*` branches accumulate. Mitigation: how-to documents cleanup patterns; auto-cleanup is a future improvement.
- **Two grader-style mechanisms in PreToolUse.** kill-switch and steer share the event, and their interaction (halt-wins-over-steer) is alphabetically-enforced — a load-bearing invariant that could break if Claude Code's hook semantics change. Mitigation: documented in the how-to + here as a re-audit trigger.
- **commit-on-stop runs on every Stop event with a dirty tree.** Active development sessions can accumulate many safety branches per session (one per turn that leaves a dirty tree). Operators get to clean them up.
- **Synthetic commit identity.** commit-on-stop commits as `commit-on-stop@crickets.local` (scoped to the single commit via `git -c user.email=...`). The identity is fake but obvious in `git log`. Mitigation: the identity is documented in the hook body + this ADR; intentional choice to keep auto-saves visually distinct from operator commits in history.

**Load-bearing assumptions** (re-audit on every Claude Code release + every toolkit installer change)

- **Claude Code runs hooks within an event in registration order.** Kill-switch-before-steer enforcement depends on this.
- **`PreToolUse` exit 2 blocks the tool call + surfaces stderr to the agent.** Kill-switch's halt mechanism depends on this. If Claude Code changes the convention, kill-switch's halt behavior breaks.
- **`Stop` event fires at agent turn-end with the working tree intact at that moment.** commit-on-stop's safety-branch timing depends on this. If Stop fires after Claude Code wipes the working tree (e.g. for cleanup), commit-on-stop's snapshot is wrong.
- **`PreToolUse` hook stdout is captured and injected into agent context.** Steer's redirect mechanism depends on this.
- **The toolkit installer registers hooks in alphabetical filesystem order.** Hook ordering invariant depends on this.

## Amendment 2026-05-30

**commit-on-stop branch → snapshot redesign (v0.2.0).**

> [!NOTE]
> **Status:** accepted
> **Date:** 2026-05-30
> **Supersedes:** decision §3 (and recasts the "safety-branch sprawl" / "many branches per session" consequences). Shipped in [crickets v2.2.0](https://github.com/alexherrero/crickets/releases/tag/v2.2.0); hook manifest `0.1.0 → 0.2.0`.

### Context

Decision §3 (v0.7.0) had commit-on-stop **stash → branch → checkout → commit → checkout-back**: it parked the dirty tree on a fresh `auto-save/<ts>` branch (under `refs/heads/`), committed there, then returned HEAD to the original branch leaving the working tree *clean*. That made three assumptions that real use broke:

1. **The operator notices the work moved.** They didn't — it looked like a reset.
2. **One agent owns the working tree.** Increasingly false: orchestrator + sub-agents (and plain two-session) runs now routinely share one tree.
3. **One Stop per second.** Branch creation keys on a second-resolution timestamp; two Stop events in the same second collide.

The open question the original ADR couldn't yet answer ("safety branches accumulate; auto-cleanup is a future improvement") is also resolved here.

### Decision

commit-on-stop is rewritten to a **non-disruptive snapshot** model. On a dirty tree at Stop it:

1. Builds a tree from the **full** working state (tracked + untracked, `.gitignore` honored) in a **temporary index** (`GIT_INDEX_FILE`), seeded from HEAD then `git add -A`. The real index is never staged into.
2. `git commit-tree`s that tree, parented on HEAD, into a commit object.
3. `git update-ref refs/auto-save/<YYYYMMDDTHHMMSSZ>` publishes the snapshot atomically.
4. Prunes to the most recent 10 snapshots.

HEAD, the current branch, the real index, and the working tree are **never** touched. Recovery is `git checkout refs/auto-save/<ts> -- .` (or `git switch -c recovered refs/auto-save/<ts>`).

This fixes the three problems directly: **(1) no working-tree mutation** — in-flight edits survive across turns, so there's no park-and-clean surprise; **(2) no branch switch** — a snapshot is just a ref write, so concurrent agents sharing one tree can't have the tree yanked out from under them; **(3) no same-second collision** — independent Stop events write independent refs (and even an identical timestamp is a benign `update-ref` overwrite of an identical-or-newer snapshot, never a hard abort mid-checkout).

**Why not the alternatives:**

- **Why not keep the branch design and only fix the collision (e.g. append a counter / nanoseconds to the ref name)?** The collision was the least of the three problems. Working-tree mutation and branch switching are inherent to a stash+checkout design — a uniquely-named branch still parks the work and still moves HEAD for the whole shared tree. The redesign had to drop checkout entirely, not harden it.
- **Why hidden refs under `refs/auto-save/` and not `refs/heads/` (branches)?** Snapshots are recovery artifacts, not workstreams. Branches pollute `git branch`, tab-completion, and `git push --all`; a hidden ref namespace keeps the safety net invisible until you ask for it, while staying fully reachable by SHA/ref.
- **Why a temporary `GIT_INDEX_FILE` + `commit-tree` and not `git stash create` (which also doesn't touch the tree)?** `stash create` records a stash commit but its tree-shape and untracked-file handling are awkward to control, and the stash reflog is operator-visible state we don't want to grow. The temp-index path gives exact control over what's captured (full dirty state, gitignore honored) with zero footprint on the real index or stash list.
- **Why `commit-tree` and not `git commit`?** `commit` would require touching the index/HEAD and, critically, honors `commit.gpgsign` — a signing prompt would hang the non-interactive hook. `commit-tree` ignores gpgsign and writes a commit object directly.

### Consequences

**Positive**

- **Multi-agent-safe by construction.** The hook only ever appends a ref. Two agents in one tree, an orchestrator and its sub-agents, or two sessions — each Stop is an independent, idempotent ref write that mutates nothing shared.
- **Edits survive across turns.** The most-reported v0.7.0 surprise ("my uncommitted work disappeared") is gone — the working tree is byte-identical before and after the hook.
- **No branch clutter; sprawl is bounded.** Snapshots don't appear in `git branch`, and auto-prune-to-10 closes the "safety-branch sprawl" / "many branches per session" negatives from the original Consequences — those are now resolved, not just documented.
- **No signing hang.** `commit-tree` can't trigger a gpg prompt, removing a way the non-interactive hook could stall.

**Negative**

- **Old `auto-save/*` branches linger.** Installs that ran v0.1.0 keep their `refs/heads/auto-save/*` branches until manually deleted (`git branch | grep auto-save/ | xargs git branch -D`). The hook.md carries a migration note; there is no automatic migration. (This is the agentm-local cleanup that paired with this release.)
- **Recovery is one indirection less obvious.** `git checkout <branch>` was familiar; `git checkout refs/auto-save/<ts> -- .` is not. Mitigation: the hook prints the exact recovery command on its stderr line, and the how-to documents listing/inspecting/restoring.
- **Snapshots are unreachable by default porcelain.** `refs/auto-save/` won't show in `git log` / `git branch` without an explicit ref or `--all`; an operator who forgets the namespace could think nothing was saved. Mitigation: documented in hook.md + the how-to; the stderr line names the ref each time.

**Load-bearing assumptions** (re-audit triggers)

- **`commit-tree`, `update-ref`, and `GIT_INDEX_FILE` semantics stay stable.** These are git plumbing (very stable), but re-audit if the repo's minimum git version moves or if a future git changes temp-index / hidden-ref behavior.
- **"The working tree" is well-defined at Stop.** Re-audit if a future Claude Code or git feature changes what a single working tree means at Stop time — e.g. shared-worktree, sparse-checkout, or a multi-tree orchestration model where one Stop's snapshot would not capture another agent's concurrently-changing files coherently.
- **`refs/auto-save/` stays a private namespace.** Re-audit if any tooling (the harness, another hook, a CI step) starts writing or relying on `refs/auto-save/` — the prune-to-10 logic assumes the hook is the sole writer.
- The v0.7.0 §3 assumption "**Stop fires with the working tree intact**" is *relaxed*: even if the tree changes between turns, the snapshot model never mutates it, so a stale-snapshot is the worst case (re-captured on the next Stop) rather than a corrupted tree.

## Related

- [Developer Safety](Developer-Safety) — the plugin page: the three hooks, their trigger files, ordering, and troubleshooting.
- [kill-switch hook spec](https://github.com/alexherrero/crickets/blob/main/hooks/kill-switch/hook.md)
- [steer hook spec](https://github.com/alexherrero/crickets/blob/main/hooks/steer/hook.md)
- [commit-on-stop hook spec](https://github.com/alexherrero/crickets/blob/main/hooks/commit-on-stop/hook.md)
- [Customization Types](Customization-Types) — what `kind: hook` means + v0.7.0 installer support.
- [Per-Host Paths](Per-Host-Paths) — where the hook scripts + settings fragments land.
- Installer CLI reference (retired in v3.0) — `--hook` flag + `.claude/settings.json` deep-merge semantics.
- [ADR 0001 — crickets purpose](crickets-hld) — the sibling-repo decision that put these customizations here.
- [ADR 0002 — evaluator design](0002-evaluator-design) — same kind=X-first-consumer pattern at one earlier turn (`kind: agent`).
- [agentm `/work` § Long-running operator-control hooks](https://github.com/alexherrero/agentm/blob/main/harness/phases/03-work.md) — harness-side dispatch.
- [agentm `/release` § commit-on-stop safety net](https://github.com/alexherrero/agentm/blob/main/harness/phases/05-release.md) — harness-side dispatch.
- [cwc-long-running-agents](https://www.anthropic.com/engineering/claude-code-best-practices) — the source pattern (Anthropic's coding-with-Claude best practices).
