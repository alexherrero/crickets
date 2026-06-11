---
title: "The compose pipeline"
status: draft
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-11
updated: 2026-06-11
last_major_revision: 2026-06-11
prd:
project: https://github.com/users/alexherrero/projects/5
parent_design: ../../wiki-composer.md
part_slug: compose-core
dependencies: [section-schema]
estimated_scope: M
---

# The compose pipeline

## Scope

Build `compose_page(manifest)` — the four-step transform that maps a manifest to page text, applied per section:

1. **Load.** Read `templates/sections/<name>.md` for each entry in the manifest's `sections:` list. Split it into frontmatter, the opinion comment, and the body. The loader takes a `lang` parameter — English today.
2. **Strip.** Drop the frontmatter and the opinion comment (both author-facing); what remains is the body.
3. **Resolve voice.** Apply the resolved house voice (`base ⊕ overlay` from `style_resolver.resolve()`) once, emitted as the delete-me author comment after the H1 — exactly as `author.py` does today. Voice guides the author filling placeholders; it does not rewrite prose.
4. **Concatenate.** Join the stripped bodies in manifest order under the page H1. The result is the assembled scaffold.

The four steps are pure functions of (manifest, library, resolved-voice, lang) — determinism is the point. **The language seam:** one language-neutral section file (translate-downstream); the loader carries `lang`, defaulted to `en` and the only value the first cut supports. It is the reserved entry point for the future translation pass, so adding Spanish never reshapes the section files.

## Dependencies

Depends on `section-schema`: the load + strip steps operate on the v2 frontmatter / opinion-comment / body split and the strip rule. The pipeline can't load a section until that shape is defined.

## Verification criteria

- `compose_page()` over the `component-overview` manifest + library produces the assembled scaffold deterministically: same manifest + library + voice + `lang=en` → byte-identical output.
- Each step (load / strip / resolve / concatenate) is unit-testable against fixtures and pure.
- `lang` defaults to `en` with no per-language branching in the pipeline (translate-downstream).
- Voice is emitted once as the after-H1 author comment, matching `author.py`'s current behavior.
- Battery green.

## Parent design

This part implements DD §1 of [Wiki Composer Design](../../wiki-composer.md) (`Status: final`). See the parent for the determinism risk (depends on `style_resolver` staying pure) and the i18n-reserved-not-proven risk (first Spanish page is the trigger). Mid-execution scope changes append to the parent's Document History.
