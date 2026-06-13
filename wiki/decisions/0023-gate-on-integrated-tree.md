# ADR 0023 — Gate the integrated tree, not the worker branch: merge-then-gate with hard-reset rollback

> [!NOTE]
> Status: accepted
> Date: 2026-06-13

## Context

[ADR 0022](0022-retire-worktrees-never-auto) sanctioned operator-initiated worker worktrees and named [`/spawn-worker`](Spawn-A-Worker-In-A-Worktree) as the open of the worker lifecycle. V5-10 sibling #3 ships its close: [`/integrate-worker <name>`](Integrate-A-Worker), the coordinator-invoked command that **lands** a finished worker's `worker/<slug>` branch onto the integration branch (normally `main`). ADR 0022 settled *who* may create a worktree (operator-initiated, never autonomous); it said nothing about *how* a finished worker's work is validated before it lands. That is this decision.

A worker's branch passed its own gates when its `/work` session finished — but it was gated **in isolation**, against the `main` it branched from. By the time the coordinator integrates it, `main` has usually moved (other workers landed, hand-fixes shipped). A branch that was green on its own can still break the integrated tree: an API another worker changed, a test another worker added, a file both touched. Gating the branch alone proves nothing about the result of the merge.

**Open questions the decision resolves:**

- What is the unit of work the gate runs on — the worker branch in isolation, or the post-merge integrated tree?
- If the gate fails *after* the merge has already been recorded, what state is `main` left in? Who guarantees it is not left broken?
- Does protecting `main` require the command to push, or to coordinate with a remote in any way?

## Decision

**Gate the integrated tree, and make the integration atomic from `main`'s point of view via merge-then-gate with hard-reset rollback.** `/integrate-worker` (the `integrate_worker.py` helper) does, in order, on the integration branch:

1. **Capture the pre-merge HEAD** of the integration branch ([`_head_sha`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/integrate_worker.py#L142)) — the rollback anchor.
2. **Merge `--no-ff`** (`git merge --no-ff worker/<slug>`, [`:375`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/integrate_worker.py#L375)) — preserves the worker's per-task commits *and* records an explicit integration point, so the merge can be reasoned about (and pruned safely) as one unit.
3. **Run the full battery on the merged HEAD** — `bash scripts/check-all.sh` ([`_check_all_gate`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/integrate_worker.py#L283), the production `_DEFAULT_GATE`), evaluating the *post-merge* tree, not the branch in isolation.
4. **On red, hard-reset back** to the captured pre-merge HEAD ([`_restore_to`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/integrate_worker.py#L167) → `git reset --hard`), so zero commits are added. **On conflict, `git merge --abort`** before any commit exists. Either way the integration branch ends exactly where it started, and the worktree is left intact for the operator to fix and re-run.
5. **On green**, promote progress (additive) then prune the worktree + branch.

The integration is **local** — the command never pushes. Publishing the integrated branch stays the operator's explicit act (`git push`), consistent with the operator-initiated framing of [ADR 0022](0022-retire-worktrees-never-auto).

**Why not gate the worker branch in isolation (gate, then merge if green)?** That validates the wrong artifact. It proves the branch was green against its *old* base, not against the `main` it is about to join — exactly the integration conflicts (a moved API, a newer test, a doubly-touched file) the worker model makes routine. Gating before the merge would let a branch that is individually green break the integrated tree, which is the one thing landing is supposed to prevent.

**Why not merge and leave `main` broken when the gate fails (let the operator clean up)?** A broken `main` is a shared-state failure: every other worker branches from it, every `/queue-status-lite` glance reads it, the next integration gates against it. Leaving it red converts one worker's failure into everyone's. The hard-reset makes the integration **atomic from `main`'s perspective** — it either lands clean or it never happened — which is the guarantee worth holding. The cost (re-running the merge after a fix) is borne by the one failing worker, not the whole team.

**Why not three-way / rebase-and-fast-forward instead of `--no-ff`?** `--no-ff` records an explicit integration commit, which is what makes the rollback anchor unambiguous (reset to the parent) and the green-path prune safe (`git branch -d`, not `-D`, because the merge made the branch an ancestor of HEAD — [`_branch_safe_gone`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/integrate_worker.py#L196)). A fast-forward would erase the integration boundary the rollback and the safe-prune both rely on.

## Consequences

**Positive**

- **`main` is never left broken.** The integration is atomic from `main`'s point of view: clean-land or no-op. A red gate or a conflict leaves the integration branch byte-identical to where it started and the worktree intact for a fix-and-retry.
- **Integration conflicts are actually caught.** Because the gate runs on the merged tree, a worker that was green in isolation but breaks against newer `main` fails *at integration*, not silently after landing.
- **No remote coupling.** The merge is local and the command never pushes, so the guarantee holds with no network, no remote race, and the publish decision stays the operator's.
- **Safe, explicit cleanup.** `--no-ff` makes the green-path prune use the safe `git branch -d` (refuses to delete unmerged work) rather than a force delete.

**Negative / accepted debt**

- **A red integration does duplicate work.** The merge + full `check-all.sh` run, then a hard-reset throwing it away — wasted on every failed attempt. Accepted: correctness of `main` outranks the cost of re-running a gate on a branch that wasn't actually ready.
- **The hard-reset assumes the integration branch's pre-merge HEAD is the only thing to protect.** Pre-mutation guards enforce a **clean working tree** ([Pre-mutation guards](Named-Plans#integrating-a-worker)) precisely so the `git reset --hard` can't destroy uncommitted operator work — but that protection is the guard's, not the reset's. The reset is only safe *because* the dirty-tree refusal runs first.
- **Gating the merged tree means the gate definition is load-bearing at integration time.** If `scripts/check-all.sh` is itself broken or absent, the [gate fail-safe](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/integrate_worker.py#L293) treats it as red (refuse to land) rather than green (land blind) — a missing gate must never read as a pass.

**Load-bearing assumptions + re-audit triggers**

- *The integration branch's history is local and resettable.* The rollback is a `git reset --hard` to a captured SHA — safe only because nothing has been pushed between merge and gate. **Re-audit if** `/integrate-worker` ever gains a push step, integrates against a shared/published branch mid-flight, or runs anywhere the integration branch isn't exclusively the coordinator's to reset. A published commit cannot be silently hard-reset away.
- *The full battery is the right gate to run on the merged tree.* `check-all.sh` is run verbatim. **Re-audit if** the battery grows a step that is unsafe or nonsensical to run on a transient merge HEAD (e.g. something that publishes, tags, or mutates remote state), since the merged tree is thrown away on red.

## Related

- [Integrate a worker](Integrate-A-Worker) — the `/integrate-worker` how-to; the operator-facing recipe this decision sits behind.
- [Named plans § Integrating a worker](Named-Plans#integrating-a-worker) — the command surface: merge strategy, gate, rollback, exit codes, and the read-only `doctor_worktrees.py` cleanup probe.
- [ADR 0022 — worktrees first-class but operator-initiated](0022-retire-worktrees-never-auto) — the sibling decision: this one governs *how* a worker lands; 0022 governs *who* may create the worktree it lands from.
- [Spawn a worker in a worktree](Spawn-A-Worker-In-A-Worktree) — the open of the lifecycle this integration closes.
- [Developer Workflows](Developer-Workflows) — the phase-loop plugin `/integrate-worker` belongs to.
