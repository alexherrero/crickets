# ADR 0030 — Generated artifacts have a single writer: defer the version bump to the serialized integrator

> [!NOTE]
> Status: accepted
> Date: 2026-06-15
> Relates to: [ADR 0029](0029-concurrent-release-coordination.md) (concurrent-release coordination — single tag writer), [ADR 0028](0028-worktree-authority-config-opt-in.md) (per-plan worktree isolation), [ADR 0023](0023-gate-on-integrated-tree.md) (merge-then-gate), [ADR 0021](0021-per-plugin-versioning.md) (per-plugin versioning + the bump guard)

## Context

The first concurrent auto-spawn run (2026-06-15) proved the build half of the worktree-PR loop works: N workers built **disjoint source** in their own `worker/<slug>` worktrees and produced clean PRs. The contention was entirely at **integration** — and almost every conflict was in one place: the generated artifacts.

Two committed-to-`main` generated outputs are shared by *every* plugin:

1. **`.claude-plugin/marketplace.json`** (and the Antigravity analog) — a single registry listing **all** plugins with their versions, generated from each `src/<slug>/group.yaml` `version:` field.
2. **`dist/`** — the committed build tree consumers pull from.

A load-bearing CI gate, **`generate.py check`** ("dist/ in sync with src/"), forces every branch to regenerate `dist/` + the marketplace pointers from `src/` on-branch. So when two concurrent workers each bumped their plugin's version and regenerated, both rewrote the shared `marketplace.json` and overlapping `dist/` stamps — and the branches rebased against each other repeatedly. [ADR 0029](0029-concurrent-release-coordination.md) made the **tag** a single serialized writer; it never touched the **generated artifacts** that carry the version registry.

**Open questions this ADR resolves:**

- Who owns the version bump + the generated registry: the worker, or a serialized integrator?
- Given the on-branch `dist-sync` gate, can the cross-plugin `marketplace.json` collision be removed *without* weakening that gate on `main`?
- Which gate (if any) must become branch-aware, and what stays authoritative everywhere?
- Standalone ADR or a fold into the ADR 0021/0029 lineage?

## Decision

**Generated artifacts have a single writer = the serialized integrator. Workers defer the version bump; nothing else.**

Concretely, the model (call it **Model A — defer-bump-only**):

### 1. Workers commit source + `dist/` regenerated at the *current* (unbumped) version

A `worker/<slug>` branch changes `src/<plugin>/`, then regenerates `dist/` **at the version already on `main`** — it does **not** bump `group.yaml` `version:`, and therefore does **not** touch any `marketplace.json` version entry. The branch still fully builds and verifies: `dist/` matches `src/` at the current version, so the `dist-sync` gate passes on the branch exactly as on `main`.

Because no branch ever changes a version line, the cross-plugin `marketplace.json` collision is **structurally gone** — disjoint-plugin landings touch disjoint `dist/<plugin>/` files only; the shared registry is never written on a branch.

### 2. The serialized integrator owns the bump + registry + final regen

