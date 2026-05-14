# ADR 0003: Base operator-control hooks — kill-switch, steer, commit-on-stop

> [!NOTE]
> **Status:** accepted
> **Date:** 2026-05-14

## Context

The cwc-long-running-agents pattern (`~/ContextVault/domains/anthropic-patterns/cwc-long-running-agents.md`) identifies three operator-precision primitives that any long-running agent workflow benefits from but the harness's existing surface area doesn't provide:

1. **Precise halt** — today, the only way to halt a runaway iteration loop in a Claude Code session is to close the session. That loses in-flight context the agent had built up; restarting is expensive (tokens, time, mental re-loading by the operator).
2. **Mid-run redirect** — today, the only way to redirect an agent that's heading the wrong direction is to interrupt-and-restart. Same cost as above. The operator-typed correction is unreliable mid-stream because the agent has to acknowledge + apply it in the same response that may be already mid-action.
3. **Crash recovery** — today, a crashed Claude Code session (or one closed mid-task) loses any uncommitted work. Recovery is "hope you committed recently."

The harness's existing hook surface (`PostToolUse` for verify, `PreCompact` for compact, `SessionStart` for state-load) is harness-shape-specific. The three operator-control primitives are host-cross-cutting and consumer-cross-cutting: they're useful for the harness's `/work` + `/release` phases, the future design skill (#6), the quality-gates bundle (#10), and any long-running custom skill. The natural home is `agent-toolkit`.

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
- **Synthetic commit identity.** commit-on-stop commits as `commit-on-stop@agent-toolkit.local` (scoped to the single commit via `git -c user.email=...`). The identity is fake but obvious in `git log`. Mitigation: the identity is documented in the hook body + this ADR; intentional choice to keep auto-saves visually distinct from operator commits in history.

**Load-bearing assumptions** (re-audit on every Claude Code release + every toolkit installer change)

- **Claude Code runs hooks within an event in registration order.** Kill-switch-before-steer enforcement depends on this.
- **`PreToolUse` exit 2 blocks the tool call + surfaces stderr to the agent.** Kill-switch's halt mechanism depends on this. If Claude Code changes the convention, kill-switch's halt behavior breaks.
- **`Stop` event fires at agent turn-end with the working tree intact at that moment.** commit-on-stop's safety-branch timing depends on this. If Stop fires after Claude Code wipes the working tree (e.g. for cleanup), commit-on-stop's snapshot is wrong.
- **`PreToolUse` hook stdout is captured and injected into agent context.** Steer's redirect mechanism depends on this.
- **The toolkit installer registers hooks in alphabetical filesystem order.** Hook ordering invariant depends on this.

## Related

- [How to use the base operator-control hooks](Use-The-Base-Hooks) — practical recipes with three worked scenarios + manual equivalents for other hosts.
- [kill-switch hook spec](https://github.com/alexherrero/agent-toolkit/blob/main/hooks/kill-switch/hook.md)
- [steer hook spec](https://github.com/alexherrero/agent-toolkit/blob/main/hooks/steer/hook.md)
- [commit-on-stop hook spec](https://github.com/alexherrero/agent-toolkit/blob/main/hooks/commit-on-stop/hook.md)
- [Customization Types](Customization-Types) — what `kind: hook` means + v0.7.0 installer support.
- [Per-Host Paths](Per-Host-Paths) — where the hook scripts + settings fragments land.
- [Installer CLI](Installer-CLI) — `--hook` flag + `.claude/settings.json` deep-merge semantics.
- [ADR 0001 — agent-toolkit purpose](0001-agent-toolkit-purpose) — the sibling-repo decision that put these customizations here.
- [ADR 0002 — evaluator design](0002-evaluator-design) — same kind=X-first-consumer pattern at one earlier turn (`kind: agent`).
- [agentic-harness `/work` § Long-running operator-control hooks](https://github.com/alexherrero/agentic-harness/blob/main/harness/phases/03-work.md) — harness-side dispatch.
- [agentic-harness `/release` § commit-on-stop safety net](https://github.com/alexherrero/agentic-harness/blob/main/harness/phases/05-release.md) — harness-side dispatch.
- [cwc-long-running-agents](https://www.anthropic.com/engineering/claude-code-best-practices) — the source pattern (Anthropic's coding-with-Claude best practices).
