---
title: research — design
status: launched
kind: design
scope: feature
area: crickets/research
governs: [src/research/]
parent: crickets-hld.md
seeded: 2026-06-20
approved: 2026-06-23
---

> [!NOTE]
> **LAUNCHED (lifted 2026-06-24, AG Phase 3; originally approved 2026-06-23).** child-design — **the `research` capability** (deep research + web fetch + synthesis), parent [crickets HLD](crickets-hld.md). `status: launched` (lifted into tracked `wiki/designs/` 2026-06-24, AG Phase 3). Points *up* at the [crickets HLD](crickets-hld.md).

# research

## Objective

`research` is the capability that **brings in what the agent hasn't seen** — codebase fan-out, bounded web lookups, and (later) scheduled outward learning, synthesized into something the work can use. It is the Researcher persona's composition, and the Architect and Designer personas compose it too. The on-demand half is two read-only agents; the deeper multi-source work is **forward-referenced** to an operator-personal agent, by name and contract. This design defines the capability and its on-demand first slice, and names the scheduled half that waits on agentm.

## Overview

Research runs in two modes:

- **On-demand** — answer a question now: `explorer` *(delivered)*, `researcher` *(delivered)*, and a new `idea-search` *(greenfield)* — find what's already in the vault before reaching outward.
- **Scheduled forward-learning** *(designed)* — reach approved sources on a cadence, bring back what's worth knowing, surface it; leans on agentm's scheduler + approved-source pipeline.

The **posture** is settled as **public**: `research` is a public capability — a deliberate reversal of the earlier "deep research is operator-personal, out of scope" intent. Deep multi-source work still stays **forward-referenced to an operator-personal agent, by name and contract**; the capability itself is public.

```mermaid
graph TD
    R["<b>research</b>"]
    R --> OD["on-demand<br/><i>explorer · researcher · idea-search</i>"]
    R --> SC["scheduled forward-learning<br/><i>learn-forward · codebase-improvement</i>"]
    OD -. "researcher forward-refs" .-> DR["operator-personal<br/>deep-research agent"]
    SC -. "lean by name" .-> SUB["agentm forward-experience<br/><i>scheduler + approved sources</i>"]
    OD -. "enhances" .-> PLAN["/plan"]
    classDef designed fill:#f4f4f6,stroke:#b0b0b8,color:#8a8a92;
    class SC,SUB designed;
```

