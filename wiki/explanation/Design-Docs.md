<!-- mode: explanation -->
# Design Docs

## Architecture

Design Docs keeps a project's reasoning true with one living design note per area. Instead of writing a design once and letting it drift, the agent changes the note whenever a decision settles something, and records why in the note's amendment log in the same edit. The hard thinking stays findable, and the next plan starts from it. It slots on top of the phase loop: Design Docs needs Development Lifecycle installed, and `/plan` reads the notes it keeps.

### Diagram

How the plugin composes:

![How design-docs composes: it sits in the centre with a solid arrow requiring development-lifecycle, and rests one-way on the AgentM substrate of memory, opinions, and personas, with no soft enhancers](../reference/diagrams/design-docs-composition.svg)

### How it works

A project keeps one note per area in its vault, with four parts: the objective, the current design, the open questions, and an amendment log. The `/design` command writes a new note or updates an existing one, and the body and the log entry change in the same edit, so the note never says one thing while its history says another. There is no draft-to-final status and no review stage: the note is live from the first save. `/plan` finds the note that governs its task and holds the plan to the calls in it. The plugin never publishes notes to the repo's `wiki/designs/`; the pages already there stay as they are.

A decision is recorded in the note it changes. Each amendment-log entry gives the date, what changed, why the alternative lost, and the trigger for looking at it again. There is no separate decision-record file and no command for one: crickets plan 105 retired the `adr` skill and `/document-decision`, so a decision is an edit to the governing note through `/design`. The plugin also ships the `prose-pass` skill, which simplifies a finished note's wording when you ask for it.

### Composition

| Direction | Plugin | How |
|---|---|---|
| Enhances (soft) | — | None. |
| Enhanced by (soft) | — | None. |
| Requires (hard) | [Development Lifecycle](Development-Lifecycle) | `/plan` and the session-start hook, both in development-lifecycle, find the notes `/design` writes, through `vault_designs.py`. |
| Required by (hard) | — | None. |

### Why not

Design Docs is opinionated about how design authoring should flow, and it will not fit every project. Reach for something else if:

- You do not run the harness's plan-driven workflow — the notes exist for `/plan` to read, so without `development-lifecycle` they have no reader.
- Your project keeps standalone ADR files and wants a tool for them. This plugin records a decision only as an amendment to a living design note.
- The change in front of you is small and self-explanatory. A one-file fix rarely needs a design note or a decision record, and updating one for it is more ceremony than the work warrants.

## Reference

### Commands & skills

Each primitive links to the source that implements it.

| Primitive | Kind | What it does |
|---|---|---|
| [`/design`](https://github.com/alexherrero/crickets/blob/main/src/design/commands/design.md) | command | Write or update the living design note for an area: objective, current design, open questions, amendment log. |
| [`prose-pass`](https://github.com/alexherrero/crickets/blob/main/src/design/skills/prose-pass/SKILL.md) | skill | Gemini simplifies a finished doc's wording; Claude checks every fact held and applies it. |

### Configuration

No configuration — the plugin works out of the box. The `/design` command finds the notes folder through agentm and adds no config key of its own.

## See also

- [How to author a design](Author-A-Design) — the steps for writing or updating a design note with `/design`.
- [How to record an architectural decision](Record-An-Architectural-Decision) — the amendment-log workflow.
- [Development Lifecycle](Development-Lifecycle) — reads the notes this plugin keeps, through `/plan`.
- [Development lifecycle design](crickets-development-lifecycle) · [Design-docs design](crickets-design) — the deeper design.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)