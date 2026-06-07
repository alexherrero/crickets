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
- **Page types:** the four Diátaxis modes (`tutorial` / `how-to` / `reference` /
  `explanation`) are today page-level monoliths; **landing types** (`home`, and later
  `plugin-home`, `project-landing`) are section-composed.

## 2. The section library (current)

| Section | Reusable | Purpose |
|---|---|---|
| `hero` | no (landing) | banner · tagline · badges |
| `intro` | yes | what it is, one plain paragraph |
| `get-started` | yes | the single first action (install) |
| `task-scenarios` | yes | user-intent table — What / Component / Example primitives |
| `lookup` | yes | user-facing reference list |
| `why-it-works` | yes | principles + research grounding |
| `major-designs` | yes | architecture first, then components |
| `decisions-index` | yes | one link to the decision index |
| `contribute` | yes | short pointer; specs live elsewhere |

Page-templates: `home.md` (the worked first instance — composes all nine).

## 3. Structural opinions (the house wiki structure)

- **Landing pages are curated, not exhaustive sitemaps.** Completeness lives in `_Sidebar`
  (the sitemap); a landing lists only what a reader acts on.
- The "do" section organizes by **user intent** — a `What / Component / Example primitives`
  table — never a flat how-to dump. Not-yet-built intents get a `coming soon` marker, never
  a dead link.
- **Long enumerations** (decisions, design sub-parts) sit behind a single **index link**,
  never inline on a landing.
- **User-facing vs contributor-facing are separated.** The landing *body* stays
  user-facing; dev/authoring specs live with the other reference material (the
  `_Sidebar` **Reference** section) + `CONTRIBUTING`, not in the landing body.
- **"Why it works" = principles + research/precedent**, ordered scope → protocol →
  principles. Not decision history (that's ADRs) and not retrospectives.
- **"Major designs"** lists architecture/substrate first (refer *out* to the substrate's own
  docs), then components in plain English.
- **`_Sidebar` is the complete sitemap**, grouped to mirror the landing's intent order:
  Get started · Do · Reference (user lookups + developer specs) · Why it works · Designs ·
  Decisions. One **Reference** section covers both lookups and contributor specs.

## 4. Voice

- Resolved as **base style-guide ⊕ overlay** (`style_resolver`): the committed floor at
  `style/base-style-guide.md`, plus on-demand learned lessons (global / per-project / per-repo).
- Governing lesson — **`user-facing-prose`** (global): plain, present-tense; cut marketing
  boasts, version-history asides, and docs meta-commentary. Describe what a thing does now.
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
2. **Enforcement** — the `check-wiki` **rule-`j` change** (curated landings are legal;
   completeness is satisfied by `_Sidebar` + index pages, not by listing everything on the
   homepage) + section-structure checks in `check-wiki` / `convention-drift`.
3. **Its own `/design` + plan** — this is net-new, beyond the wiki-maintenance finale. i18n
   (§5) is a first-class axis of that design.

## 7. Worked reference instance

The **crickets wiki** built during pass 1 is the reference: `wiki/Home.md` (the composed
landing), `wiki/_Sidebar.md` (the sitemap with the Developer reference group),
`wiki/explanation/decisions/Decisions.md` (the decision index), and the `Why-*` principle
pages. Pass 2 should reproduce these from the templates + voice + composer.
