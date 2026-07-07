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
> **LAUNCHED (lifted 2026-06-24, AG Phase 3; originally approved 2026-06-23) · locked 2026-06-28 (final AG design sweep).** child-design — **the `research` capability** (deep research + web fetch + synthesis), parent [crickets HLD](crickets-hld.md). `status: launched` (lifted into tracked `wiki/designs/` 2026-06-24, AG Phase 3). Points *up* at the [crickets HLD](crickets-hld.md).

# research

## Objective

`research` is the capability that **brings in what the agent hasn't seen** — codebase fan-out, bounded web lookups, and (later) scheduled outward learning, synthesized into something the work can use. It is the Researcher persona's composition, and the Architect and Designer personas compose it too. The on-demand half is two read-only agents; the deeper multi-source work is **forward-referenced** to an operator-personal agent, by name and contract. This design defines the capability and its on-demand first slice, and names the scheduled half that waits on agentm.

## Overview

Research runs in two modes:

- **On-demand** — answer a question now: `explorer` *(delivered)*, `researcher` *(delivered)*, and a new `idea-search` *(greenfield)* — find what's already in the vault before reaching outward.
- **Scheduled forward-learning** *(delivered)* — reach approved sources on a cadence, bring back what's worth knowing, surface it; leans by name on agentm's scheduler + approved-source pipeline.

