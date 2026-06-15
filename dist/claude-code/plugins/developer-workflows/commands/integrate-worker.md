---
name: integrate-worker
description: Operator-initiated — land a finished worker's worker/<name> branch on the integration branch, but only if the merged tree still passes the full deterministic battery; then fold the worker's progress into mainline and prune its worktree + branch. Never autonomous, never pushes.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: <name> [--project-root <path>] — <name> is the worker name AND the named-plan slug it was spawned on
---

You are running **integrate-worker** — the closing step of the coordinator flow. It is the lifecycle counterpart to [`/spawn-worker`](spawn-worker.md): where spawn-worker hands a named plan to an isolated worker, integrate-worker **lands** that worker. It merges the worker's `worker/<name>` branch into the integration branch (normally `main`), runs the full deterministic battery **on the merged result**, and only on green folds the worker's progress into the mainline log and prunes the worktree. It wraps the `integrate_worker.py` helper and surfaces the helper's result; it does not re-derive resolution, the merge, or the gate.

**Arguments:** $ARGUMENTS — the first token is `<name>` (the worker name, which is also the named-plan slug the worker was spawned on). Optionally `--project-root <path>` (default: cwd).

> **Operator-initiated, never autonomous, merge order human-decided** (the V5-10 design call; ADR 0022). A normal session never merges a worker on its own. This command is the *sanctioned* coordinator action: when the **operator** invokes it, deciding which worker lands next IS the initiation. It fits at the end of the coordinator flow: `/plan --stage` → `/plan --activate` → [`/spawn-worker`](spawn-worker.md) → launch a `/work` session in the worktree → **`/integrate-worker`**. It integrates the one worker you name, when you name it — it never auto-sequences merges across workers.

## Non-negotiable constraints

1. **Operator-initiated only.** Run this exclusively when the operator asks for it, naming the worker to land. Never integrate a worker autonomously, never as cleanup or convenience for another task.
2. **Named plans only — the singleton is refused.** `<name>` must be a real named-plan slug (`foo`, `PLAN-foo`, `PLAN-foo.md` all → `foo`). An empty or singleton name exits 2; the singleton plan has no `worker/<name>` branch to integrate.
3. **`main` is never left broken — the helper owns it.** The gate runs on the **post-merge / integrated** tree, not the worker branch in isolation, so an integration that merges cleanly but breaks `main` is caught. A merge **conflict** is `git merge --abort`-ed; a **red gate** hard-resets the integration branch back to the captured pre-merge HEAD (zero commits added). Every refusal leaves the worker's worktree + branch intact for inspection. Do not work around a rollback or retry to dodge a red gate; the gate is the contract.
4. **It does not push, and never bypasses branch protection.** The merge is **local** — publishing the integrated `main` stays the operator's act. Never push as a side effect of integrating. When the operator *does* land the integrated branch, it goes **through branch protection + required CI** — squash, wait for required checks green, then merge — never an admin override (LC-3). Build fans out N-wide; integration lands one at a time through the protected path.
5. **Promotion is additive.** On green the worker's `progress-<slug>.md` is *appended* into the mainline `progress.md` (the named file is kept; the vault plan/progress pair is left untouched). A promotion or prune failure after a green merge does **not** undo the merge — it is reported for manual cleanup.
6. **Surface the helper's output verbatim.** On success the helper prints a one-line integration summary on stdout; on refusal/rollback it prints the reason on stderr. Show the operator exactly what the helper said — do not paraphrase the result or invent a reason.
7. **Integration is serialized — one at a time (LC-1/LC-5).** The helper holds a per-repo advisory lock (`.git/integrate.lock`, separate from spawn's worktree-add lock) across the whole merge → gate critical section, so a second concurrent `/integrate-worker` **blocks** rather than racing on the shared integration branch + version registry (ADR 0030). Build is N-wide; the integrator is the single writer. Do not work around the lock to land two workers at once.

## Process

1. **Run the helper from the integration branch.** From the repo root, on the integration branch (normally `main`) with a clean working tree, invoke `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/integrate_worker.py" <name>` (append `--project-root <path>` only if the operator passed it in `$ARGUMENTS`). The command wires the **real gate**: the helper's default gate runs `bash scripts/check-all.sh` in the repo root on the merged tree. Do not run this from inside the worktree.
2. **On exit 0 — report what landed and the next step.** Print the helper's summary (merged `worker/<name>` → the integration branch, progress promoted, worktree + branch pruned), then remind the operator:
   > Integrated `worker/<name>` into `<branch>` and pruned the worktree. `<branch>` is **not pushed** — run `git push` yourself when ready.
   If the helper's stderr carried a best-effort warning (promotion or prune incomplete), surface it too — the merge stands, but the named survivor needs manual cleanup.
3. **On exit 2 — surface the refusal/rollback and stop.** Show the helper's stderr (named-only · missing `worker/<name>` branch · undiscoverable worktree · detached/dirty integration branch · resolver refusal · merge **conflict aborted** · **red gate rolled back**). `main` and the worktree are untouched/restored — do not retry with a mutated name to dodge the guard. For a red gate, the printed gate output is the signal: fix the worker's plan inside its surviving worktree (its own `/work`), then re-run.
4. **On exit 1 — graceful-skip.** A located agentm resolver reported no resolvable `_harness/` (e.g. the project isn't bound to a vault). Report it plainly; integrate nothing.

## What this command does not do

It does not push the integrated branch (the merge is local — `git push` stays the operator's act), does not author/stage/activate a plan (that's `/plan`), does not run the worker's `/work` for you, does not auto-resolve merge conflicts, does not auto-sequence merges across workers (you name the one to land), and does not delete or archive the vault named-plan/progress pair (promotion is additive). To survey worktrees needing attention, use the read-only `doctor_worktrees.py` probe.
