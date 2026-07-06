---
name: spawn-worker
description: Operator-authority-required — give a named plan its own isolated checkout by spawning a worker git worktree on a fresh worker/<name> branch, pre-bound to that plan. Spawning without operator authority is forbidden.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: <name> [--project-root <path>] [--worktree-path <path>] — <name> is the worker name AND the activated named-plan slug it binds to
---

You are running **spawn-worker** — the worktree step of the coordinator flow. It hands one **activated named plan** to a worker by creating a `git worktree` on a fresh `worker/<name>` branch and pre-binding it to that plan, so a `/work` session run *inside* the worktree resolves its own `PLAN-<name>.md` without re-passing `--name`. It wraps the `spawn_worker.py` helper and surfaces the helper's result; it does not re-derive resolution.

**Arguments:** $ARGUMENTS — the first token is `<name>` (the worker name, which is also the activated named-plan slug it binds to). Optionally `--project-root <path>` (default: cwd) and `--worktree-path <path>` (default: `<repo>.worktrees/<name>` beside the repo).

> **Operator authority required — never without it** (the V5-10 design call — the worktree operator-authority rule, developer-safety design; refined by the worktree-per-plan plan). Authority = an explicit invocation of this command OR a durable `isolation.mode: worktree-per-plan` config opt-in in `.harness/project.json`. A session never spawns a worktree without operator authority — no silent auto-spawn. This command is the *explicit-command* path: when the **operator** invokes it, creating the worktree IS the initiation. It fits the coordinator flow after a plan is staged and activated: `/plan --stage` → `/plan --activate` → **`/spawn-worker`** → launch a `/work` session in the new worktree. Do not invoke it speculatively or as a side effect of another task.

## Non-negotiable constraints

1. **Operator authority required.** Authority = an explicit invocation of this command OR a durable `isolation.mode: worktree-per-plan` config opt-in. Never spawn a worktree without operator authority — no silent auto-spawn, never as cleanup or convenience for another task.
2. **Named plans only — the singleton is refused.** `<name>` must be a real named-plan slug (`foo`, `PLAN-foo`, `PLAN-foo.md` all → `foo`). An empty or singleton name exits 2; the singleton plan cannot be handed to a worker.
3. **No-clobber, no partial spawn — the helper owns it.** Every guard runs *before* any mutation: a pre-existing worktree path (even a dangling symlink) or `worker/<name>` branch exits 2 with stderr and creates **nothing**. A non-zero plan resolve (unsafe slug, dangling marker, missing/empty `PLAN-<name>.md`) is authoritative and propagated — the worktree is never created for a plan that doesn't resolve. Do not work around a refusal; report it.
4. **Surface the helper's output verbatim.** On success the helper prints the new worktree path on stdout; on refusal it prints the reason on stderr. Show the operator what the helper said — do not paraphrase the path or invent a reason.

## Process

1. **Run the helper.** Invoke `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spawn_worker.py" <name>` (append `--project-root <path>` / `--worktree-path <path>` only if the operator passed them in `$ARGUMENTS`). It writes the worktree-local `.harness/active-plan` marker as the **bare slug** — the exact case-preserving form agentm's `resolve_active_plan` reads back — so the binding needs no `--name`.
2. **On exit 0 — report the worktree and the next step.** Print the worktree path the helper emitted, then tell the operator how to start the worker:
   > Worktree ready at `<path>` on branch `worker/<name>`. Start the worker with: `cd <path>` then run `/work` — the worktree-local marker binds it to `PLAN-<name>.md`, no `--name` needed.
3. **On exit 2 — surface the refusal and stop.** Show the helper's stderr (named-only / no-clobber / resolver refusal / failed `git worktree add`). Do not retry with a mutated name or path to dodge the guard; the guard is the contract. If the path or branch already exists, the operator chooses whether to remove it or pick a different name.
4. **On exit 1 — graceful-skip.** A located agentm resolver reported no resolvable `_harness/` (e.g. the project isn't bound to a vault). Report it plainly; spawn nothing.
5. **On exit 3 — already shipped, benign no-op (LC-6).** The resolved plan declares `expected_artifacts` and every one already exists on `main`, so the lane is already shipped — the helper refused **before any mutation** (no worktree, no branch). Report the `already shipped — nothing to do` message and stop; this is the defense-in-depth backstop to `/plan --activate`'s reconcile, not an error to retry past. The work is done; pick a different plan.

## What this command does not do

It does not stage, activate, or author a plan (that's `/plan --stage` / `--activate`), does not run the worker's `/work` for you, and does not prune or merge worktrees (integration/merge is separate, deferred work). It creates one pre-bound worktree and hands it back — the worker is launched, and later integrated, by the operator.