![The research capability: on-demand (explorer · researcher · idea-search) enhances /plan and forward-refs the operator-personal deep-research agent; scheduled forward-learning (learn-forward · codebase-improvement) leans by name on agentm's forward-experience engine (scheduler + approved sources)](diagrams/crickets-research.svg)

*Two modes — on-demand and scheduled forward-learning both ship; scheduled forward-learning leans by name on agentm's forward-experience substrate (built 2026-07-07); deep multi-source work is forward-referenced to an operator-personal agent; the on-demand half enhances `/plan`.*

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

### `idea-search` — find what's known first *(delivered)*

- *Entry:* `idea-search <question>` — invoked before reaching outward, to surface ideas already captured in the vault + codebase that bear on the question.
- *Exit:* a ranked set of existing relevant entries, so research starts from what's known.
- *Automated:* a read-only scan over the recall engine.
- *Artifacts:* none — reads memory, writes nothing.

Delivered — `src/research/scripts/idea_search.py`, covered by `scripts/test_research_idea_search.py`.

### Scheduled forward-learning — `learn-forward` + `codebase-improvement` *(delivered)*

- *Entry:* a scheduled trigger (the agentm scheduler, via a job manifest's `command:`).
- *Exit:* surfaced findings — `learn-forward`: ideas mined from approved sources; `codebase-improvement`: stale-pattern findings in the operator's own repos — **surfaced, never adopted silently**.
- *Automated:* `learn-forward` (`src/research/scripts/learn_forward.py`) is a thin wrapper that calls agentm's real `run_forward_learning()` in-process via `agentm_bridge.py`'s `load_forward_learning_module()`; `codebase-improvement` (`src/research/scripts/codebase_improvement.py`) is self-contained — it scans a target repo for a stale pattern via plain substring match (stdlib-only, no AST) and never edits the repo.
- *Artifacts:* `learn-forward` surfaces via agentm's own forward-learning output path; `codebase-improvement` writes exactly one watchlist finding per stale pattern found, in the same entry shape `forward_learning.py` uses (`personal/_watchlist/codebase-improvement/<slug>.md`, `status: pending-review` frontmatter), so agentm's `watchlist_review.py` picks it up as part of the same merged review surface — **surfaced, never adopted silently**.

Both lean **by name** on agentm's **forward-experience substrate** — the scheduler + approved-source pipeline — built 2026-07-07 as `PLAN-wave-e-experience` task 1 on agentm (`harness/skills/memory/scripts/forward_learning.py`, config at `_meta/forward-learning-sources.json`, job registration via `templates/jobs/forward-learning.yaml` against `scripts/runner/manifest.py`). `research` names the interface and uses it; it does not absorb the substrate (the one-way rule) — `codebase_improvement.py` calls no private agentm function, only writing the shared watchlist entry shape.

Shipped as `PLAN-wave-c-research-forward-learning` (all 3 tasks: `learn-forward`, `codebase-improvement`, plugin wiring — `src/research/group.yaml` bumped 0.1.1 → 0.2.0). Covered by `scripts/test_research_learn_forward.py` (3 tests) and `scripts/test_research_codebase_improvement.py` (4 tests).

### The adapt-don't-import boundary

`research` borders the skill-discovery seam (agentm's `adapt_skills.py` + `adapt-evaluator`, which surface candidates to the operator's watchlist). Research may feed the same vault discovery corpus, but the direction stays **discovery → watchlist → operator-gate** — research creates no reverse coupling; it cannot consume the watchlist to auto-adopt. The operator gate is the sole sink.

### First slice

`explorer` + `researcher` + a new `idea-search`. Scheduled forward-learning (`learn-forward` + `codebase-improvement`) followed once the agentm forward-experience substrate shipped (`PLAN-wave-e-experience` task 1, 2026-07-07) — landed via `PLAN-wave-c-research-forward-learning`. This ships a real research capability without touching unbuilt infrastructure at each step.

### Opinions it consumes

research leans on **`how-we-engineer`** — it feeds the plan → design → architecture sizing ladder, bringing in what the work needs to know before it plans. *No shipped prose site to bind yet — the design's own stated lean, not yet realized in a runtime prompt (`src/research/` carries no skill/command markdown, only `scripts/`; PLAN-wave-d-personas task 1 grounding pass, 2026-07-07). Request-by-name is Phase-3/4 — the [Opinions design](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates).*

## Dependencies

- **enhances `development-lifecycle`'s `plan`** (soft) — research informs the brief before planning; `researcher` sits at the front of the loop. It works standalone, so it enhances rather than requires the loop (matching the composition map).
- **leans by name on the agentm forward-experience substrate** (scheduler + approved-source pipeline — built 2026-07-07, `PLAN-wave-e-experience` task 1) for the scheduled half ([Experience design](https://github.com/alexherrero/agentm/wiki/agentm-experience-and-dreaming)); it rests on the agentm substrate, one-way.
- **leans on the recall engine** for `idea-search` ([agentm Memory System](https://github.com/alexherrero/agentm/wiki/agentm-memory-system)).
- **composes with an operator-personal deep-research agent by forward-reference** when present — by name and contract.
- **borders the adapt-don't-import seam** (one-way: discovery → watchlist → operator-gate).
- Points up at the [crickets HLD](crickets-hld.md); the requires/enhances mechanics are in [crickets-composition](crickets-composition.md); the Researcher persona is in [agentm Personas](https://github.com/alexherrero/agentm/wiki/agentm-personas).

## Risks & open questions

- **Deep multi-source research is forward-referenced.** `researcher` references an operator-personal deep-research agent by name + contract when one is installed, degrading to `explorer` + bounded `WebFetch` otherwise. Revisit if the forward-reference proves insufficient in real use.
- **The scheduled half shipped** (`PLAN-wave-c-research-forward-learning`, 2026-07-07) once the agentm scheduler + approved-source pipeline landed (`PLAN-wave-e-experience` task 1, same date). It stays in this design (one capability, not a split — operator-decided).
- **`idea-search`'s relevance bar** — a vault scan that surfaces stale or tangential ideas wastes the "find what's known first" step; calibrate the recall threshold so it returns genuinely-bearing entries, not everything adjacent.
- **Re-audit triggers:** revisit the forward-reference approach only if it proves insufficient in real use; re-verify `learn-forward` / `codebase-improvement` against agentm's forward-learning shapes (`_meta/forward-learning-sources.json`, `templates/jobs/forward-learning.yaml`) if agentm changes them, since this design's own build re-confirmed those shapes had drifted from the original guess (JSON config, not YAML; a real job-manifest schema, not a mockable `Scheduler` object) before consuming them.

## References

- **The agents:** `researcher` + `explorer` (read-only; `researcher` forward-references an operator-personal deep-research agent when present)
- **The forward-experience substrate it leans on (built 2026-07-07):** [agentm Experience design](https://github.com/alexherrero/agentm/wiki/agentm-experience-and-dreaming) (the scheduler + approved-source learning — `harness/skills/memory/scripts/forward_learning.py`)
- **The recall engine `idea-search` leans on:** agentm `harness/skills/memory/scripts/recall.py` ([agentm Memory System](https://github.com/alexherrero/agentm/wiki/agentm-memory-system))
- **The adapt-don't-import seam it borders:** agentm `harness/skills/memory/scripts/adapt_skills.py` · `harness/agents/adapt-evaluator.md` (discovery → watchlist → operator-gate)
- **Siblings:** [crickets HLD](crickets-hld.md) · [composition](crickets-composition.md) · [agentm Personas](https://github.com/alexherrero/agentm/wiki/agentm-personas) (Researcher) · [agentm Experience](https://github.com/alexherrero/agentm/wiki/agentm-experience-and-dreaming)

## Amendment log

**2026-07-07 — scheduled forward-learning shipped; `research` is now fully delivered (PLAN-wave-c-research-forward-learning).** `learn-forward` (`src/research/scripts/learn_forward.py`) and `codebase-improvement` (`src/research/scripts/codebase_improvement.py`) landed, unblocking the `[PENDING-IMPL]` this design named at approval. `learn-forward` is a thin wrapper leaning **by name** on agentm's real forward-learning pipeline (`harness/skills/memory/scripts/forward_learning.py`, shipped the same day as `PLAN-wave-e-experience` task 1 — the substrate this design was waiting on); `agentm_bridge.py` (idea-search's existing bridge module) gained `load_forward_learning_module()`, the same resolver pattern `load_recall_module()` already used. `codebase-improvement` is self-contained — stdlib-only substring scan for a stale pattern, writes exactly one watchlist finding per hit in `forward_learning.py`'s own entry shape, never edits the scanned repo, calls no private agentm function. `src/research/group.yaml` bumped 0.1.1 → 0.2.0. Flipped every `(designed)` / `[PENDING-IMPL]` marker in this doc to `(delivered)` for the scheduled half, and separately corrected a stale `idea-search` `[PENDING-IMPL]` marker left over from before that primitive shipped (unrelated to this plan; `idea_search.py` + its test suite already existed). *Why worth recording precisely:* this plan's own unblock condition was re-verified against real agentm artifacts, not design prose, before the session started — and two of the three original guesses had drifted (config is JSON against `_meta/forward-learning-sources.json`, not YAML; job registration is a real schema in `templates/jobs/forward-learning.yaml` against `scripts/runner/manifest.py`, not a mockable `Scheduler` object). *Re-audit trigger:* if agentm changes either shape again, re-verify `learn_forward.py` / `agentm_bridge.py` against the new shape before trusting this doc's file references.

**2026-07-07 — corrected the `how-we-engineer` binding claim; no real prose site exists (PLAN-wave-d-personas task 1 grounding pass).** `src/research/` carries exactly two files (`scripts/agentm_bridge.py`, `scripts/idea_search.py`) — zero skill/command markdown, so there is no static-prose site for the grammar to bind. Reworded "Opinions it consumes" above from "hardwired today" (implying a real, undeclared binding waiting on request-by-name plumbing) to state plainly that no grounded binding exists yet — the same shape `PLAN.archive.20260707-opinion-consumer-grammar.md` task 4 already found for `maintenance`/`wiki`. *Why not author the missing prose here:* out of this plan's scope (the consumer grammar, not net-new opinion-standard content) — deferred to whoever next substantively touches research. *Re-audit trigger:* if a future change adds real `how-we-engineer`-shaped prose to a shipped `src/research/` file, reclassify this as a grounded binding and wire it via the markdown-prose consumer grammar ([composition](crickets-composition.md)).

**2026-06-28 — lock-down sweep (operator review).** Converted the two-modes mermaid to a house-style hand-SVG (`diagrams/crickets-research.svg`); and, per operator review, removed the public / operator-personal posture discussion from the body, Risks, re-audit, and this log (the deep-research forward-reference mechanism stays). Confirmed the two modes — on-demand (built) and scheduled forward-learning (designed, leaning by name on agentm's forward-experience substrate). Locked as a v5–v8 guidepost.

**2026-06-23 — added the two-modes diagram (diagram backfill).** Per the every-design-carries-a-diagram rule.

**2026-06-23 — added an Opinions-it-consumes clause (portfolio backfill).** Made explicit that research leans on `how-we-engineer` (it feeds the sizing ladder) — a standard Design clause adopted across the capability designs.

**2026-06-23 — authored, reviewed, and finalized.**

The `research` capability brings in what the agent hasn't seen, in two modes. **On-demand:** `explorer` + `researcher` (delivered read-only agents) and a new `idea-search` (greenfield, over the recall engine). **Scheduled forward-learning:** `learn-forward` + `codebase-improvement` (designed) — both lean by name on agentm's unbuilt scheduler + approved-source pipeline, surfacing findings to the idea incubator/watchlist, never auto-adopting. The adapt-don't-import seam stays one-way (discovery → watchlist → operator-gate). The first slice is the two agents + `idea-search`, with no dependency on unbuilt infrastructure. Deep multi-source research is **forward-referenced**: `researcher` references an operator-personal deep-research agent by name and contract.

Operator decisions (2026-06-23): **`research` owns `researcher`**; deep multi-source work is forward-referenced to an operator-personal agent (by name + contract); the scheduled + on-demand halves stay **one capability, one design** (not a split). Conformed to the per-primitive operational contract with `(delivered)` / `(greenfield)` / `(designed)` markers, and fixed a composition-lint violation (the draft both `requires` *and* `enhances` `development-lifecycle` → corrected to `enhances`, since research works standalone). **Built-vs-designed:** the two agents delivered; `idea-search` + the scheduled half greenfield/blocked on the agentm scheduler. **Re-audit triggers:** flip `[PENDING-IMPL]` as `idea-search` then the scheduled workflows land; revisit the forward-reference approach only if it proves insufficient in real use.
