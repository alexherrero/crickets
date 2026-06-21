---
title: Wiki Section Taxonomy Design
status: launched
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-10
updated: 2026-06-11
last_major_revision: 2026-06-11
prd:
project: https://github.com/users/alexherrero/projects/5
kind: design
scope: feature
area: crickets/wiki
governs:
  - src/wiki-maintenance/scripts/check-wiki.py
parent: wiki-maintenance-design.md
---

<!--
  Authored 2026-06-10 via /design author from the settled taxonomy
  discussion. Lightweight shape: Context · Design · Alternatives · Risks
  (the N/A-for-this-change sections — Dependencies, Migrations, Quality
  Attributes, Project management, Operations — are omitted; their one
  load-bearing point each is folded into Design or Risks).
  status: draft → review → final → launched.
-->

# Wiki Section Taxonomy Design

## Context

### Objective

The wiki generator's section taxonomy is a four-section Diátaxis skeleton (`get-started · do · reference · why`) that doesn't match how the operator navigates a project and has no home for a project's structural component map. This design replaces it with a seven-section taxonomy — How-to · Reference · Architecture · Designs · Explanation · Decisions · Operational — where Architecture is a per-project, dynamically-populated component map and Operational is suppressed on public wikis. It threads that taxonomy through the three coupled surfaces it lives in, and validates the result by restructuring crickets' own wiki to it and rewriting agentm's wiki from scratch against it.

### Background

The generator (`wiki_init.py`) hard-codes `DEFAULT_SECTIONS = ["get-started", "do", "reference", "why"]` plus standalone `designs`, `decisions`, and `plugins` folders, and crickets' hand-built wiki is its canonical no-op reference — if `SECTION_META` drifts from that wiki, a `wiki-init` run on crickets stops being idempotent. So the taxonomy lives in three coupled surfaces that must move together: the rendered sidebars (root + per-folder `_Sidebar.md`), the generator's `SECTION_META`/`DEFAULT_SECTIONS`, and the authoring spec (`diataxis-author/templates/README.md` §3).

Two gaps drove the redesign. There was nowhere for a project's **structural component map** — the "how is this built" view between Reference's lookup tables and the per-feature designs; the old `plugins` folder was a flat list that fit only crickets. And the four-section skeleton split task content across `Do`/`Get-Started`, a division the operator never wanted. The shaping constraint: **Architecture is unique per project** — crickets' components (plugins, customization model, build & distribution, host adapters, harness interface) share almost nothing with agentm's (phases, AgentMemory, auto-detect, device-wide substrate). A static `SECTION_META` can't encode that, so the *frame* stays static while Architecture's *contents* move into a per-repo manifest.

## Design

### Overview

The taxonomy has two halves that change independently. The **frame** is a fixed, ordered set of seven top-level sections — How-to, Reference, Architecture, Designs, Explanation, Decisions, Operational — shared by every project. Two are **conditional**: Architecture appears only when the project declares one; Operational only when the wiki isn't public. The other five are always present.

The **Architecture contents** are per-project. Rather than hard-code sub-sections, the generator reads a small per-repo manifest (`wiki/architecture.yml`) listing each large component as `{slug, title, summary, overview-page}`, scaffolds an `architecture/<slug>/` folder per entry, and renders a nested, grouped Architecture block in the sidebar — the one genuinely new render mechanic, a third nesting level on top of the per-folder-sidebar model ([ADR 0018](wiki-maintenance-design)). A few components recur across the operator's sibling repos (host-adapters, the sibling-interface, distribution); those ship as **optional pillar toggles** so a project gets them with one keyword, while everything else is free-form.

Two renames close an earlier Diátaxis experiment: `do→How-to` (reversing `do→Do`) and `why→Explanation` (reversing `why→Why-It-Works`), with Get-Started/Tutorials folding into How-to. Architecture is understanding-oriented and sits *before* Designs: each Architecture page links *down* to its design, and the per-feature designs also list in their own Designs section after Architecture. Reference keeps the lookup tables (Manifest-Schema, Per-Host-Paths, Compatibility); Architecture pages link *out* to that detail rather than duplicating it.

### Detailed Design

No new infrastructure — this is a generator + content change, run by the existing `wiki-init` command. The work lands across the three coupled surfaces:

| Surface | File(s) | Change |
|---|---|---|
| Generator source | `src/wiki-maintenance/scripts/wiki_init.py` | `SECTION_META`/`DEFAULT_SECTIONS` reshaped to the 7-section frame; conditional tagging; manifest reader + nested render |
| Rendered sidebars | root `wiki/_Sidebar.md` + per-folder `<section>/_Sidebar.md` | reordered + renamed; Architecture gains the nested sub-section render |
| Authoring spec | `diataxis-author/templates/README.md` §3 | the intent-folder list + Architecture nesting + conditional-section rules |

