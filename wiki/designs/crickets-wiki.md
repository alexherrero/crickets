---
title: wiki — design
status: launched
kind: design
scope: feature
area: crickets/wiki
governs: [src/wiki-maintenance/]
parent: crickets-hld.md
seeded: 2026-06-20
approved: 2026-06-23
---

> [!NOTE]
> **LAUNCHED (lifted 2026-06-24, AG Phase 3; originally approved 2026-06-23).** child-design — **the `wiki` capability** (opinionated, template-driven wiki maintenance in the operator's voice). `status: launched` (lifted into tracked `wiki/designs/` 2026-06-24, AG Phase 3). Points *up* at the [crickets HLD](crickets-hld.md).

# wiki

## Objective

`wiki` **keeps the documentation tree true to what the code does, structured by Diátaxis, and written in the operator's voice** — a write-executor scoped to `wiki/`, a deterministic linter, and a template + voice-learning skill, driven at phase boundaries. It **enforces the `documentation` convention** (the Diátaxis structure, owned by [conventions](crickets-conventions.md)) and applies the operator's **voice** (an agentm opinion). It renames `wiki-maintenance` → `wiki` (bare noun) and declares `[wiki]`.

## Overview

A wiki earns trust only if it stays **true to the code, consistently structured, and in one voice** — otherwise it rots into stale, shapeless prose nobody reads. `wiki` is the system that holds those three: a deterministic structure **floor**, opinionated **authoring**, a drift **watch**, and a **voice-learning** loop — all scoped to `wiki/` and driven at phase boundaries. It enforces the **`documentation` convention** (Diátaxis, from [conventions](crickets-conventions.md)) and writes in the operator's **voice** (an agentm opinion).

```mermaid
graph TD
    CODE["the code + phase artifacts"] --> DOC
    DCONV["documentation convention<br/><i>Diátaxis · from conventions</i>"] --> DOC
    VOICE["operator's voice<br/><i>learned opinion</i>"] --> DOC
    DOC["documenter<br/><i>write-executor · scoped to wiki/**</i>"] --> LINT["check-wiki.py<br/><i>deterministic gate · Diátaxis · length · vendor</i>"]
    LINT --> TREE["wiki/** tree"]
    WATCH["wiki-watch<br/><i>drift loop</i>"] -. "re-triggers" .-> DOC
    DOC -. "operator's edits" .-> LOOP["diataxis-author + style-scope-evaluator<br/><i>voice-learning loop</i>"]
    LOOP -. "updates" .-> VOICE
    classDef floor fill:#eef4ff,stroke:#3a6ea5,color:#1e3a5f;
    class LINT floor;
```

*The `documenter` authors each page from three inputs — the code + phase artifacts, the **`documentation` convention** (Diátaxis structure, from conventions), and the operator's **voice** — then the deterministic `check-wiki.py` gate must pass before it lands in `wiki/**`. The `wiki-watch` loop re-triggers on drift; the operator's edits feed the voice-learning loop back into the voice.*

## Design

### Why a wiki

Docs that drift from the code are worse than no docs — they read as authoritative and quietly mislead. A wiki earns its keep only when three properties hold: it is **true** to what the code does, **structured** so a reader lands on the right kind of page, and written in **one voice**. `wiki` exists to make those hold *automatically*, at phase boundaries, instead of resting on a human remembering to update a page. The trajectory it serves is a navigable knowledge base that compounds.

### The structure — Diátaxis, owned by conventions

The structure standard is **Diátaxis**: every page is exactly one of four modes — **tutorials · how-to · reference · explanation** — and never blends them (the single-mode rule), under an intent-group folder layout, with length ceilings and a naming style. This is a **base standard, not a wiki-private rule** — it lives as the **`documentation` convention in [conventions](crickets-conventions.md)** (the house-standards shell, where "how we structure docs" sits alongside testing + ci). `wiki` is its **executor**: `check-wiki.py` is the gate, the templates encode it, the `diataxis-author` skill authors against it, and a per-repo `.diataxis-conventions.md` overrides it. The canonical Diátaxis definition is in conventions; wiki tools it.

### The system that keeps it true

Four parts, in the order they run:

1. **A deterministic floor.** `check-wiki.py` enforces the `documentation` convention mechanically — single-mode, length (with a soft-warning carve-out for load-bearing pages), the vendor gate — in CI (`wiki-sync.yml`). Structure is a gate, not an LLM's mood.
2. **Opinionated authoring.** The `documenter` agent — **hard-scoped to `wiki/**`** (+ `Home.md` / `_Sidebar.md` / `project.json`), never touching code — authors each page from the code, the documentation convention, and the voice, in templates, preview-before-write.
3. **A drift watch.** `wiki-watch` runs one cycle that detects doc-worthy changes and re-dispatches the `documenter`, so docs follow the code instead of waiting on a human.
4. **A voice-learning loop.** When the operator edits a page, `diataxis-author` generalizes the lesson, `style-scope-evaluator` recommends a scope (global / per-project / per-repo), and the confirmed lesson lands in a voice overlay. The voice is **learned and stored, not hardcoded** — which is how the docs sound like the operator across repos.

The floor guarantees structure; authoring + watch keep the docs true to the code; the voice loop keeps them consistent — the three properties, held without a human in the loop.

### The parts

| Primitive | Kind | What it does |
|---|---|---|
| `documenter` | agent | The write-executor — creates / updates / prunes pages; **hard-scoped to `wiki/**`** (+ the three index files); never touches code. |
| `check-wiki.py` | script | The deterministic gate — enforces the `documentation` convention (Diátaxis single-mode · length · vendor). |
| `diataxis-author` | skill | The authoring + voice-learning skill — templates, the single-mode rule, the edit-driven style-capture loop. |
| `wiki-author` · `wiki-watch` | skill | Authoring entry + the one-cycle drift watch. |
| `diataxis-evaluator` · `style-scope-evaluator` | agent | Read-only judges for the ambiguous mode-classification + voice-scope calls. |
| `wiki-composer` | script | The manifest → page transform (`compose_page`): load each `templates/sections/<name>.md`, strip its `<!-- SECTION -->` opinion comment, resolve voice, concatenate in manifest order — deterministic; leaves `<…>` author-fill placeholders intact. |
| `/wiki-init` · `/wiki-watch` · `/recent-wiki-changes` | command | **Init** (idempotent, preview-first provisioning: scaffolds the seven-section IA + per-folder sidebars + landings, drops a parameterized `wiki-sync.yml` into the target's `.github/workflows/`, wires the gate per the distribution split; warns on billed Actions minutes when the target isn't public) · the drift watch · the recent-changes digest. |
| `wiki-sync.yml` | workflow | The publish **deployment** — one workflow, two jobs: `lint-wiki` (the `check-wiki` gate, on push + PR) then `update-wiki` (`needs: lint-wiki`; `rsync -a` mirror of `wiki/` to the GitHub wiki — add/edit/rename/delete; fails loudly on case-insensitive dupe basenames; graceful-skip when the wiki is disabled; self-heals on the next green push). Publishing is deployment, lint-gated — not CI. |

### Opinions + conventions it consumes

wiki **enforces the `documentation` convention** ([conventions](crickets-conventions.md)) — the objective Diátaxis structure, one-way: wiki reads + gates it, never authors it. And it **consumes two agentm opinions**: **`good`** applied to docs (a page is good when it is true, single-mode, and findable) and the operator's **voice** (the learned prose style). The split *is* the conventions↔opinions line: the **structure** is objective + gate-backed → a convention; the **voice** is subjective + learned → an opinion. *(Hardwired / overlay today; request-by-name is the Phase-3/4 registry work — the [Opinions design](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates).)*

## Dependencies

- **requires [conventions](crickets-conventions.md)** — consumes + enforces the **`documentation` convention** (the Diátaxis structure); `check-wiki.py` is that convention's gate. wiki tools the standard; conventions owns it.
- **enhances [development-lifecycle](crickets-development-lifecycle.md)'s `documentation`** — the `documenter` runs at the loop's phase boundaries to keep docs in step with the code.
- **consumes the operator's voice + `good`** ([agentm Opinions](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates)) — the subjective prose voice (a learned overlay) + what a good doc is.
- **the Maintainer persona's drift detector (designed)** — a proactive docs-drift loop depends on the agentm **scheduler**; this capability is its write surface. See [Personas](https://github.com/alexherrero/agentm/wiki/agentm-personas).
- Points up at the [crickets HLD](crickets-hld.md); the requires/enhances mechanics are in [crickets-composition](crickets-composition.md).

## Migrations

- **The capability rename** `wiki-maintenance` → **`wiki`** (bare noun), with resolver aliasing (`[wiki-maintenance]` → `[wiki]`).
- **The `enhances` target re-points** — it enhanced `developer-workflows:documentation`; that capability is now **`development-lifecycle`**.
- The plugin directory (`src/wiki-maintenance/`) follows the rename at v6.0.

## Risks & open questions

- **All delivered** — the agents, commands, scripts, skills, and the CI workflow ship today; the rename is mechanical.
- **The `documentation` convention home is new** — the Diátaxis standard + its gate (`check-wiki.py`) ship in wiki today; landing the standard as the `documentation` domain in [conventions](crickets-conventions.md) is the structural lift (conventions owns it, wiki keeps enforcing). Until then the standard lives in wiki's skill + linter.
- **The Maintainer drift detector is designed, not built** — its proactive loop waits on the agentm scheduler.
- **Phase-5 conformance sweep** — the wiki conformance pass (analyze the tree against the foundations + the classification spine) is driven through this capability; it is scheduled work, not yet run.
- **Load-bearing GitHub-wiki rendering assumptions** — the whole IA rides on three live-verified GitHub Wiki behaviors: page links resolve **by basename only** (folders don't namespace), **case-insensitively**, and GitHub renders the **nearest** `_Sidebar.md` to the viewed page. These give the collapse/expand nav trick *and* the silent-clobber failure mode `check-wiki` guards (the case-insensitive basename-dupe check). **Re-audit if** GitHub changes wiki rendering or migrates off Gollum.
- **Re-audit triggers:** flip `wiki-maintenance` → `wiki` + re-point the `enhances` edge at v6.0; build the Maintainer drift loop when the scheduler lands; run the Phase-5 conformance sweep.

## References

- crickets `src/wiki-maintenance/` (→ `src/wiki/`) — agents (`documenter`, `diataxis-evaluator`, `style-scope-evaluator`) · commands (`/wiki-init`, `/wiki-watch`, `/recent-wiki-changes`) · scripts (`check-wiki.py`, `wiki_init.py`, `wiki_watch_*`, `vendor_gate.py`) · skills (`diataxis-author`, `wiki-author`, `wiki-watch`) · `wiki-sync.yml`; declares `[wiki]`
- **Up / enhances:** [crickets HLD](crickets-hld.md) · [composition](crickets-composition.md) · [development-lifecycle](crickets-development-lifecycle.md) · **[conventions](crickets-conventions.md) (the `documentation` convention it enforces)** · [Personas](https://github.com/alexherrero/agentm/wiki/agentm-personas) (Maintainer) · [agentm Opinions](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates) (`good` + the voice)

## Amendment log

**2026-06-24 — archived `diataxis-author.md` (AG Wave 2, landmark — vault-archived, not deleted).** The launched design that was *the canonical record of the `diataxis-author` skill's internals* is moved to `<vault>/_vault-archive/ag-design-history/diataxis-author.md` (HISTORICAL banner; git + the archive retain the full text). Its still-live shape is held here + in the [conventions](crickets-conventions.md) `documentation` domain (the Diátaxis canon); recorded for the living tree: the skill is **one skill with five sub-commands** — `author` (live authoring guidance: mode-classify + template-select + filename-style) · `check` (drift detection wrapping `check-wiki.py` + mode-mixed / stale-xref / template-drift / convention-drift signals) · `repair` (interactive, preview-first fixes, splitting mode-mixed pages via `documenter`) · `migrate` (one-shot legacy → Diátaxis, `git mv` blame-preserving, `wiki/.diataxis` marker guards re-runs; subsumed the harness `migrate-to-diataxis` predecessor) · `classify` (single-page mode + confidence, heuristic for clear cases, the read-only `diataxis-evaluator` sub-agent for ambiguous ones). The `documenter` is its **dispatched write-worker** (Diátaxis-aware, scoped to `wiki/**`); **AgentMemory convention I/O** reads operator conventions (relocated from `_always-load` to the on-demand `_global` store, via the `documenter-context` resolver) and offers operator-confirmed write-back of judgment calls (silenceable via `MEMORY_REVIEW_MODE`); a per-repo `wiki/.diataxis-conventions.md` overrides global conventions. The skill ships inside this capability's plugin (originally seeded from the agentm Diátaxis spec, ADR 0004; the post-launch pivot reframed it "enforce Diátaxis modes" → "Diátaxis as floor + operator templates/voice," adding the edit-driven voice-capture loop + `style-scope-evaluator`). *Why archive, not delete:* it is a named landmark — the most detailed surviving record of the skill's design — worth preserving for context, even though the governing truth is now this living design.

**2026-06-24 — subsumed `wiki-maintenance-design.md`, `wiki-design.md`, `wiki-composer.md`, `wiki-maintenance-provisioning.md` (AG Wave 2, move-and-retire).** Four superseded wiki designs whose still-live value lands here; all deleted (git history retains the full PRD text + part files). The three C4-folded ADRs they had absorbed (AG Phase-2) are preserved below with decision + why-not + re-audit, alongside the composer's three operator-locked design calls (contemplated as an ADR but folded into the design body, never minted). The body's parts table gains the `wiki-composer` + corrects the `wiki-sync.yml` row; Risks gains the GitHub-wiki rendering assumptions the IA rides on.

- **ADR 0008 — the `diataxis-author` skill (2026-05-22).** Shipped as one skill with five sub-commands (author / check / repair / migrate / classify), deterministic Python pipelines + one read-only `diataxis-evaluator` sub-agent (zero write scope), subsuming the migrate-to-Diátaxis predecessor; write-back split by lesson kind (voice → on-demand `<vault>/projects/_global/wiki-style/` via `style_resolver.py`, never auto-loaded; structural-naming stays in `_always-load`). *Why not author-only / two Diátaxis skills / read-only memory:* author-only misses the maintenance gap; two skills = a mental-model burden; read-only memory taxes the operator per judgment call. *Re-audit trigger:* a model bump changing how agents consume mode-separated docs, or the four-mode taxonomy being deprecated.
- **ADR 0018 — per-folder sidebars: intent-grouped wiki folders with nearest-`_Sidebar.md` nav (2026-06-08).** Intent-group folders each carry their own `_Sidebar.md`; GitHub Wiki renders the **nearest** one (live-verified) → collapse/expand nav with no platform migration; a `<!-- mode: X -->` hint preserves mode-enforcement in mixed folders; `check-wiki` rule (j) checks the **union of all sidebars** for ≤2-click reachability, not "root lists everything." (Superseded-in-spirit by the seven-section taxonomy / ADR 0020 for the *frame*, but the nearest-sidebar **mechanism** persists.) *Why not type-folders / a dynamic JS sidebar / a content heuristic:* type-folders contradict intent ordering; a JS sidebar means leaving GitHub Wiki; a content heuristic is fragile. *Re-audit trigger:* GitHub changing wiki rendering / migrating off Gollum, or wiki-sync flattening the tree.
- **ADR 0019 — wiki provisioning: gate-distribution split + supersession-gated retirement (2026-06-10).** `wiki-init` makes provisioning one idempotent, preview-first action. Two load-bearing calls: (1) **gate-distribution split** — the agent runs `check-wiki.py` *by reference* (`${CLAUDE_PLUGIN_ROOT}/scripts/check-wiki.py`, upgrades for free) while CI **vendors** a copy into the target's `.github/scripts/` (GitHub runners have no `${CLAUDE_PLUGIN_ROOT}`), re-synced via `--resync-gate`; (2) **supersession-gated retirement** — installing crickets plugins removes only the `~/.claude/` standalones an *installed* crickets plugin supersedes, matched by name **and** crickets provenance, preview-first / dry-run-default (never touches agentm-native design / memory / doctor). *Why not vendor-everywhere / reference-everywhere / blind-removal / name-only matching:* vendoring rots on the next move; a referenced CI gate can't resolve a path; blind removal would delete design/memory/doctor; name-only could remove a same-named non-provided standalone. *Re-audit trigger:* GitHub Actions exposing a runner-visible plugin path (CI could then reference, retiring the vendor half), or a host ceasing to export `${CLAUDE_PLUGIN_ROOT}`.

**The composer's three operator-locked design calls (from `wiki-composer.md`; folded here, never an ADR).** The composer is the manifest → page transform `compose_page(manifest)`: for each section it **loads** `templates/sections/<name>.md`, **strips** the author-facing frontmatter + the single `<!-- SECTION … -->` opinion comment, **resolves** voice (base ⊕ overlay via `style_resolver.resolve()`, emitted as a delete-me author comment after the H1), and **concatenates** the stripped bodies in manifest order under the page H1 — pure, deterministic (same inputs + `lang=en` → byte-identical). (1) **Scaffold, don't invent** — it emits structure + voice-guidance with angle-bracketed `<…>` author-fill placeholders left **intact**; best-effort filled pages were rejected (plausible-but-wrong prose + broken reproduction); a surviving `<…>` is how enforcement detects an unfilled page. (2) **Translate downstream** — sections are one language-neutral file; the loader carries a `lang` param defaulted to `en`; translation runs as a downstream pass on the assembled page (per-language `<name>.es.md` variants rejected — N× sync cost). (3) **Monolith verbatim-fallback** — `author.py` branches on a `sections:` frontmatter list: present → compose; absent (how-to / tutorial / reference / explanation) → today's verbatim `read_text()` + voice-comment injection, unchanged; fail-closed on a missing/unparseable section or unknown manifest name (never a partial page). Section **schema-v2** is additive over v1 (`optional:`, `heading-variants:`, the angle-bracket placeholder convention); `check-wiki` rules m/n/o enforce section presence+order, heading-variant conformance, and unfilled-placeholder (`--strict` promotes the last to a failure). *Re-audit trigger:* the first real non-English page tests whether translate-downstream holds.

**2026-06-23 — authored, reviewed, and finalized.** `wiki` keeps the documentation tree **true to the code, structured by Diátaxis, and in the operator's voice** — a `documenter` write-executor (hard-scoped to `wiki/**`), the `check-wiki.py` deterministic gate, the `diataxis-author` authoring + voice-learning skill, the `diataxis-evaluator` + `style-scope-evaluator` judges, the `/wiki-*` commands, and `wiki-sync.yml`; all delivered. The design reads **reasoning → structure → maintenance-system → parts**: why a wiki (drifted docs mislead; true · structured · one-voice), the **Diátaxis structure** (owned by the [conventions](crickets-conventions.md) `documentation` domain, enforced here), the four-part system that holds it (deterministic floor → opinionated authoring → drift watch → voice-learning loop), then the parts.

The load-bearing split (operator-ratified): the objective **structure** is the **`documentation` convention** — wiki **requires conventions** and consumes + enforces it (`check-wiki.py` is its gate), one-way; the subjective **voice** is an agentm **opinion** (a learned overlay), as is **`good`** applied to docs. **Migrations:** `wiki-maintenance` → `wiki` + the `enhances` re-point (`developer-workflows` → `development-lifecycle`) at v6.0; the `documentation` standard lands as a conventions domain. **Designed-not-built:** the Maintainer drift detector (waits on the agentm scheduler); the Phase-5 conformance sweep. **Re-audit:** land the documentation domain in conventions; flip the rename + re-point at v6.0; build the Maintainer loop; run the conformance sweep.
