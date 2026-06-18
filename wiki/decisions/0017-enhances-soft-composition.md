# ADR 0017 — Soft composition (`enhances:`), the three-way developer split, and a local capability probe

> [!NOTE]
> Status: accepted
> Date: 2026-06-04

## Context

Bucket ④ extracted the operator's opinionated developer process out of `agentm` into native crickets plugins — the first build step of the V5 "unbundling" ([memory-os-architecture HLD](https://github.com/alexherrero/agentm/wiki/memory-os-architecture)). The companion child design [Developer Plugin Suite](../designs/developer-plugin-suite) (`launched`) ships the full design across six parts; this ADR locks the load-bearing decisions.

The `#40` schema modelled only **hard** dependencies (`requires:` / `standalone:` — [ADR 0013](0013-bundles-native-plugins)). But the relationships in the dev-loop are **soft**: a safety layer that should auto-engage *when present*; an adversarial reviewer that should upgrade `/review` *when installed* — each also useful entirely on its own. There was no manifest expression for "augments X when both are installed," no runtime to make it engage, and the monolithic `developer` seed conflated three separable concerns.

**Open questions the decision resolves:**

- How do plugins compose *softly* (auto-engage when present) without a hard dependency that forces all-or-nothing?
- Is the dev process one plugin or several — and where are the seams?
- How does a thin `/review` discover, deterministically (not by agent guesswork), that a deeper reviewer is available?
- Where does that discovery permanently live — in each plugin, or in the host?

## Decision

### 1. `enhances:` — soft composition declared on the enhancer

A new optional `group.yaml` field, `enhances: [{group, capability?, effect}]`, declares "when installed alongside `<group>`, I augment it (optionally its named `<capability>`)." It is **orthogonal to `requires:`/`standalone:`** — the `standalone: true ⟺ requires: []` invariant is untouched (it governs hard deps only), so a standalone plugin may carry `enhances:`. The enhancee optionally declares `capabilities:` that an `enhances` entry can target by name. `lint_src` validates the edge (target exists · no self-enhance · `enhances ∩ requires = ∅` · named capability declared); the generator carries it into the marketplace metadata; `bootstrap.sh` suggests installing a declared enhancer.

**Why not hard `requires:` between the dev plugins?** They're independently useful — `developer-safety` in any session, `code-review` on any diff. A hard dep forces all-or-nothing and denies those standalone uses.

**Why declare on the enhancer, not `enhanced_by:` on the enhancee?** Declaring on the enhancer keeps the enhancee's manifest **closed to edit** as new enhancers appear — the enhancee stays open/extensible.

**Why not agent-judgment ("the agent just sees the reviewer")?** Non-reproducible. The composition must be a deterministic, testable fact.

### 2. The three-way developer split (workflows · safety · code-review)

The monolithic `developer` seed splits into **`developer-workflows`** (the phase-gated loop — the base), **`developer-safety`** (control hooks + safety conventions, usable in any session), and **`code-review`** (adversarial review of any diff/PR). None `requires:` another; they compose via `enhances:`.

**Why split rather than one `engineering-process` mega-plugin?** `developer-safety` and `code-review` each have a real standalone use case; fusing them denies those uses. The discipline: split only where a standalone use exists — we did **not** split `explorer`/`evaluator` out of workflows (they only make sense inside the loop).

**Why is the *workflow* the base (not a conventions blob)?** The phase loop is the load-bearing thing other plugins enhance; naming it `developer-workflows` matches the operator's original "engineering-process" intent and gives `enhances:` a precise target.

### 3. Two enabling modes + capability-keyed resolution via the agentm host API

`enhances:` is declarative; enabling happens two ways. **Emergent** (safety → workflows): once installed, session-global hooks fire regardless — no detection needed. **Conditional dispatch** (the general pattern: a phase command checks for an enhancer and dispatches it iff present, else continues — graceful-skip, never a hang). The first instance is code-review → workflows' `/review`: `/review` queries the capability resolver and dispatches the adversarial pass iff the `adversarial-review` capability is available, else runs gates only. The same pattern wires the **documenter** across all six `developer-workflows` phase commands (`/setup` `/plan` `/work` `/review` `/release` `/bugfix`): each queries `find_capability.py wiki-maintenance` and dispatches the `documenter` on exit-0, graceful-skips on exit-1.