*Two modes — on-demand (ships) and scheduled forward-learning (designed, leaning by name on agentm's unbuilt substrate); deep multi-source work is forward-referenced to an operator-personal agent; the on-demand half enhances `/plan`.*

## Design

### `explorer` — single-question codebase fan-out *(delivered)*

- *Entry:* dispatched with one specific question about the codebase (tools: Read/Glob/Grep).
- *Exit:* a structured short answer with `file:line` references + caveats.
- *Automated:* file-level search answering the one question; dispatched in parallel only for *independent* questions, never to split a single one.
- *Artifacts:* none — read-only.

### `researcher` — codebase + bounded web *(delivered)*

- *Entry:* dispatched with a research question (tools: Read/Glob/Grep/WebFetch).
- *Exit:* structured findings with references + caveats.
- *Automated:* dispatches `explorer` for in-repo fan-out and runs its own `WebFetch` for a few targeted lookups; **forward-references an operator-personal deep-research agent by name** when one is installed, degrading to `explorer` + `WebFetch` otherwise. The bounded-web boundary is deliberate — unbounded crawling is the named anti-pattern.
- *Artifacts:* none — read-only.

### `idea-search` — find what's known first *(greenfield)*

- *Entry:* `idea-search <question>` — invoked before reaching outward, to surface ideas already captured in the vault + codebase that bear on the question.
- *Exit:* a ranked set of existing relevant entries, so research starts from what's known.
- *Automated:* a read-only scan over the recall engine.
- *Artifacts:* none — reads memory, writes nothing.

**`[PENDING-IMPL]`** — build `idea-search` over the recall engine (documenter); it does not exist today.

### Scheduled forward-learning — `learn-forward` + `codebase-improvement` *(designed)*

- *Entry:* a scheduled trigger (the agentm scheduler).
- *Exit:* surfaced findings — `learn-forward`: ideas mined from approved sources; `codebase-improvement`: stale-pattern findings in the operator's own repos — **surfaced, never adopted silently**.
- *Automated:* `learn-forward` routes to approved sources on a cadence; `codebase-improvement` applies research insights to detect stale patterns.
- *Artifacts:* findings land in the **idea incubator / watchlist** for operator review, via the memory engine.

Both lean **by name** on agentm's **forward-experience substrate** — the scheduler + approved-source pipeline — which are designed-not-built (the [Experience design](https://github.com/alexherrero/agentm/wiki/agentm-experience-and-dreaming)). `research` names the interface and uses it; it does not absorb the substrate (the one-way rule).

**`[PENDING-IMPL]`** — build `learn-forward` + `codebase-improvement` once the agentm scheduler + approved-source pipeline ship (documenter); the on-demand half ships first, with no dependency on unbuilt infrastructure.

### The adapt-don't-import boundary

`research` borders the skill-discovery seam (agentm's `adapt_skills.py` + `adapt-evaluator`, which surface candidates to the operator's watchlist). Research may feed the same vault discovery corpus, but the direction stays **discovery → watchlist → operator-gate** — research creates no reverse coupling; it cannot consume the watchlist to auto-adopt. The operator gate is the sole sink.

### First slice

`explorer` + `researcher` + a new `idea-search`. Defer all scheduled forward-learning until the agentm forward-experience substrate is built. This ships a real research capability without touching unbuilt infrastructure.

### Opinions it consumes

research leans on **`how-we-engineer`** — it feeds the plan → design → architecture sizing ladder, bringing in what the work needs to know before it plans. *(Hardwired today; request-by-name is Phase-3/4 — the [Opinions design](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates).)*

## Dependencies

- **enhances `development-lifecycle`'s `plan`** (soft) — research informs the brief before planning; `researcher` sits at the front of the loop. It works standalone, so it enhances rather than requires the loop (matching the composition map).
- **leans by name on the agentm forward-experience substrate** (scheduler + approved-source pipeline — designed-not-built) for the scheduled half ([Experience design](https://github.com/alexherrero/agentm/wiki/agentm-experience-and-dreaming)); it rests on the agentm substrate, one-way.
- **leans on the recall engine** for `idea-search` ([agentm Memory System](https://github.com/alexherrero/agentm/wiki/agentm-memory-system)).
- **composes with an operator-personal deep-research agent by forward-reference** when present — by name and contract.
- **borders the adapt-don't-import seam** (one-way: discovery → watchlist → operator-gate).
- Points up at the [crickets HLD](crickets-hld.md); the requires/enhances mechanics are in [crickets-composition](crickets-composition.md); the Researcher persona is in [agentm Personas](https://github.com/alexherrero/agentm/wiki/agentm-personas).

## Risks & open questions

- **No public deep-research command — by design.** The posture is public (settled), but the operator-personal deep-research agent proved non-portable as a vendored primitive, so `research` ships **no** public deep-research command; `researcher`'s forward-reference covers the deep work. Revisit only if forward-reference proves insufficient in real use.
- **The scheduled half is blocked** on the agentm scheduler + approved-source pipeline (designed-not-built) — named and deferred. It stays in this design (one capability, not a split — operator-decided).
- **`idea-search`'s relevance bar** — a vault scan that surfaces stale or tangential ideas wastes the "find what's known first" step; calibrate the recall threshold so it returns genuinely-bearing entries, not everything adjacent.
- **Re-audit triggers:** flip the `[PENDING-IMPL]` markers as `idea-search`, then the scheduled workflows, land; revisit a public deep-research command only if forward-reference proves insufficient.

## References

- **The agents:** `researcher` + `explorer` (read-only; `researcher` forward-references an operator-personal deep-research agent when present)
- **The forward-experience substrate it leans on (designed-not-built):** [agentm Experience design](https://github.com/alexherrero/agentm/wiki/agentm-experience-and-dreaming) (the scheduler + approved-source learning)
- **The recall engine `idea-search` leans on:** agentm `harness/skills/memory/scripts/recall.py` ([agentm Memory System](https://github.com/alexherrero/agentm/wiki/agentm-memory-system))
- **The adapt-don't-import seam it borders:** agentm `harness/skills/memory/scripts/adapt_skills.py` · `harness/agents/adapt-evaluator.md` (discovery → watchlist → operator-gate)
- **Siblings:** [crickets HLD](crickets-hld.md) · [composition](crickets-composition.md) · [agentm Personas](https://github.com/alexherrero/agentm/wiki/agentm-personas) (Researcher) · [agentm Experience](https://github.com/alexherrero/agentm/wiki/agentm-experience-and-dreaming)

## Amendment log

**2026-06-23 — added the two-modes diagram (diagram backfill).** Per the every-design-carries-a-diagram rule.

**2026-06-23 — added an Opinions-it-consumes clause (portfolio backfill).** Made explicit that research leans on `how-we-engineer` (it feeds the sizing ladder) — a standard Design clause adopted across the capability designs.

**2026-06-23 — authored, reviewed, and finalized.**

The `research` capability brings in what the agent hasn't seen, in two modes — **on-demand** (`explorer` + `researcher`, delivered read-only agents; a new `idea-search`, greenfield, over the recall engine) and **scheduled forward-learning** (`learn-forward` + `codebase-improvement`, designed; both lean by name on agentm's unbuilt scheduler + approved-source pipeline, surfacing findings to the idea incubator/watchlist, never auto-adopting). The adapt-don't-import seam stays one-way (discovery → watchlist → operator-gate). First slice = the two agents + `idea-search`, no dependency on unbuilt infrastructure. A public **deep-research command does not exist** — `researcher` forward-references an operator-personal deep-research agent by name and contract.

Operator decisions (2026-06-23): the posture is **public** (a deliberate reversal of the earlier operator-personal / out-of-scope intent; deep multi-source work still forward-referenced); **`research` owns `researcher`**; the scheduled + on-demand halves stay **one capability, one design** (not a split). Conformed to the per-primitive operational contract with `(delivered)` / `(greenfield)` / `(designed)` markers, and fixed a composition-lint violation (the draft both `requires` *and* `enhances` `development-lifecycle` → corrected to `enhances`, since research works standalone). **Built-vs-designed:** the two agents delivered; `idea-search` + the scheduled half greenfield/blocked on the agentm scheduler. **Re-audit triggers:** flip `[PENDING-IMPL]` as `idea-search` then the scheduled workflows land; revisit a public deep-research command only if forward-reference proves insufficient.
