---
title: "Dogfood finale: learn-the-voice on real agentm wiki pages"
status: draft
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-04
updated: 2026-06-04
last_major_revision: 2026-06-04
prd:
project: https://github.com/users/alexherrero/projects/5
parent_design: ../../wiki-maintenance-design.md
part_slug: dogfood-finale
dependencies: [style-learning-loop, wiki-watcher]
estimated_scope: L
---

# Dogfood finale: learn-the-voice on real agentm wiki pages

## Scope

The operator-paced finale that is simultaneously the plugin's **validation** and its **training corpus**.

- **Run the learning loop against a batch of real agentm wiki pages.** The skill rewrites a page → the operator critiques/edits → the skill studies the delta and learns → rewrites until the operator is satisfied → persists the confirmed voice lessons → moves to the next page. Over the batch the output converges on the operator's expectations.
- **Validation + corpus in one.** The phase answers "does it produce pages the operator accepts?" (validation) while the operator's edits are exactly what tune the templates + style overlay (training corpus).
- **Promotion.** Proven overlay lessons are promoted into the shipped repo base style-guide via the **operator-gated** `promote` path (a maintainer source-edit + commit + regenerate), so future installs start closer to the mark.
- **Gates the slim.** The V5 ⑤ slim (deleting the parallel-run agentm copies from `scaffold-fold-in`) is **gated on this proving out** — rollback is simply "don't delete; parallel-run holds."

## Dependencies

- **`style-learning-loop`** — the learning loop, the style overlay, and the scope-capture path must exist to dogfood them (the load-bearing prerequisite).
- **`wiki-watcher`** — this is the **finale**: it validates the *complete* plugin (authoring · capture · documenter wiring · watcher) and gates the V5 ⑤ slim, so it sequences after the full build. The dependency on `wiki-watcher` (which transitively pulls in `scaffold-fold-in` + `documenter-wiring`) forces dogfood-finale topologically last.

## Verification criteria

- The learning loop runs end-to-end on a batch of real agentm wiki pages and produces operator-accepted output.
- Confirmed voice lessons are persisted to the overlay at the operator-selected scope (global / per-project / per-repo).
- At least one proven lesson is promoted into the repo base via the operator-gated `promote` path + regenerate.
- Rewritten pages pass `check-wiki.py --strict`.
- The V5 ⑤ slim is unblocked **only after** dogfood proof; until then the agentm copies remain (parallel-run holds, rollback = don't delete).

## Parent design

This part implements one slice of [Wiki-Maintenance — an opinionated, template-driven wiki maintainer](../../wiki-maintenance.md) (`Status: final`). See the parent for Context, Alternatives Considered, Quality Attributes overview, and Operations strategy. Mid-execution changes to this part's scope must be appended to the parent's Document History.
