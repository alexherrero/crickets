<!-- mode: index -->
# Wiki Maintenance

Opinionated, template-driven wiki maintenance — it keeps a repo's `wiki/` in the **Diátaxis** shape and your **house voice**, and watches for doc-worthy changes. Standalone; it also powers `developer-workflows`' phase-boundary documentation when both are installed.

## Install

```bash
claude plugin install wiki-maintenance@crickets
```

On Antigravity, install by path (see [Install crickets plugins](Install-Into-Project)). The authoring engine + agents run on both hosts; the watcher scheduling and a couple of commands are Claude-first ([Antigravity limitations](Antigravity-Limitations)).

## What it ships

| Primitive | Kind | What it does |
|---|---|---|
| **`wiki-author`** | skill | "update the wiki" — create or update a Diátaxis page for this (or another registered) repo; dispatches the documenter with preview-before-write (Claude-only) |
| **`diataxis-author`** | skill | the Diátaxis engine — mode selection, template-fill, filename style, drift detection + repair, legacy-wiki migration; learns voice lessons from your own edits |
| **`documenter`** | agent | the structural write-executor — creates / updates / prunes `wiki/**`, preserves human edits, never touches code, enforces one mode per page |
| **`wiki-watch`** | skill + command | one idempotent watcher cycle — detect doc-worthy changes, judge significance, dispatch the documenter PR-default (`/wiki-watch`, loop/cron-friendly) |
| **`recent-wiki-changes`** | command | list recently-changed wiki pages across registered repos (Claude-only) |
| **`diataxis-evaluator`** | agent | read-only — classify a page's Diátaxis mode when it's ambiguous |
| **`style-scope-evaluator`** | agent | read-only — recommend the scope (global / per-project / per-repo) to store a confirmed voice lesson |

`check-wiki.py` is the deterministic linter behind the authoring + repair flows (mode discipline, link integrity, the section conventions).

## How it composes

- **Standalone** — maintain any repo's wiki directly; `requires: []`.
- **Enhances `developer-workflows`** — soft: the phase commands dispatch the `documenter` to author or repair pages at phase boundaries (the `enhances: documentation` declaration), so the wiki tracks the code without a separate step.
- **Hosts** — the Diátaxis engine, the documenter, and the evaluators are host-symmetric; the `wiki-author` trigger, `recent-wiki-changes`, and the watcher's scheduling are Claude-first ([Antigravity limitations](Antigravity-Limitations)).

## Why it works

A wiki rots when it's hand-maintained and voiceless. This plugin fights both: **Diátaxis single-mode discipline** (every page is exactly one of tutorial / how-to / reference / explanation) keeps the structure honest; a **house-voice overlay** plus an **operator-in-the-loop learning loop** — it captures generalizable lessons from your edits — keeps the prose yours; and the deterministic `check-wiki.py` linter plus the `documenter`'s preserve-human-edits / never-touch-code scoping keep the automation safe. See [the style-learning loop](Style-Learning-Loop) and [run the wiki-watcher](Run-The-Wiki-Watcher).

## Related

- [Run the wiki-watcher](Run-The-Wiki-Watcher) — drive one watcher cycle.
- [Style-learning loop](Style-Learning-Loop) · [Wiki Watch Config](Wiki-Watch-Config) — the voice layer + the watcher's config contract.
- [Developer Workflows](Developer-Workflows) — the base plugin this enhances at phase boundaries.
- [Plugin anatomy](Plugin-Anatomy) — what a crickets plugin is + its structure.
- [Wiki Maintenance design](wiki-maintenance-design) — why the voice layer + operator-in-the-loop learning exist.
