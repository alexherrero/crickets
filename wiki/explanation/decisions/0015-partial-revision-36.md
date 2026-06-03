# ADR 0015 — #36 partial-revision: #40 proves the architecture, defers the catalog moves

> [!NOTE]
> Status: accepted
> Date: 2026-06-02

## Context

The V4 #36 reorganization moved the compound skills (`design`, `diataxis-author`, `ship-release`) and the agentic-memory layer into `agentm`, leaving crickets with its base primitives. The full v3.x catalog envisioned in the HLD — Developer (base) plus Testing, Releasing, Wiki, Design-docs, GitHub-CI, PII, and the knowledge/personal set — is mostly still to be built, and several of the #36 skills still physically live in `agentm/harness/`. When #40 (the native-plugin model, [ADR 0013](0013-bundles-native-plugins)) landed, it raised a scope question that this ADR resolves. HLD: [crickets-v3-native-plugins](../designs/crickets-v3-native-plugins).

**Open questions the decision resolves:**

- Does #40 do the full #36 reorg + catalog build, or only prove the architecture?
- If the moves are deferred, what is the contract for the deferred work — and why record it now rather than just doing it?

## Decision

### 1. #40 is architecture-only + proof scope (design Decision 3)

#40 proves the native-plugin model on crickets' **existing** primitives, and dogfoods install on both hosts across the operator's repos:

- `pii-scrubber` → a standalone PII plugin.
- `commit-on-stop` / `kill-switch` / `steer` + the `evaluator` agent → the grouped **Developer** plugin.
- `dependabot-fixer` → **GitHub-CI**; `diataxis-evaluator` → **Wiki**.

That is four groups / seven primitives — enough to exercise every emitter path (skills, agents, hooks, marketplace, dependencies, the snippet/rules gap) and to dogfood install + load + fire on both hosts.

### 2. Defer the #36 skill relocations + the full catalog to bucket ④

The following are **explicitly out of #40** and tracked for bucket ④:

- The #36 skill *relocations*: `design` → Design-docs, `diataxis-author` → Wiki, `ship-release` → Releasing.
- The full **Developer-base composition** + the new bundles (Testing, Releasing, knowledge/personal).

**Why defer rather than do it all in #40?** Proving the architecture is #40's goal; relocating skills and building the catalog is independent, larger work that builds *cleanly on top of* the proven generator. Bundling it into #40 would balloon a focused, shippable proof into an open-ended migration.

**Why write this ADR now rather than just doing the moves later?** To record the scope boundary as a contract. Without it, a future reader sees a sparse catalog and a half-applied #36 and cannot tell whether #36 was *partially revised on purpose* or *abandoned*. This ADR is the "on purpose" — it hands bucket ④ a clear starting contract.

## Consequences

### Positive

- **#40 stays scoped and shippable** — a clean architecture proof, not a migration.
- **Bucket ④ inherits a clear contract**: a proven generator + a named list of moves and bundles still to build.

### Negative

- **The catalog is sparse after #40** (four groups, seven primitives). The opinionated full set the HLD describes is mostly future work.
- **The crickets/agentm boundary is not yet at its #36 target** — the three compound skills still live in `agentm/harness/` until ④ relocates them.

### Load-bearing assumptions + re-audit triggers

1. **The generator scales to the full catalog without rework.** It was proven on four groups / seven primitives; Testing and Releasing will be the first genuinely new groups. **Re-audit when bucket ④ builds the first new bundle** — if a new primitive kind or host mapping needs generator changes, surface them then rather than assuming a pure data-add.
2. **The #36 target boundary still holds.** The deferred moves assume the crickets/agentm split lands where #36 put it. **Re-audit if the split shifts again before ④ executes** (e.g. a skill moves a second time) — the deferred-moves list in this ADR would need updating.

## Related

- [crickets-v3-native-plugins](../designs/crickets-v3-native-plugins) — the HLD; design Decision 3 (architecture-only + proof scope)
- [ADR 0013](0013-bundles-native-plugins) — the native-plugin model #40 proved
- [ADR 0014](0014-install-decoupling) — the install decoupling delivered alongside the proof
- [ADR 0001](0001-crickets-purpose) — the original crickets/agentm split that #36 + this ADR continue to shape