#### 1. The static frame

```python
DEFAULT_SECTIONS = ["how-to", "reference", "architecture", "designs",
                    "explanation", "decisions", "operational"]
```

`SECTION_META` maps each slug to `(basename, title, one-liner)`; the renames land here (`how-to`, `explanation`). `architecture` and `operational` are tagged conditional (a `CONDITIONAL_SECTIONS` set) so the renderer can suppress them. Basenames keep mirroring crickets' own wiki so a `wiki-init` run on crickets stays a near-no-op — which is why the crickets dogfood must move `do/→how-to/`, `why/→explanation/`, and absorb `plugins/` into `architecture/plugins/`. `check-wiki.py` updates in the same arc so the new intent-folder set passes lint.

#### 2. The per-project Architecture manifest (net-new)

`wiki_init.py` reads no per-repo config today (CLI-flag-driven), so `wiki/architecture.yml` is a new file the generator learns to read:

```yaml
architecture:
  pillars: [host-adapters, sibling-interface]   # recurring toggles, optional
  components:
    - slug: plugins
      title: Plugins
      summary: One folder per plugin; the generated dist surface.
      overview: Plugins              # the section's anchor page
    - slug: customization-model
      title: Customization model
      summary: How a customization is declared, validated, installed.
      overview: Customization-Model
```

