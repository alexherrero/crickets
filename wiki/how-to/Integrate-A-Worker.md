# How to integrate a finished worker

> [!NOTE]
> **Goal:** Land a finished worker's `worker/<slug>` branch on `main` — but **only if the integrated result still passes the full deterministic battery** — then fold the worker's progress into the mainline log and tidy up its worktree + branch.
> **Prereqs:** the `developer-workflows` plugin installed ([Install crickets plugins](Install-Into-Project)); a worker you [spawned in a worktree](Spawn-A-Worker-In-A-Worktree) whose `/work` session is finished (its `worker/<slug>` branch holds the per-task commits); a **clean `main` working tree** (no in-flight changes); you on `main` in the repo root, not inside the worktree.

Use `/integrate-worker <name>` when a worker has finished its plan and you — the coordinator — decide it is the one to land next. It is the closing step of the coordinator lifecycle: `/plan --stage` → `/plan --activate` → [`/spawn-worker`](Spawn-A-Worker-In-A-Worktree) → run `/work` inside the worktree → **`/integrate-worker`**. After it ships, the spawn→work→integrate worker lifecycle is complete.

`<name>` is the same activated named-plan slug the worker was spawned on (`foo`, `PLAN-foo`, and `PLAN-foo.md` all normalize to `foo`). Merge **order is human-decided**: the command integrates the one worker you name, when you name it — it never auto-sequences merges across workers. For the full command surface (arguments, guards, exit codes), see [Named plans](Named-Plans#integrating-a-worker).

> [!IMPORTANT]
> Three guarantees this command holds: **`main` is never left broken** (a red gate on the integrated tree hard-resets `main` back to where it started), it **never pushes** (the merge is local — pushing stays your act), and progress promotion is **additive** (the worker's `progress-<slug>.md` is appended into the mainline `progress.md`, never deleted; the vault named-plan pair is left untouched).

## Steps

1. **Stand on the integration branch with a clean tree.** From the repo root (not inside the worktree), check out the integration branch — normally `main` — and make sure its working tree is clean (`git status` shows nothing to commit). A dirty tree is a hard refusal: commit or stash any in-flight changes first. Confirm the worker's `/work` session is finished and its `worker/<slug>` branch holds the per-task commits.

2. **Run `/integrate-worker <name>`.** Pass the worker's name — the same activated named-plan slug it was spawned on (`foo`, `PLAN-foo`, and `PLAN-foo.md` all normalize to `foo`). Add `--project-root <path>` only if the repo root isn't your cwd. The command wraps `integrate_worker.py`, which wires the real gate (`bash scripts/check-all.sh`) onto the **merged** tree:
   ```
   /integrate-worker my-feature
   ```
   You choose which worker lands and when — the command integrates the one you name and never auto-sequences merges across workers.

3. **Read the outcome the command reports** (the three rows below in [Outcomes](#outcomes)): GREEN → merged, gate passed, progress promoted, worktree + branch pruned (exit `0`); RED gate → merged then hard-reset back, worktree kept, gate output printed (exit `2`); CONFLICT → `git merge --abort`, worktree kept (exit `2`). The command surfaces the helper's own message verbatim — read that line, don't re-derive it.

4. **On GREEN, push `main` yourself.** The integration is **local** — the command never pushes. Once you're satisfied with what landed, run `git push` to publish the integrated branch:
   ```
   git push
   ```

5. **On RED or CONFLICT, fix inside the surviving worktree, then re-run.** The worktree is left intact for inspection. For a red gate, read the printed gate output and fix the worker's plan in its own `/work` session inside the worktree; for a conflict, resolve the divergence in the worker's branch (e.g. merge `main` into it inside the worktree, re-run its gates). Then re-run `/integrate-worker <name>`.

## Outcomes

The integration runs `scripts/check-all.sh` (the full 8-gate battery) on the **post-merge / integrated** tree — not the worker branch in isolation — so an integration conflict between the worker's work and newer `main` is actually caught. There are three outcomes:

| Outcome | What `/integrate-worker` does | Your worktree | Exit |
|---|---|---|---|
| **GREEN** | merges `worker/<slug>` → `main` (`--no-ff`), gate passes, appends `progress-<slug>.md` into `progress.md`, then prunes the worktree + deletes the merged branch | removed (work landed) | `0` |
| **RED gate** | merged, but the gate failed on the integrated tree → **hard-resets `main` back to the captured pre-merge HEAD**; prints the gate output | left intact for inspection | `2` |
| **CONFLICT** | the merge itself conflicted → `git merge --abort` | left intact | `2` |
| graceful-skip | the located agentm resolver reports no resolvable `_harness/` | untouched | `1` |

After a GREEN integration `main` carries the worker's commits but is **not pushed** — run `git push` yourself once you're ready.

## Verify

After a **GREEN** integration, confirm what landed:

- `git log --oneline --merges -1` on `main` shows the `--no-ff` integration merge commit for `worker/<slug>`.
- The mainline `progress.md` carries the appended `progress-<slug>.md` entries plus a one-line integration record (the worker's named `progress-<slug>.md` is **kept** — promotion is additive).
- `git worktree list` no longer shows the worker's worktree, and `git branch --list worker/<slug>` is empty (pruned via the safe `git branch -d`).

After a **RED gate** or **CONFLICT** (exit `2`), confirm nothing changed:

- `git log --oneline -1` on `main` is the same commit it was before you ran the command (the rollback hard-reset it back, or the merge was aborted before any commit).
- `git worktree list` still shows the worker's worktree and `worker/<slug>` still exists — left intact for you to fix and re-run.

## Troubleshooting

- **`/integrate-worker` refused (exit 2) and changed nothing.** Every guard runs *before* any merge, so a refusal leaves `main` and the worktree untouched. It refuses on: an empty/singleton name; a missing `worker/<slug>` branch; an undiscoverable worktree; a **dirty `main` working tree** (commit or stash your in-flight changes first); or an unresolvable plan/progress pair. Fix the named condition, then re-run.
- **The gate went red and `main` rolled back.** This is by design — `main` is never left broken. Read the printed gate output, fix the worker's plan inside the surviving worktree (its `/work` session), then re-run `/integrate-worker <name>`.
- **The merge conflicted.** The command aborted the merge and left the worktree intact. Resolve the divergence in the worker's branch (rebase/merge `main` into it inside the worktree, re-run its `/work` gates), then re-run.
- **Worktrees piling up after integrations?** Run the read-only `doctor_worktrees.py` probe — it lists every `worker/<slug>` worktree and classifies each (active · merged-but-unpruned · orphaned · dangling-marker) with its plan mapping. It mutates nothing; you prune on demand. See [Named plans](Named-Plans#integrating-a-worker).

## Related

- [Spawn a worker in a worktree](Spawn-A-Worker-In-A-Worktree) — the open of the lifecycle this command closes: hand an activated named plan to a worker in its own checkout.
- [Named plans](Named-Plans#integrating-a-worker) — the lookup: `/integrate-worker`'s arguments, guards, exit codes, and the `doctor_worktrees.py` probe.
- [Run a named plan](Run-A-Named-Plan) — author + stage + activate the plan a worker binds to.
- [ADR 0022 — worktrees first-class but operator-initiated](0022-retire-worktrees-never-auto) — the norm that sanctions the worker worktrees this command merges and prunes.
- [ADR 0023 — gate the integrated tree](0023-gate-on-integrated-tree) — *why* the gate runs on the merged tree and `main` hard-resets on red rather than gating the worker branch in isolation.
- [Developer Workflows](Developer-Workflows) — the phase-loop plugin this command belongs to.
