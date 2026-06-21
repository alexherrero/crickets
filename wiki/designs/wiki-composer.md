---
title: Wiki Composer Design
status: launched
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-11
updated: 2026-06-11
last_major_revision: 2026-06-11
prd:
project: https://github.com/users/alexherrero/projects/5
---

<!--
  Authored via /design author (2026-06-11). The composer is item 1 of the
  diataxis-author README §6 codification roadmap; follows the launched Wiki
  Section Taxonomy design (that shipped the section library + manifests — this
  builds the transform that turns a manifest into a page). Full 10-section
  shape, not the taxonomy's lightweight draft: the composer is unshipped, so
  Dependencies / Migrations / QA / Project management / Operations each carry
  real content.

  Three load-bearing forks settled with the operator before Detailed Design:
  assembled-scaffold output · translate-downstream i18n (lang seam reserved,
  English-only first cut) · monolith verbatim fallback.
  status: draft → review → final → launched.
-->

# Wiki Composer Design

## Context

### Objective

Crickets' wiki authoring skill now describes each page type as a *manifest* — an ordered list of reusable section files — but nothing turns that list into a page. The `author` command reads a manifest verbatim, so it emits the manifest's own scaffolding comment instead of assembled prose; only the older single-file templates produce something usable. This design builds the **composer**: the step that reads a page manifest, loads each named section, strips its author-facing opinion comment, applies the house voice and the target language, and concatenates the sections in order into a publishable page. It is what makes the section system and taxonomy actually produce pages.

### Background

The seven-section taxonomy ([ADR 0020](wiki-section-taxonomy), launched 2026-06-11) reorganized the wiki and added per-component Architecture landings. That work split the page templates into a section *library*: 25 reusable section files under `templates/sections/`, each with frontmatter (`section`, `reusable`, `applies-to`), a scaffold, and a baked-in `<!-- SECTION … -->` opinion comment — plus four page-type *manifests* (`component-overview`, `home`, `plugin-home`, `section-index`) whose frontmatter `sections:` list *is* the page. The README §6 codification roadmap names the composer as item 1: the missing transform.

The composer extends an existing surface, not a greenfield one. `author.py`'s `author_page()` already resolves voice (`base ⊕ overlay` via `style_resolver.py`), injects it as an author-facing comment after the H1, and degrades to the bare template when resolution fails. But it loads `templates/<mode>.md` with `read_text()` — verbatim — which is exactly why manifests don't work yet: there is no step that expands a `sections:` list. The four Diátaxis-mode templates (`how-to`, `tutorial`, `reference`, `explanation`) are still monoliths read verbatim, so the composer has to assemble manifests without breaking the monolith path authors rely on today.

Two realities widen the scope past a simple concatenator. The section files carry opinion comments written for a *human author*, not for publication — the composer must strip them, which forces a convention for what is strippable versus what is content. And the operator has committed to multilingual wikis (≥ Spanish): language is a composition axis in its own right, not a later bolt-on — the authoring spec already records it as a deferred requirement (§5) — so the loading step needs a defined place for it even if the first cut ships English-only. Both push toward a small section schema-v2 and a defined output contract rather than a one-function patch.

## Design

### Overview

The composer is a function over a page manifest. Given a manifest — a small file whose frontmatter lists an ordered set of section names — it produces a page by running each section through the same four steps: **load** the section file from the library, **strip** its author-facing opinion comment, **resolve** the house voice (the committed style floor plus any learned overlay lessons) and the target language, then **concatenate** the results in manifest order under the page's title. Those four steps are the whole composer; everything else is the schema and the contract around them.

It does not replace the existing author command — it extends it. `author.py` already resolves voice and emits a template; the composer adds a manifest-expansion step in front of the emit and falls back to today's verbatim behavior for the four monolith templates not yet converted. That fallback is deliberate: it lets the section system and the monoliths coexist while the Diátaxis modes migrate one at a time, instead of a flag-day rewrite.

