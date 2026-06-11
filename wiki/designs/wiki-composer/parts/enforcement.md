---
title: "check-wiki section-structure enforcement"
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
part_slug: enforcement
dependencies: [section-schema, author-wiring]
estimated_scope: M
---

# check-wiki section-structure enforcement

## Scope

The composer makes assembly correct at author time; enforcement keeps authored pages from drifting from the library afterward (README §6 item 2). `check-wiki.py` gains section-structure checks for manifest-backed page types:

- **Section presence + order** — a page's H2 sections match its manifest's order, with no unknown sections. (The taxonomy already locks Architecture's *component* order; this locks a page's *section* order.)
- **Heading-variant conformance** — a section with `heading-variants` renders one of its declared headings, not an invented one.
- **Unfilled-placeholder finding** — a surviving `<…>` is a soft finding (scaffolded but not filled); `--strict` promotes it to a failure. Same findings-not-failures model as the `convention-drift` banned-terms check.

Enforcement is what makes the output contract trustworthy over time: assembly is correct when authored, the check keeps it correct after hand-edits.

## Dependencies

Depends on `section-schema` — it reads `heading-variants` + the placeholder convention to check against — and on `author-wiring`, which produces the real composed pages (the `component-overview` proof slice) the checks validate against. Sequences last.

## Verification criteria

- A manifest-backed page whose H2 sections deviate from manifest order, or add an unknown section, is flagged.
- A section with `heading-variants` rendering an out-of-list heading is flagged; an in-list heading passes.
- A surviving `<…>` placeholder is a soft finding; `--strict` promotes it to a failure (mirrors `convention-drift`).
- The checks run in the gate battery + CI; the `component-overview` proof slice passes clean.
- Battery green.

## Parent design

This part implements DD §4 of [Wiki Composer Design](../../wiki-composer.md) (`Status: final`). See the parent for the Testability proof-slice acceptance test and the Data Integrity round-trip strip invariant. Mid-execution scope changes append to the parent's Document History.