**Implementation:** `find_capability.py` is a thin bridge bundled with developer-workflows that discovers agentm's `capability_resolver.py` via best-effort path-fallback (the `find_agentm_script` pattern, first used in wiki-maintenance). When agentm is absent, it exits 1 (unavailable) — same graceful-skip contract, no hard dep on agentm (DC-2: siblings not layers).

**History:** the original implementation used `capability_probe.py` (slug-keyed, a host-CLI query). It shipped with the suite so the suite could ship unblocked, and was explicitly marked "interim — retires when agentm V5-8 lands." With agentm V5-8 shipped (`e7b9139`, 2026-06-15) and this ADR amendment (2026-06-18, crickets `ad2c2ed`), the local slug-keyed probe is **retired** and the capability-keyed resolver is the live path.

**Why generalize to the host?** Each plugin hand-rolling an install-dir probe is duplication; the capability resolver is the only component that authoritatively knows what's installed across both Claude Code and Antigravity.

## Consequences

**Positive**

- Each plugin is independently installable *and* composes into a richer whole — install one, two, or all three.
- The enhancee stays open to new enhancers without manifest edits (extensibility).
- Composition is a deterministic, unit-testable fact (lint rules + the probe), not LLM judgment.
- `enhances:` is a general catalog mechanism — the future Testing / Releasing bundles reuse it.
- The generator grew reusable capabilities along the way (`command` + `snippet` discovery, group-level `scripts/` asset-bundling).

**Negative / accepted debt**

- `enhances:` is a **crickets-only** concept — tooling-resolved, not host-resolved (neither host has native soft-composition).
- ~~The **local probe is duplicated debt** until agentm V5-8 lands.~~ **Resolved (2026-06-18):** `capability_probe.py` retired; `find_capability.py` + agentm capability resolver is the live path.
- **Parallel-run duplication**: agentm keeps its baked-in workflow/agent/hook copies until the V5 ⑤ slim — a window of two sources of truth.
- **Host limitations carried, not worked around**: Antigravity plugin hooks are observe/side-effect-only (kill-switch/steer/evidence-tracker are Claude-only-effective; commit-on-stop works on both); Claude drops `snippet` instruction files (conventions reach only Antigravity `rules/` + the operator-global config).

**Load-bearing assumptions + re-audit triggers**

- *Hosts lack native soft-composition.* **Re-audit if** a host ships an `enhances`-like primitive (mirrors ADR 0013's hard-dep trigger) — then drop the tooling-resolved layer.
- ~~*The host capability-discovery API will land (agentm V5-8).*~~ **Triggered + resolved (2026-06-18):** V5-8 shipped; `capability_probe.py` retired; all phase commands query `find_capability.py` → agentm capability resolver.
- *Antigravity hooks stay observe-only.* **Re-audit if** Antigravity ships hook-veto / reads hook stdout — then kill-switch/steer/evidence-tracker become AG-effective.
- *`capabilities:` named in an `enhances` edge stay in sync with the target's declared list.* Guarded by `lint_src` at build; **re-audit if** that cross-check is ever relaxed.

## Related

- [Developer Plugin Suite](../designs/developer-plugin-suite) (`launched`) — the child design + its six part files.
- [memory-os-architecture HLD](https://github.com/alexherrero/agentm/wiki/memory-os-architecture) (V5) — the parent; the unbundling this wave begins.
- [ADR 0013](0013-bundles-native-plugins) — bundles are native plugins generated from one SoT (the `requires:`/`standalone:` hard-dep model `enhances:` extends).
- [ADR 0016](0016-project-surface-split) — the project-surface split.
- agentm `ROADMAP-AgentMemoryV5.md` item **V5-8** — the host capability-discovery API that retires the local probe; and **⑤ V5 slim** — removing agentm's now-duplicated baked-in copies (the **dev-loop** portion is unblocked by this wave's dogfood; the docs/PM portions follow as bucket ④'s Wiki/docs + project-management plugins land).