The generator expands each `pillars:` toggle to its known template, scaffolds `architecture/<slug>/` + a section landing per `components:` entry, and feeds the ordered list to the sidebar renderer. An absent/empty manifest suppresses Architecture entirely (conditional gate #1). The block is validated (required keys; known pillar names) and fails closed with a clear error.

#### 3. The nested sub-section render (third nesting level)

The sidebar model ([ADR 0018](wiki-maintenance-design)) is two levels today (root lists sections; each folder lists its pages). Architecture adds a third — the root Architecture entry expands into its components:

```
### 🏛️ [Architecture](Architecture)
- [Plugins](Plugins)
- [Customization model](Customization-Model)
- [Build & distribution](Build-And-Distribution)
- [Host adapters](Host-Adapters)
- [Harness interface ↔ Agent M](Harness-Interface)
```

Per-component folders still get their own `_Sidebar.md` for pages *within* a component (GitHub Wiki renders the nearest sidebar). This is the only new render mechanic.

#### 4. The visibility gate for Operational

`wiki-init` already takes `--visibility {public|private|internal|unknown}`. Operational renders only when `visibility != public` — both `private` and `internal` are non-public (the distinction is *audience*, not content-sensitivity; both get Operational); `public` and `unknown` suppress it. crickets and agentm are public → suppressed for both, but the slot exists for the operator's private wikis.

#### 5. The lockstep validation (the two dogfoods)

The crickets wiki is the canonical reference: after the change, crickets' hand-built `wiki/` must match what `SECTION_META` + crickets' `architecture.yml` render, or the no-op invariant breaks. So restructuring crickets in place (`do/→how-to/`, `why/→explanation/`, `plugins/→architecture/plugins/`, + four new pillars) is the *lock* that proves surfaces 1 and 2 agree, not just validation. agentm gets a full rewrite — its Tutorials/How-to/Explanation tree replaced wholesale by the frame + agentm's own manifest. The static frame, manifest expansion, conditional gates, and nested render are pure functions over fixtures (no-manifest · single-component · recurring-pillars · public-vs-private), unit-tested in the battery; the crickets no-op is the e2e check.

The Detailed Design's five subsections map onto the translate split: **frame · manifest · render+gate · crickets-dogfood · agentm-dogfood · docs/ADR** — likely 4–6 parts.

## Alternatives Considered

- **Hard-code Architecture sub-sections in `SECTION_META`** (like the old `plugins` folder). Rejected — every project's architecture differs; a static list fits crickets and nothing else. The manifest is the only way to make Architecture per-project without forking the generator per repo.
- **A flat Architecture section** (one page, no sub-folders). Rejected — the operator wanted real sub-sections, each a component with its own pages (e.g. "the interface with Agent M"); a flat list can't carry per-component depth.
- **Fold Designs into Architecture.** Rejected — Architecture is the understanding-oriented component map; Designs are per-feature design docs. Different Diátaxis modes; each Architecture page links *down* to its design and designs also list separately. Co-documenting blurs the map/feature line.
- **Gate Operational on a content-sensitivity flag** instead of visibility. Rejected — the real axis is audience (public vs not), and `--visibility` already encodes it; a separate flag is a second source of truth to keep in sync.

## Technical Debt & Risks

1. **The no-op invariant is load-bearing and fragile.** If crickets' hand-built wiki and `SECTION_META` disagree after the change, `wiki-init` on crickets stops being idempotent and the canonical reference rots. *Mitigation: the crickets dogfood IS the lock — restructure crickets, then prove `wiki-init` is a no-op against it in the battery. Re-audit on any future `SECTION_META` edit.*
2. **The manifest is a new schema to maintain + validate.** A malformed `architecture.yml` could scaffold garbage or crash the generator. *Mitigation: validate the block (required keys per component; known pillar names); fail closed. Re-audit if a third repo's manifest exposes a missing field.*
3. **Three coupled surfaces can still drift** between releases even with the dogfood lock — a future edit to one without the others reintroduces drift. *Mitigation: a battery check that the rendered crickets sidebar matches the generator output. Re-audit if the check is ever skipped.*

## Document History

| Date | Change | Status |
|---|---|---|
| 2026-06-10 | Authored via `/design author` from the settled taxonomy discussion (7-section frame · per-project Architecture manifest · nested render · visibility gate · two dogfoods). Lightweight shape — N/A-for-this-change sections omitted, their load-bearing points folded into Design/Risks. Operator approved the lighter draft; **draft → review → final** in one pass. Translated to **6 parts** via `/design translate` (split verbatim from the design's DD mapping): `static-frame` · `architecture-manifest` · `render-and-gate` · `crickets-dogfood` · `agentm-dogfood` · `docs-adr`. | final |
| 2026-06-10 | Sequenced into 6 `PLAN.md` via `/design sequence` (topo order static-frame → architecture-manifest → render-and-gate → crickets-dogfood → agentm-dogfood → docs-adr). `static-frame` activated as the vault `_harness/PLAN.md`; the other 5 queued to `_harness/designs/wiki-section-taxonomy/queued-plans/`. Ready for `/work`. | final |
| 2026-06-11 | **final → launched.** All 6 parts shipped + their PLAN.md archived: `static-frame` (DEFAULT_SECTIONS/_FOLDER_MODE reshaped to the seven sections), `architecture-manifest` (`wiki/architecture.yml` reader + PILLAR_TEMPLATES + fail-closed parse), `render-and-gate` (nested third-level Architecture sidebar + the has_architecture/renders_operational gates), `crickets-dogfood` (crickets' own wiki restructured to the frame), `agentm-dogfood` (agentm's wiki rewritten against it), `docs-adr` (README §3 authoring spec · the Declare-Architecture how-to · the wiki-design weave-in · **ADR 0020**). The seven-section frame, the per-project Architecture manifest, and the two conditional gates are the shipped taxonomy; ADR 0020 records the calls. No further queued plans — the design is closed. | launched |

## Amendment log

*Folded decision history (AG Phase-2 C4 — record retired into this design; git holds the full ADR text).*

**2026-06-21 (C4 fold) — ADR 0020 retired into this design (AG Phase 2).** The agentm/crickets ADR model was retired (AG design-doc §5); ADR 0020 (the seven-section wiki taxonomy) folded here and deleted via `migrate-adr.py` (inbound links repointed, index/sidebars pruned). Stamped `area: crickets/wiki` (child of [wiki-maintenance-design](wiki-maintenance-design)), `governs: src/wiki-maintenance/scripts/check-wiki.py` (the gate that enforces this taxonomy). *Why not keep it as an ADR:* the append-only model forces a chain-read; the living body is the single source.

**2026-06-11 — seven-section wiki taxonomy: fixed frame + per-project Architecture manifest + conditional gates (was ADR 0020).** A **fixed seven-section frame in fixed order** — How-to · Reference · Architecture · Designs · Explanation · Decisions · Operational — scaffolded by `wiki_init.py`'s `DEFAULT_SECTIONS` and allow-listed by `check-wiki`'s `_FOLDER_MODE`; it **supersedes (in spirit) the intent-folder IA** of the per-folder-sidebar decision (see [wiki-maintenance-design](wiki-maintenance-design)), keeping that design's nearest-`_Sidebar.md` + two-level reachability. **Architecture** comes from a per-project `wiki/architecture.yml` manifest (`components:` of `{slug,title,summary,overview}` + optional `pillars:` toggles), read by the generator for order/landings/nested sidebar. **Two conditional sections:** Architecture renders on declaration; Operational renders on **audience (visibility)**, not per-page sensitivity (public wikis suppress it). *Why not per-repo improvised folders / Diátaxis-type-only / hard-coded architecture / always-present sections / sensitivity-gated Operational:* improvisation drifts with no source of truth; Diátaxis modes don't cover Architecture/Designs/Decisions/Operational; a hard-coded architecture list is wrong for every repo but one; stub sections are noise; sensitivity is the per-page PII gate's job, not the section frame's. *Re-audit trigger:* a recurring doc type with no home (add a section) or a universally-empty section (drop it); the `{slug,title,summary,overview}` shape proving too thin/thick.
