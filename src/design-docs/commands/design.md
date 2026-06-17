---
name: design
description: Author → translate → sequence a design doc. Delegates to the developer-workflows /design command — install developer-workflows to use this.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
---

This command delegates to **developer-workflows** `/design` — the full implementation lives in
`src/developer-workflows/commands/design.md`.

**Requires:** `developer-workflows`. This plugin provides the `/design` surface so design-docs
users get the command without installing the full phase loop. The workflow logic (status
lifecycle, storage resolution, helper scripts) is owned by developer-workflows, not this wrapper.

## Three verbs

| Verb | Invocation | What it does |
|---|---|---|
| **author** | `/design author <slug\|brief>` (or bare `/design`) | Write a new design doc or resume/review an in-progress one. The only verb that transitions `Status`. |
| **translate** | `/design translate <slug>` | Split a `Status: final` doc into structural `parts/` files. |
| **sequence** | `/design sequence <slug>` | Topo-order `parts/` into named plans (first activated, rest queued). |

The pipeline is strictly ordered: `author` → `translate` → `sequence`. A hard `Status: final`
gate — set only by human approval inside `author` — unblocks `translate` and `sequence`.

If `developer-workflows` is not installed, this command has no implementation to delegate to.
Install `developer-workflows` first, then install `design-docs` on top.
