---
title: "Section schema v2"
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
part_slug: section-schema
dependencies: []
estimated_scope: S
---

# Section schema v2

## Scope

Pin the section-file shape the loader depends on. v1 (shipped with the taxonomy) is `section` / `reusable` / `applies-to` + scaffold + one `<!-- SECTION … -->` comment. v2 adds two optional frontmatter fields and pins two conventions the existing files already follow, so the composer treats the whole library uniformly:

- **`optional: true`** — the section is conditional: the manifest's default `sections:` list omits it; a page inserts it only when warranted (`safety` is the worked example — included only on a component with a guardrail or host-gap story). Defaults `false`.
- **`heading-variants:`** — an ordered list of allowed H2 headings for a section whose heading is concern-specific. `safety` declares `[Safety, Host gaps, Limitations]`; enforcement (`enforcement` part) checks the rendered heading against this list, not a single fixed string.
- **Placeholder convention** — author-fill slots are angle-bracketed (`<name the enforcer + where it runs>`). The composer leaves them intact; a surviving `<…>` is how enforcement detects an unfilled page.
- **Strip rule** — the first HTML comment in a section file, if it opens with `SECTION `, is the opinion block; the loader strips exactly that. Everything after is body, so a body may still carry its own HTML comments.

Schema-v2 is additive: every v1 file is a valid v2 file (new fields default off), so the library needs no migration.

## Dependencies

None — foundational. The schema is the contract the compose pipeline loads against: `compose-core`'s load + strip steps can't split a section into frontmatter / opinion-comment / body until that shape is defined, and `enforcement` can't check heading-variants or placeholders until the fields exist.

## Verification criteria

- A section with `optional: true` is parsed as conditional; absence defaults to `false`.
- `heading-variants:` parses as an ordered list; a section without it falls back to its single fixed heading.
- The strip rule isolates exactly the first `<!-- SECTION … -->` comment; an HTML comment in the body after it is preserved (round-trip invariant).
- Every existing v1 section file parses unchanged under v2 — additive, no migration.
- Battery green (unit tests over the schema parse).

## Parent design

This part implements DD §2 of [Wiki Composer Design](../../wiki-composer.md) (`Status: final`). See the parent for Context, Alternatives, and the strip-rule-thin-contract risk (re-audit if a section ever needs a non-opinion leading comment). Mid-execution scope changes append to the parent's Document History.
