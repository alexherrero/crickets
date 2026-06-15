# ADR 0029 — Concurrent-release coordination: tag-from-main, branch protection, single writer

> [!NOTE]
> Status: accepted
> Date: 2026-06-15
> Relates to: [ADR 0028](0028-worktree-authority-config-opt-in.md) (worktree auto-spawn authority), [ADR 0022](0022-retire-worktrees-never-auto.md) (operator-initiated worktrees), [ADR 0023](0023-gate-on-integrated-tree.md) (merge-then-gate)

## Context

[ADR 0028](0028-worktree-authority-config-opt-in.md) shipped per-plan worktree isolation: each plan unit runs in its own `worker/<slug>` worktree and lands via a PR to `main`. With N plans potentially interleaving on `main`, two new failure classes emerge that ADR 0022/0023/0028 do not address:

1. **Tag-tip race:** a concurrent worker creates a tag pointing to a `worker/<slug>` branch tip instead of a `main` commit. If two plans race on the same tag name, one of them force-pushes a published tag — the unrecoverable case the recoverability gate already names but cannot prevent if the tag is created before the branch is merged.
2. **Last-writer-wins on merge order:** without linear-history enforcement, two plans merging concurrently can produce non-linear history where reachability checks become ambiguous.

**Open questions this ADR resolves:**

- Should the tag-reachability check be a pre-tag guard, a `check-*` gate, or both?
- Should a merge-queue bot be introduced at the current scale?
- Should this be a standalone ADR or folded into the ADR 0022-supersession chain?
- What is the re-audit trigger if concurrency grows?

## Decision

Three hardening layers are added, composing on top of the ADR 0028 per-plan worktree foundation:

### 1. `check_tag_reachability.py` gate (code-side backstop)

A `scripts/check_tag_reachability.py` gate runs in both `check-all.sh` (10th gate: "tag-reachability") and the Linux CI workflow. It checks every git tag in the repo points to a commit reachable from `main` (tries `main` first, then `origin/main`; graceful-skip if neither resolves). A `/release` step-7 pre-tag mandate says to run this check before `gh release create`.

**Both guard + gate:** the gate proves the invariant holds after the fact (catching any tag created outside the loop); the `/release` mandate enforces it before the tag is created. Defense in depth.

### 2. `main` branch protection (operator config)

Required CI status checks + squash/rebase-only merges + no force-push + require linear history. Documented as the operator-configured prerequisite in [Configure main branch protection](../how-to/Configure-Main-Branch-Protection.md). The loop *assumes* this is set; `check_tag_reachability.py` is the code-side backstop when it isn't.

### 3. Serialized single writer (`/release` only)

`/release` is the sole path in the loop that creates and pushes tags. `/work` (constraint 11) and `/bugfix` (Non-negotiables bullet) explicitly prohibit tag creation. `/release` constraint 8 documents the sole-writer invariant and the re-audit trigger.

### No merge-queue bot at this scale

At solo / 2–4-plan concurrency, `git merge --no-ff` (integrate-worker) + the linear-history branch protection rule provides sufficient serialization. A merge-queue bot (e.g. Mergify, GitHub's native merge queue) adds setup cost and a third-party dependency that isn't justified until the bottleneck is observable.

### Own ADR (not folded into the supersession chain)

The three hardening layers are a distinct *concurrent-release* concern, not a worktree-authority concern. Folding them into ADR 0028 would make that ADR cover two unrelated topics. A standalone ADR is cleaner and easier to re-audit independently.

## Why not the alternatives

| Alternative | Why rejected |
|---|---|
| Pre-tag guard in `/release` only (no gate) | Defense-in-depth: the gate catches tags created outside the loop (e.g. a manual `git tag`) that the `/release` mandate can't prevent. Both together makes the invariant structurally enforced, not just procedurally. |
| Merge-queue bot | Unjustified overhead at solo / 2–4-plan scale. `/integrate-worker`'s local merge-then-gate already enforces post-merge-green (ADR 0023). Deferred to the re-audit trigger. |
| Fold into ADR 0022-supersession (ADR 0028) | Two distinct concerns in one ADR makes future re-audit harder. Own ADR with cross-references is cleaner. |
| `release-please`/`changesets` now | Significant setup cost and automation scope that isn't justified at current scale. Named as the escalation option when the re-audit trigger fires. |

## Consequences

**Positive:**
- The force-push-on-shared-tag trap is structurally unreachable: `check_tag_reachability.py` catches any off-main tag and CI fails before it can be published.
- Branch protection + linear history makes merge-order deterministic and `git merge-base` reachability unambiguous.
- The single-writer model is explicit in the spec prose and locked by 4 spec tests in `TestTagSerializationContracts`.

**Negative:**
- The tag-reachability gate adds a `git tag --list` + `git merge-base` scan on every `check-all.sh` run — fast for typical tag counts (< 100 tags, < 1ms), negligible in practice.
- Branch protection is operator-configured, not code-enforced — `check_tag_reachability.py` is the backstop when protection is missing.

**Load-bearing assumptions + re-audit triggers:**
- *Assumption:* the tag set stays small (< a few hundred). At large tag counts the `check_tag_reachability.py` scan stays fast (linear in tag count, each tag is one `git rev-list -n1` call). Re-audit if the scan time exceeds 1s in practice.
- *Assumption:* concurrency stays below 4–5 simultaneous landers. **Re-audit trigger:** when a merge-queue bottleneck becomes observable (workers blocking on integrate-worker serially), evaluate `release-please`/`changesets` to parallelize release-note generation while keeping tag serialization.

## Related

- [Configure main branch protection](../how-to/Configure-Main-Branch-Protection.md) — operator setup guide for the four required controls
- [CI gates](../reference/CI-Gates.md) — the `tag-reachability` gate in the gate table
- [ADR 0028](0028-worktree-authority-config-opt-in.md) — the worktree auto-spawn authority this part builds on
- [ADR 0023](0023-gate-on-integrated-tree.md) — the merge-then-gate that enforces post-merge-green
