---
title: "Dogfood: full rewrite of agentm's wiki"
status: draft
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-10
updated: 2026-06-10
last_major_revision: 2026-06-10
prd:
project: https://github.com/users/alexherrero/projects/5
parent_design: ../../wiki-section-taxonomy.md
part_slug: agentm-dogfood
dependencies: [crickets-dogfood]
estimated_scope: L
---

# Dogfood: full rewrite of agentm's wiki

## Scope

Full rewrite of agentm's `wiki/` against the new frame — agentm needs the rewrite anyway, and it's the proof the mechanic generalizes beyond crickets:

- Replace the current Tutorials/How-to/Explanation tree wholesale.
- Author agentm's `wiki/architecture.yml` with its six pillars: **phases · agentmemory · auto-detect-orchestrate · device-wide-substrate · host-adapters** (recurring) **· toolkit-interface** (↔ crickets, recurring).
- Rebuild How-to / Reference / Explanation / Decisions content to the frame; run `wiki-init` to scaffold the Architecture skeleton, then fill each component's overview page.
- Operational suppressed (agentm is public).

## Dependencies

- **crickets-dogfood** — prove the mechanic on the canonical reference (and lock the generator's no-op) before rewriting a second repo against it.

## Verification criteria

- agentm's `wiki/` renders the 7-section frame with its six Architecture pillars.
- The old Tutorials/How-to/Explanation tree is gone.
- Each Architecture pillar has an overview page that links *down* to its design where one exists.
- `check-wiki.py` green on agentm's tree.

## Parent design

This part implements the second half of DD §5 of [Wiki Section Taxonomy Design](../../wiki-section-taxonomy.md) (`Status: final`) — the generalization proof. See the parent's Risk #4 (the rewrite is large; the manifest gives it a skeleton). Mid-execution scope changes append to the parent's Document History.