`/integrate-worker` (then `/release`), as the single serialized writer ([ADR 0029](0029-concurrent-release-coordination.md)'s lock/marker, **not** a merge-queue bot at this scale), performs — from current `main`, once per landing — the sequence: merge worker `src` + `dist` → bump the affected plugin's `version:` → regenerate `dist/` + `marketplace.json` (now the registry version line moves) → commit. The version registry changes **only on `main`, by one writer, one landing at a time.**

### 3. Gate disposition — the load-bearing part

| Gate | On a `worker/<slug>` branch | On `main` |
|---|---|---|
| **`dist-sync`** (`generate.py check`) | **Fully authoritative — unchanged.** Workers keep `dist/` in sync at the current version, so the gate bites identically on the branch. | **Fully authoritative.** Never relaxed. |
| **`version-bump`** (`check-version-bump.py`) | **Branch-aware:** in a deferred-bump worker context the absent bump is *expected*, so the gate treats it as a graceful pass (advisory), not a failure. | **Fully authoritative.** Every shipped `src/` change must clear the published version — the integrator's bump satisfies this on the net `HEAD`-vs-baseline diff the gate already measures. |

This is **tighter than the constraint anticipated.** The plan permitted relaxing `dist-sync` to be branch-aware *if* the chosen model deferred regeneration. By deferring **only the bump** (workers still regenerate `dist/` at the current version), `dist-sync` needs **no** change and stays authoritative everywhere — the only gate that becomes branch-aware is `version-bump`, whose entire job is to demand a bump the integrator now owns. The "never weaken `dist-sync` on `main`" constraint is satisfied by leaving it untouched.

The branch-aware signal for `version-bump` is a **deferred-bump worker context** — the `worker/<slug>` branch convention or an explicit defer marker/env, composing with the gate's existing `$VERSION_BUMP_BASE` CI input. The exact signal is fixed in implementation (this ADR locks the *contract*, not the wiring).

### Own ADR (not folded)

Generated-artifact contention is a distinct concern from tag coordination (0029) or per-plugin versioning's anti-recurrence guard (0021). A standalone ADR keeps each re-auditable independently; it cross-references the lineage rather than expanding any one of them to cover two topics — consistent with 0029's own "own ADR" call.

## Why not the alternatives

| Alternative | Why rejected |
|---|---|
| **B — per-plugin `marketplace.json` fragments** assembled by the generator, so disjoint-plugin landings never textually collide | Adds a fragment-assembly layer and a new file-layout to maintain, and it only removes *cross-plugin* registry collisions — same-plugin concurrent edits still collide, and the `dist/` regen-forcing is untouched. Model A removes the cross-plugin collision with **zero** new machinery (workers just stop bumping). Fragment-split is noted as a possible future *complement* if same-plugin concurrency becomes common, not the primary fix. |
| **C — union merge-driver** (`.gitattributes merge=union` on `marketplace.json`) | A stopgap that *hides* the conflict by concatenating both sides rather than removing it — produces duplicate/garbled registry entries on real divergence and still forces on-branch regen. Conflict-avoidance-by-construction (Model A) beats conflict-masking. |
| **Defer regeneration too** (workers commit `src` only; `dist-sync` skipped on branches) | Strictly weaker branch CI: a worker branch whose `dist/` is stale can't verify its own build, so a generation break wouldn't surface until integration. Deferring **only** the bump keeps the branch fully verifiable and confines the gate relaxation to the one gate (`version-bump`) that exists to demand the deferred action — leaving `dist-sync` authoritative everywhere. |
| **A merge-queue bot now** (Mergify / GitHub merge queue) | Unjustified overhead at solo / 2–4-plan scale; [ADR 0029](0029-concurrent-release-coordination.md)'s serialize-with-a-marker call stands. Re-audit when simultaneous landers exceed a handful. |

## Consequences

**Positive:**

- The cross-plugin `marketplace.json` collision is structurally unreachable: no branch ever writes a version line, so disjoint-plugin landings cannot conflict on the registry.
- `dist-sync` stays fully authoritative on every branch and on `main` — the load-bearing build-integrity gate is *strengthened in scope* (untouched) rather than relaxed.
- The version registry has one writer (the integrator) and one write point (`main`), extending [ADR 0029](0029-concurrent-release-coordination.md)'s single-writer model from tags to generated artifacts.
- Worker branches stay fully buildable and verifiable — only the version *label* is deferred.

**Negative:**

- A worker-branch PR is intentionally "incomplete": it carries `src` + `dist` at the *current* version, not the bumped/shipped artifact. The shipped artifact is produced once, deterministically, at integration. (Accepted: the branch still builds + tests green; see the re-audit trigger.)
- `version-bump` gains a branch-aware code path — a small added surface that must be proven *not* to leak its relaxation onto `main` (the integration test must show `main` enforcement intact).
- Same-plugin concurrent edits remain a genuine conflict — by design. Model A removes *incidental* cross-plugin registry churn, not true overlap; those surface clearly rather than auto-merging.

**Load-bearing assumptions + re-audit triggers:**

- *Assumption:* concurrency stays at solo / 2–4 simultaneous landers, so a serialized single-writer integrator (marker/lock) is sufficient. **Re-audit trigger:** when workers observably block on serial integration, evaluate a merge queue (the shared 0029 trigger).
- *Assumption:* same-plugin concurrent edits stay rare. **Re-audit trigger:** if two workers routinely edit the same plugin, revisit Model B's per-plugin fragment split as a complement.
- *Assumption:* a deferred-bump branch context is reliably detectable in CI (branch convention / marker). **Re-audit trigger:** if a CI topology change (e.g. a checkout that loses the branch name) makes the signal unreliable, move it to an explicit env/marker.

## Related

- [ADR 0029](0029-concurrent-release-coordination.md) — the single tag writer this extends to generated artifacts
- [ADR 0023](0023-gate-on-integrated-tree.md) — the merge-then-gate the integrator runs on the post-merge tree
- [ADR 0021](0021-per-plugin-versioning.md) — per-plugin versioning + the `check-version-bump.py` guard that becomes branch-aware here
- [CI gates](../reference/CI-Gates.md) — the `dist-sync` + `version-bump` gates in the gate table
