---
title: "The wiki-init action — scaffold the IA, sidebars, and landings"
status: draft
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-10
updated: 2026-06-10
last_major_revision: 2026-06-10
prd:
project: https://github.com/users/alexherrero/projects/5
parent_design: ../../wiki-maintenance-provisioning.md
part_slug: wiki-init
dependencies: [wiki-sync-template]
estimated_scope: M-L
---

# The wiki-init action — scaffold the IA, sidebars, and landings

## Scope

Build `wiki-init` — a plugin command (an agent action, since plugins have no target-repo install hook) that provisions a target repo's wiki. It scaffolds the [intent-folder IA](wiki-maintenance-design) (a sensible default subset — `get-started/ how-to/ reference/ explanation/`, extensible via `--sections`), each folder with a `_Sidebar.md` and a section-index landing built from the template library; drops the `wiki-sync.yml` from `wiki-sync-template` into `.github/workflows/`; and wires the bundled gate into the target's CI.

It is **idempotent + preview-first**: it detects an existing `wiki/` and fills only what's missing — never overwrites an operator-authored page; `--preview` writes nothing and prints the plan. Before it writes the workflow it runs the **non-public cost warning**: check the target's visibility, and if the repo isn't public, warn that GitHub Actions minutes are billed for private repos (the publish + lint workflows consume them) — public repos run free, so the warning fires only when relevant, and the operator confirms before the workflow lands.

Covers Detailed Design §2.

## Dependencies

- **`wiki-sync-template`** — `wiki-init` drops the workflow template that part ships and wires the gate that part single-sources; it can't provision the publish/lint half until that exists.

## Verification criteria

- On an empty repo, `wiki-init` scaffolds the section folders + per-folder `_Sidebar.md` + section-index landings, and drops `[W] Update Wiki` into `.github/workflows/`.
- On a repo that already has a `wiki/`, it fills only the gaps (a missing sidebar, an absent landing) and never edits an existing page's body; a second run is a no-op.
- `--preview` writes nothing and prints the plan; `--sections` selects the folder set.
- A non-public target triggers the billed-Actions warning before the workflow is written; a public target does not.
- The scaffold/plan logic is unit-tested against fixtures (empty · partial · full wiki); the full gate battery is green.

## Parent design

This part implements one slice of [Wiki-Maintenance Provisioning Design](wiki-maintenance-provisioning) (`Status: final`). See the parent for Context, Alternatives Considered (agent-command vs install-hook · idempotent gap-fill), Quality Attributes (Reliability, Data Integrity), and Operations. Mid-execution scope changes append to the parent's Document History.