The composer *emits*: an assembled scaffold — the section bodies concatenated with author-fill placeholders. *Language* enters during a translation pass downstream of assembly, with the loader reserving a `lang` seam. The Detailed Design builds directly on both.

### Infrastructure

No new runtime. The composer is a function added to `author.py`, run by the existing `/diataxis author <page-type>` command the same way authoring runs today. It reuses `style_resolver.py` for voice and the `templates/` tree for input; the only new I/O is reading the section files a manifest names.

| Piece | Where | What it does |
|---|---|---|
| `compose_page()` | `scripts/author.py` (new) | manifest → page: load · strip · resolve · concatenate |
| section loader | `scripts/author.py` (new helper) | reads `templates/sections/<name>.md`; splits frontmatter / opinion comment / body |
| manifest reader | `scripts/author.py` (extended) | parses a page template's `sections:` frontmatter list |
| `style_resolver.resolve()` | `scripts/style_resolver.py` (reused) | `base ⊕ overlay` voice, unchanged |
| monolith fallback | `scripts/author.py` (existing path) | verbatim `read_text()` when a template has no `sections:` |

When each path runs:

| Trigger | Path |
|---|---|
| `/diataxis author <page-type>` on a manifest (`sections:` present) | compose: expand the list, assemble |
| `/diataxis author <mode>` on a monolith (how-to/tutorial/reference/explanation) | fallback: verbatim emit (today's behavior) |
| section missing / unparseable, or manifest names an unknown section | fail closed with the manifest + section name |

Two guarantees carry the rest of the design: composition is **deterministic** (same manifest + library + voice + `lang=en` → byte-identical output — what makes the proof slice an acceptance test), and **non-destructive** to the monolith path (a template without `sections:` emits exactly as today).

### Detailed Design

#### 1. The compose pipeline

`compose_page(manifest)` maps a manifest to page text through four steps, applied per section:

1. **Load.** Read `templates/sections/<name>.md` for each entry in the manifest's `sections:` list. Split it into frontmatter (`section`/`reusable`/`applies-to` + the schema-v2 fields below), the opinion comment (the `<!-- SECTION … -->` block), and the body (scaffold + placeholders). The loader takes a `lang` parameter — English today.
2. **Strip.** Drop the frontmatter and the opinion comment. Both are author-facing — frontmatter is library bookkeeping, the comment tells a human author how to use the section — and neither belongs in a published page. What remains is the body.
3. **Resolve voice.** Apply the resolved house voice (`base ⊕ overlay` from `style_resolver.resolve()`) once, emitted as the delete-me author comment after the H1, exactly as `author.py` does today. The output contract keeps the composer structural: voice guides the author filling placeholders, it doesn't rewrite their prose.
4. **Concatenate.** Join the stripped bodies in manifest order under the page H1. The result is the assembled scaffold.

The four steps are pure functions of (manifest, library, resolved-voice, lang). Determinism is the point.

**The language seam.** A section is one language-neutral file (the resolved fork: translate downstream). The loader carries a `lang` parameter, defaulted to `en` and the only value the first cut supports. When i18n is built, a translation pass runs on the assembled page (or per stripped body); `lang` is its reserved entry point, so adding Spanish never reshapes the section files. Nothing in schema-v2 is per-language — the direct consequence of choosing translate-downstream over per-language variants.

#### 2. Section schema v2

The loader depends on a section file having a predictable shape. v1 (shipped with the taxonomy) is `section` / `reusable` / `applies-to` + scaffold + one `<!-- SECTION … -->` comment. v2 adds two optional frontmatter fields and pins two conventions the existing files already follow, so the composer treats the whole library uniformly:

- **`optional: true`** — the section is conditional: the manifest's default `sections:` list omits it, and a page inserts it only when warranted. `safety` is the worked example — included only on a component with a guardrail or host-gap story. Defaults `false`.
- **`heading-variants:`** — an ordered list of allowed H2 headings for a section whose heading is concern-specific. `safety` declares `[Safety, Host gaps, Limitations]`; the author picks the fitting one, and enforcement (§4) checks the rendered heading against this list rather than a single fixed string.
- **Placeholder convention** — author-fill slots are angle-bracketed (`<name the enforcer + where it runs>`). The composer leaves them intact (output contract); a surviving `<…>` is how enforcement detects an unfilled page.
- **Strip rule** — the first HTML comment in a section file, if it opens with `SECTION `, is the opinion block; the loader strips exactly that. Everything after is body. The rule is unambiguous and still lets a body carry its own HTML comments.

Schema-v2 is additive: every v1 file is a valid v2 file (new fields default off), so the library needs no migration.

#### 3. Manifest expansion + monolith fallback

`author.py` gains the dispatch that chooses compose-vs-verbatim — a single branch on the presence of a `sections:` frontmatter list:

- `sections:` present (`component-overview`, `home`, `plugin-home`, `section-index`) → **compose**: expand the list, run the pipeline, emit the assembled scaffold.
- no `sections:` (`how-to`, `tutorial`, `reference`, `explanation`) → **fallback**: today's verbatim `read_text()` + voice-comment injection, unchanged.

This is what lets the two shapes coexist (the resolved monolith fork). `/diataxis author <page-type>` routes to the same `author_page()` entry point; only the internal branch differs, so the command surface doesn't change. A manifest naming a section absent from the library, or a section file that won't parse, fails closed with the manifest + section name — never a partial page, mirroring the taxonomy's fail-closed manifest validation.

#### 4. check-wiki enforcement

The composer makes assembly correct at author time; enforcement keeps authored pages from drifting from the library afterward (README §6 item 2). `check-wiki.py` gains section-structure checks for manifest-backed page types:

- **Section presence + order** — a page's H2 sections match its manifest's order, with no unknown sections. (The taxonomy already locks Architecture's *component* order; this locks a page's *section* order.)
- **Heading-variant conformance** — a section with `heading-variants` renders one of its declared headings, not an invented one.
- **Unfilled-placeholder finding** — a surviving `<…>` is a soft finding (scaffolded but not filled); `--strict` promotes it to a failure. Same findings-not-failures model as the `convention-drift` banned-terms check.

Enforcement is what makes the output contract trustworthy over time: assembly is correct when authored, the check keeps it correct after hand-edits.

## Alternatives Considered

- **Patch `author.py` to inline-expand `sections:` with no schema-v2 and no strip rule.** Rejected — the section files carry author-facing opinion comments that must not publish; without a defined strip rule the composer either leaks them or guesses where they end. The schema is small but load-bearing.
- **Per-language section variants** (`<name>.es.md`) for i18n. Rejected for the first cut (operator call) — N× the files to keep structurally in sync as the library grows; translate-downstream keeps one source of truth and defers the translation mechanism without foreclosing it.
- **Best-effort filled pages** instead of an assembled scaffold. Rejected (operator call) — the composer can't know component-specific content; inventing it produces plausible-but-wrong prose and breaks deterministic reproduction. Structure + voice is what it can own.
- **Convert all four monoliths now.** Rejected (operator call) — doubles the scope and turns one proof slice into four; the verbatim fallback lets the modes migrate one focused design at a time.
- **Fold the composer into the taxonomy design.** Rejected — the taxonomy shipped the library + manifests as a complete, launched unit; the transform is a distinct concern with its own forks (output contract, i18n) that earned their own design + plan.

## Dependencies

- **`style_resolver.py`** — voice resolution (`base ⊕ overlay`), reused unchanged.
- **The section library + four manifests** shipped by the taxonomy (`templates/sections/` + `component-overview`/`home`/`plugin-home`/`section-index`) — the composer's input. Assumed present (launched 2026-06-11).
- **`check-wiki.py`** — extended for the §4 enforcement checks.
- No new third-party libraries, no external services. Pure Python over the existing `templates/` tree.

## Migrations

- **Section schema v1 → v2** — additive only; every v1 file is a valid v2 file (new fields default off). Shipping the composer needs no file edits; sections adopt the new fields as they need them (`safety` already models `optional` + `heading-variants`).
- **No content migration** — the composer is net-new behavior behind the existing command; hand-authored pages are unaffected (enforcement reports drift as findings, not failures).
- **Deferred to their own designs** — converting `how-to`/`tutorial`/`reference`/`explanation` to manifests; building the translate-downstream pass for Spanish.

## Technical Debt & Risks

1. **The strip rule is a thin contract.** "First HTML comment opening with `SECTION `" is unambiguous only while every section file follows it; a section authored without the prefix would leak its comment into a page. *Mitigation: §4 enforcement can check a section file's opinion comment matches the prefix; the library is small and reviewed. Re-audit if a section ever needs a non-opinion leading comment.*
2. **The verbatim fallback is a fork that can rot.** Two emit paths (compose vs verbatim) mean a change to voice-injection or H1 handling must land in both, or the monoliths drift from manifest pages. *Mitigation: the dispatch is a single branch and both paths share `author_page()`'s tail. Re-audit when the first monolith converts (the fork narrows) and when the last does (it closes).*
3. **Determinism depends on `style_resolver` staying pure.** The proof-slice acceptance test assumes same inputs → byte-identical output; an overlay resolving non-deterministically (e.g. set-ordering) would make it flaky. *Mitigation: the proof slice pins `lang=en` + a fixed overlay set; resolver ordering is already deterministic. Re-audit if overlays gain a dynamic or remote source.*
4. **i18n is reserved, not proven.** The `lang` seam is designed but unbuilt; a translate-downstream pass might surface a constraint the schema didn't anticipate (a section whose structure differs by language). *Mitigation: ship the seam, not the mechanism. The first real Spanish page is the re-audit trigger for whether translate-downstream holds or per-language variants are needed after all.*

## Quality Attributes

### Testability

The composer is pure functions over (manifest, library, voice, lang); each step — load, strip, resolve, concatenate — is unit-testable against fixtures. The acceptance test is the **`component-overview` proof slice**: a hand-composed reference page the build reproduces byte-for-byte from the manifest + library. Determinism (pinned `lang=en` + fixed overlay) makes the reproduction exact, not approximate. The proof slice lands in the gate battery (`scripts/check-all.sh`), so a composer regression fails CI.

### Internationalization & Localization

The defining concern, drawn out rather than deferred silently. The first cut ships English-only, but the loader carries a reserved `lang` parameter and the schema keeps sections language-neutral (translate-downstream), so adding Spanish is a new pass at a defined seam — not a reshape of every section file. The trade accepted: the translated voice has no guard yet; that's deferred with the build, and the first Spanish page is its re-audit trigger.

### Reliability

Fail closed: a missing or unparseable section, or a manifest naming an unknown section, halts with the manifest + section name rather than emitting a partial page. The monolith fallback degrades gracefully — a template without `sections:` always emits — so the composer can't break existing authoring. Voice resolution already falls back to the bare template on failure (`author.py`); the composer inherits that.

### Data Integrity

The round-trip invariant: stripping a loaded section must preserve its body exactly — only the frontmatter and the single opinion comment come off. A strip rule that over-matched (eating a body comment) would corrupt content silently. The proof slice guards the whole-page round-trip; a per-section strip test guards the unit. No persistent state, so no corruption-at-rest surface.

## Project management

### Work estimates

Four natural parts, all small-to-medium:

| Part | Scope | Size |
|---|---|---|
| `compose-core` | the four-step pipeline + the `lang` seam | M |
| `section-schema` | v2 frontmatter fields + strip rule + placeholder convention | S |
| `author-wiring` | manifest dispatch + monolith fallback in `author.py` | S |
| `enforcement` | `check-wiki` section-structure checks | M |

`section-schema` and `compose-core` are coupled (the schema is the pipeline's contract) and likely sequence first.

### Documentation Plan

- **`wiki/designs/wiki-composer.md`** (this design) — the "why."
- **`diataxis-author/templates/README.md`** — flip §6 item 1 from "not built yet" to shipped; the `component-overview.md` manifest's "FOLLOW-UP (not built yet): the composer…" comment turns present-tense.
- **A how-to** under `wiki/how-to/` — composing a page from a manifest (an extension of the authoring how-to).
- **An ADR** — record the three locked calls (assembled-scaffold output · translate-downstream i18n · monolith-fallback) if they warrant a record separate from this design.
- **`wiki/reference/`** — the schema-v2 fields, if the Manifest-Schema reference page should carry them.

### Launch Plans

Ships behind the existing `/diataxis author` command — no flag, no phased rollout (local authoring tool). Live when the four parts complete and the proof slice is green in the battery. Date TBD.

## Operations

### Monitoring and Alerting

The gate battery is the monitor: the proof-slice reproduction in `scripts/check-all.sh` + CI is the alert. A composer regression surfaces as a failing check, read and acted on by the agent (LLM) during `/work` or `/release` — there's no runtime dashboard because there's no runtime service.

### Rollback Strategy

Each part is a revertible code change behind the existing command; schema-v2 is additive, so there's no migration to unwind. A `git revert` of a part restores the prior emit path (compose falls back to monolith-only). Fully reversible.

*(SLAs and Logging omitted — no service surface, no persistent state.)*

## Document History

| Date | Change | Status |
|---|---|---|
| 2026-06-11 | Authored via `/design author` (follows the launched Wiki Section Taxonomy design; composer = README §6 item 1). Three load-bearing forks resolved with the operator — **assembled-scaffold** output contract, **translate-downstream** i18n (`lang` seam reserved, English-only first cut), monoliths **kept as verbatim fallback**. Full draft filled: four-step pipeline · section schema-v2 · manifest-dispatch + fallback · check-wiki enforcement; QA kept to the four real attributes (Testability / i18n / Reliability / Data Integrity); four candidate parts sized (compose-core · section-schema · author-wiring · enforcement). Section-by-section review pass run with the operator: 10 of 12 sections approved unchanged; Objective + Overview revised to the operator's wording (Objective's closing sentence simplified; Overview's third paragraph reframed as settled, front-loading the two resolutions). **review → final** in one pass. | final |
| 2026-06-11 | Translated to 4 parts via `/design translate` (split verbatim from the Detailed Design mapping): `section-schema` (DD §2) · `compose-core` (DD §1) · `author-wiring` (DD §3) · `enforcement` (DD §4). Dependency-wired to the topo order `section-schema → compose-core → author-wiring → enforcement`; parts at `wiki/designs/wiki-composer/parts/`, registered nested in the designs sidebar. Status stays `final` — translate doesn't transition Status. | final |
| 2026-06-11 | Sequenced into 4 `PLAN.md` via `/design sequence` (topo order `section-schema → compose-core → author-wiring → enforcement`; Kahn sort, clean linear order — no tie-breaks). `section-schema` activated as the vault `_harness/PLAN.md`; the other 3 queued to `_harness/designs/wiki-composer/queued-plans/`. Plans are vault-redirected (DC-8), not repo `.harness/`. Status stays `final` — sequence doesn't transition Status; harness `/release` does `final → launched` when the last part's PLAN.md completes. Ready for `/work`. | final |
| 2026-06-11 | All four parts shipped and CI-green on `main` — `section-schema → compose-core → author-wiring → enforcement` (final part = enforcement 4/4: check-wiki rules **(m)** section-order, **(n)** heading-variant, **(o)** unfilled-placeholder). Each part's `PLAN.md` completed and archived; harness `/release` transitions **final → launched**. The composer is live on `main` (crickets installs from `main`); the version stamp follows at release. | launched |
