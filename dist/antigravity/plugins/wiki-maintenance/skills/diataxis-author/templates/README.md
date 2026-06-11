# Wiki section-template model + structural conventions — the authoring spec

> **Status: pass-1 specification (hand-authored).** This is the authoritative source
> for how this project's wikis are structured and voiced. During **pass 1** the wiki is
> hand-edited against these rules (the composer isn't built yet). After pass 1 the rules
> here are **codified** (composer + checks); **pass 2** re-authors the wiki *through* the
> codified skillset as a dogfood — checking the machine reproduces the hand-built result.
>
> The `diataxis-author` skill and the `documenter` agent both treat this file as the
> standard. When they conflict with a page, the page is wrong.

## 1. The composition model

A wiki is built from **pages**; each page is composed from **sections**.

- A **section-template** — `templates/sections/<name>.md` — is a reusable unit: frontmatter
  (`section`, `reusable`, `applies-to`) + a scaffold + a baked-in opinion comment. Authored
  once; composed into any page whose type appears in its `applies-to`.
- A **page-template** — `templates/<page-type>.md` — is a **manifest**: frontmatter
  `sections: [ordered list]`. The list *is* the page — resolve each name to
  `sections/<name>.md` and compose in order. Edit the list to author a page.
- **Page types:** **landing types** (`home`, and later `plugin-home`, `project-landing`)
  are section-composed today. The four Diátaxis modes (`tutorial` / `how-to` / `reference` /
  `explanation`) are still page-level monoliths, but their sections are now extracted into the
  library (§2), ready for the composer to assemble.

## 2. The section library

| Section | Page types | Purpose |
|---|---|---|
| `hero` | landing | banner · tagline · badges (landing-only, not reusable) |
| `intro` | landing, plugin-home, reference, section-index | what it is, one plain paragraph |
| `get-started` | landing, plugin-home | the single first action (install) |
| `task-scenarios` | landing, plugin-home | user-intent table — What / Component / Example primitives |
| `lookup` | landing | user-facing reference list |
| `why-it-works` | landing, plugin-home | principles + research grounding |
| `major-designs` | landing | architecture first, then components |
| `decisions-index` | landing | one link to the decision index |
| `contribute` | landing, plugin-home | short pointer; specs live elsewhere |
| `plugin-composition` | plugin-home | one plugin's standalone / requires / enhances + host reach |
| `how-it-works` | component-overview | the mechanism — the lead of a component landing; table for the parallel parts |
| `component-composition` | component-overview | one Architecture component's couplings to its siblings |
| `safety` | component-overview | OPTIONAL cross-cutting-concern callout (`## Safety` / `## Host gaps`) — only when a guardrail or host-gap story exists |
| `section-contents` | section-index | the section's pages as curated one-liners (not regurgitated) |
| `recent-changes` | section-index, plugin-home | tooling-maintained dated list of recent edits |
| `mode-block` | how-to, tutorial | the `> [!NOTE]` Goal / [Time] / Prereqs block |
| `steps` | how-to, tutorial | numbered, imperative steps |
| `verify` | how-to, tutorial | confirm the result (optional) |
| `notes` | how-to, reference | caveats / gotchas (optional) |
| `see-also` | all | cross-links — the universal footer |
| `what-you-learned` | tutorial | the recap |
| `next` | tutorial | where to go after |
| `quick-reference` | reference | the `## ⚡ Quick Reference` opener table; doubles as a catalog (add a Details column) |
| `host-differences` | reference | per-host asymmetry — state both hosts + the equivalent, not just "unsupported" |
| `validation` | reference | what the validator asserts (grouped by scope) + the command to run it |

Page-templates: `home.md` (landing), `plugin-home.md` (the per-plugin page — the wave-2
per-plugin-pages target — Developer-Safety is the first, in the `plugins/` section), `section-index.md` (a section's landing — one per intent-folder),
and `component-overview.md` (an Architecture component's landing — one per `architecture.yml` entry)
are section manifests. The four Diátaxis mode templates (`how-to` /
`tutorial` / `reference` / `explanation`) are still **monoliths** read live by `author.py`; their
sections now live in the library above, and the **composer** (§6) will assemble them at
codification — until then the monoliths stay.

> **Keep the library current.** When you polish a page during pass 1 and hit a generalizable
> section it doesn't yet have, pull it into `templates/sections/` and add a row here in the
> *same* pass. The library must never fall behind the pages — no batch backfills.

## 3. Structural opinions (the house wiki structure)

- **Landing pages are curated, not exhaustive sitemaps.** Completeness lives in the per-section
  sidebars (see *the sidebar is per-section* below); a landing lists only what a reader acts on.
- The "do" section organizes by **user intent** — a `What / Component / Example primitives`
  table — never a flat how-to dump. Not-yet-built intents get a `coming soon` marker, never
  a dead link.
- **Long enumerations** (decisions, design sub-parts) sit behind a single **index link**,
  never inline on a landing.
- **Link the design, not the ADR.** When a page explains *how* something works, link the
  relevant **design section** (the how-it-works explanation) — not the ADR (the decision
  record). ADRs live behind the `Decisions` index; designs explain the system.
- **User-facing vs contributor-facing are separated.** The landing *body* stays
  user-facing; dev/authoring specs live with the other reference material (the
  `_Sidebar` **Reference** section) + `CONTRIBUTING`, not in the landing body.
- **"Why it works" = principles + research/precedent**, ordered scope → protocol →
  principles. Not decision history (that's ADRs) and not retrospectives.
- **"Major designs"** lists architecture/substrate first (refer *out* to the substrate's own
  docs), then components in plain English.
- **The sidebar is per-section, not one complete sitemap.** The wiki is organized into
  **intent-group folders** matching the nav sections — `get-started/` · `do/` · `reference/` ·
  `why/` · `designs/` · `decisions/` · `plugins/`. Each folder carries its own `_Sidebar.md`; GitHub Wiki renders
  the **nearest** one, so a per-folder sidebar shows the full section list with **only the current
  section expanded**; collapsed headings link to that section's **index landing**. The **root
  sidebar (the homepage)** instead shows **all sections expanded one level** — the full map.
  Reachability is **≤2 levels** — the root shows each section's pages one level deep, a per-folder
  sidebar lists its full section; a page need not be on the root. (Needs the wiki-sync to exempt `_Sidebar.md`/`_Footer.md`
  from the basename dupe-check; `check-wiki` rule-j checks the union of all sidebars.)
- **Mode follows intent, not folder — pin it with a hint when they diverge.** Intent folders mix
  Diátaxis modes (a tutorial + a how-to in `get-started/`; how-tos filed under `reference/`). A page
  whose folder default doesn't fit carries an invisible `<!-- mode: tutorial|how-to|reference|explanation -->`
  comment that `check-wiki` reads (folder default otherwise). Folder→mode defaults: `get-started`/`do`
  → how-to, `reference` → reference, `why`/`designs`/`decisions` → explanation, `plugins` → index (a landing).
- **Page basenames are globally unique — case-insensitively.** GitHub Wiki flattens every page to its
  basename and resolves links **case-insensitively**, so `Developer-Safety` and `developer-safety`
  collide and the second silently clobbers the first. `check-wiki` rule-g enforces this. When a
  user-facing page and an internal/design page want the same name, the **user-facing page wins the
  clean name**; the design page takes a `-design` qualifier. (Pass-1: the `Developer-Safety` plugin +
  `Style-Learning-Loop` reference pages vs their design parts → `developer-safety-design` /
  `style-learning-loop-design`.)
- **Every section has an index landing — not a redirect to a sub-page.** Each intent-folder gets an
  index page (`Get-Started`, `Reference`, …) marked `<!-- mode: index -->` (a shape-exempt landing,
  not a Diátaxis mode): what the section *is* + its pages as curated one-liners (not regurgitated) +
  a **tooling-maintained Recent changes** block. The sidebar's section heading links to the index,
  never the first sub-page. (Rollout 2026-06-08; the `section-index` page-template + `section-contents`
  / `recent-changes` sections.)
- **Pick the mode by reader intent, not topic.** A page that's mostly lookup — tables, a
  catalog, troubleshooting — with thin task content is **reference**, not how-to, even if it's
  titled "How to use X." (Pass-1: the base-hooks content is lookup-heavy — trigger files + troubleshooting — so reference, not how-to; it now lives in the Developer-Safety plugin page.)
- **Infrastructure other workflows invoke is reference, not how-to.** A page about a mechanism the
  system runs *for* the operator — a voice layer, a hook, a watcher — is **reference**, even if you
  *can* drive it by hand. Lead with **what it is** + **how the infra uses it** (which workflows invoke
  it), describe the mechanism, and demote any hands-on to a **light section at the end** (for
  experimenting). A how-to is a task the operator performs; if they rarely run it, it's reference.
  (Pass-1: the style-learning-loop how-to → the `Style-Learning-Loop` reference, at the operator's call.)
- **One-line pointer over inline detail.** When content's canonical home is another page, leave
  a brief pointer (a line or a few words), not a duplicated block. (Pass-1: the hook-portability
  contract → `Hooks`; the Antigravity gaps → the `Antigravity-Limitations` register.)
- **Status column for support/capability tables.** A reference table cataloging support or
  capability carries an explicit status column — ✅ Supported / ⚠️ Partial / ❌ Unsupported —
  with the explanation in the adjacent column. (Pass-1: the Compatibility per-plugin table.)
  A **gaps/limitations register** uses a different status vocabulary — 🟡 mitigated (a workaround
  exists; the gap is contained) / ✅ resolved (the host shipped a path; strike the row) — because
  a gap with a mitigation isn't "open"; it only reopens when the host provides a path to resolve
  it. (Pass-1: the Antigravity-Limitations register — the operator's "mitigated, not open" call.)
- **Catalog a family of primitives on one reference page.** Related items (hooks, plugins,
  kinds) get a central reference page — an explainer + a `⚡ Quick Reference` table with a
  **Details** column linking per-item detail; those Details links repoint to per-item pages as
  they land. (Pass-1: the `Hooks` page.)
- **Retiring a page.** When a page's subject is retired (a removed tool, a dropped feature),
  delete the page rather than leave it stale: repoint live See-also links to the successor page,
  drop the `_Sidebar` entry, de-link historical references in ADRs/CHANGELOG (preserve the prose —
  drop only the dead link, mark *(retired in vX)*), and fold any surviving lookup surface into the
  page that owns the workflow. (Pass-1: `Installer-CLI` deleted — `install.sh` was retired in v3.0,
  its surviving `generate.py` surface folded into Modify-a-plugin.)
- **Ground a reference in the artifacts, not the old prose.** When rewriting a reference that
  catalogs concrete outputs — paths, generated files, schema values — derive every fact from the
  real artifacts (the build output, the emitter/source code), never from the page's prior prose. A
  stale reference's prose describes a dead model; the artifacts are the truth. (Pass-1:
  Per-Host-Paths rebuilt from the `dist/` tree + the `emit_*` source — the v2.x installer-dispatch
  prose was entirely obsolete, including a wrong "`command` is n/a on Antigravity" row the artifacts
  corrected.)
- **Document host asymmetries symmetrically.** For a two-host project, state what *each* host does.
  When one host lacks a feature, name its equivalent — what it does *instead* — never just
  "unsupported / n/a". (Pass-1: operator edits — a `snippet` → an Antigravity `rules/` file vs the
  convention carried in Claude's `CLAUDE.md`/`AGENTS.md`; a bundled script → `${CLAUDE_PLUGIN_ROOT}/…`
  on Claude vs a relative path on Antigravity.) The `host-differences` section bakes this in.
- **A cluster of detail pages needs an anchor.** When several reference pages each document a *part*
  of one thing, add an overview/anchor page that says what the whole *is* and points down to the
  parts; the parts link back up. Distinct from cataloging items on one page — this is an overview
  *over a cluster of pages*. (Pass-1: `Plugin-Anatomy` over `Customization-Types` / `Per-Host-Paths` /
  `Manifest-Schema`, at the operator's prompt. The wave-2 `plugin-home` page-template is its
  per-plugin instance.)
- **A cross-cutting concern is its own section, not a composition bullet.** On a component
  overview, a guardrail or where-it-falls-short story (PII defense, a destructive-action gate, a
  host capability with no authoring path) gets its OWN short section after `how-it-fits`, before
  `see-also` — `## Safety` for a guardrail, `## Host gaps` / `## Limitations` for the shortfall
  variant. Never a `how-it-fits` bullet: that section is for sibling-component couplings, and a
  concern is not a coupling. Include it only when the component carries one (most don't), and name
  the enforcer/gap + where it's tracked — the full mechanism is the Reference page's job. (Pass-1:
  Build & distribution → `## Safety` (PII guardrails → CI-Gates); Host adapters → `## Host gaps`
  (Antigravity authoring gaps → Antigravity-Limitations).) The `safety` section-template bakes this in.

## 4. Voice

- Resolved as **base style-guide ⊕ overlay** (`style_resolver`): the committed floor at
  `style/base-style-guide.md`, plus on-demand learned lessons (global / per-project / per-repo).
- Governing lesson — **`user-facing-prose`** (global): plain, present-tense; cut marketing
  boasts, version-history asides, docs meta-commentary, and **LLM-tell vocabulary**
  ("first-class" → "supported", "seamless", "robust", "leverage"). Describe what a thing does now.
- **Strip plan-internal jargon + implementation internals from user-facing pages.** Cut design-call
  codes (`DC-W4`, `DC-8`), task/part numbers (`part 4`, `task 1-4`), internal IDs (`(W1)`), and bucket
  labels; cut implementation names a reader doesn't act on — resolver/function names, internal `.py`
  filenames, test counts (`38 tests`), internal mechanics (`CycleReport`, `finalize_cycle`). State the
  behaviour, not how it's built or which task shipped it. (Pass-1: applied across the wiki-maintenance
  pages — Antigravity-Limitations · Wiki-Watch-Config · Run-The-Wiki-Watcher · Style-Learning-Loop.)
- Lesson — **`command-howto-clarity`** (global): in command/install how-tos, flag example
  lists as examples + show per-item commands; state versions as minimums; defer per-host
  detail to the reference page.
- **Cross-links name the seam, not the page.** A `How it fits` or `See also` bullet says what
  crosses between the two pages — the division of labor — not a re-description of the linked page;
  prefer a crisp two-clause contrast that splits the work. (Pass-1: the component landings' `How it
  fits` bullets — "host adapters define *where* each kind lands; build & distribution puts it there".)
- **Brand:** a tastefully *hidden* easter-egg link is welcome (e.g. the banner tagline); keep
  the Men-in-Black reference implicit — never explained inline.

## 5. Internationalization (deferred requirement)

The system **must** support multiple languages — **at least Spanish**. Language is a
**first-class composition axis**: per-language section variants, or a translation layer the
composer applies. Design for it; not built in pass 1. (See the `wiki-section-templates-i18n`
project memory.)

## 6. Codification roadmap (the build, after pass 1)

1. **Composer** — reads a page manifest, loads its sections, applies the resolved voice
   (base ⊕ overlay) + the target language, and concatenates them into the page. Wires
   `/diataxis author <page-type>` to assemble from sections instead of emitting a monolith.
2. **Enforcement** — the `check-wiki` **rule-`j` change** ✅ *landed* (commit `0ad9ca4`:
   curated landings are legal; completeness lives in `_Sidebar`). Still to do: section-structure
   checks in `check-wiki` / `convention-drift`.
3. **Its own `/design` + plan** — this is net-new, beyond the wiki-maintenance finale. i18n
   (§5) is a first-class axis of that design.

## 7. Worked reference instance

The **crickets wiki** built during pass 1 is the reference: `wiki/Home.md` (the composed
landing), `wiki/_Sidebar.md` (the sitemap with the Developer reference group),
`wiki/explanation/decisions/Decisions.md` (the decision index), and the `Why-*` principle
pages. Pass 2 should reproduce these from the templates + voice + composer.
