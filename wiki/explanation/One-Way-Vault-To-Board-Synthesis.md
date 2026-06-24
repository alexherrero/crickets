# One-way vault-to-board synthesis

> [!NOTE]
> Implemented — catalog bundle #8 (roadmap #41). The `github-projects` plugin is built under `src/github-projects/`; the design calls below are locked and recorded in [ADR 0025](crickets-github-projects). This page is the *why*; [GitHub Projects plugin](GitHub-Projects) is the reference surface and [Sync a project board](Sync-A-Project-Board) the operator recipe.

The `github-projects` plugin answers a specific question: how does a project's state become legible to a human without making the human's view a second place that has to be kept in sync? The answer crickets settles on is **one-way deterministic synthesis** — the vault is the single source of truth, and the GitHub Project board is a *generated* mirror of it, never an editable peer. This page explains why that shape, what it buys, and the one structural property that makes it both safe and a little uncanny: the plugin that maintains the boards is itself tracked on a board.

## Two sources of truth, one direction

There are two audiences for project state. The **agent** needs a working substrate it can read and write freely — that's the vault (roadmap, plans, progress). The **human** needs a glanceable, familiar surface — that's a GitHub Project board. The temptation is to let both be authoritative and reconcile them. Crickets refuses that: reconciliation between two writable stores is where drift, conflicts, and "which one is right?" live.

Instead the relationship is strictly directional:

```
  vault (agent's source of truth)
      │  project_model.py  →  item graph (stable ids, parent-chain)
      │  project_sync.py   →  deterministic render
      ▼
  GitHub Project board (generated human mirror — never hand-maintained)
```

The board is downstream. Nothing flows back. A human reading the board is reading a faithful projection of the vault; a human *editing* the board is editing something that the next sync will overwrite — which is exactly the signal that the board is not where state lives (DC-4: one write path; deterministic, one-way, idempotent vault→board synthesis).

## Why deterministic, idempotent, single-path

Three properties make the projection trustworthy rather than merely automatic:

- **Deterministic render** — the same vault state always renders the same board: stable field order, `YYYY-MM-DD` dates, and links built from the configured remote URL rather than hand-typed. Determinism is what lets a `vault == board` drift gate (`check_project_sync.py`) exist at all — you can only assert equality against a render that's reproducible.
- **Idempotent writes** — `project_sync.py post` is a create-or-update keyed by a stable id. Re-running it converges; it never duplicates. This is what makes the board *recoverable*: if it drifts, you re-sync and it's correct again, with no manual cleanup.
- **A single write path** — exactly one path (`project_sync.py post`, backed by `gh`) ever writes to GitHub. There is no second writer to race, no back-channel to audit. The `--dry-run` boundary lets you see the render before any of it lands.

Determinism plus idempotency plus one path is what turns "sync the board" from a risky bulk mutation into a safe, repeatable projection.

## What the board mirrors — and what stays vault-only

The board does not mirror the whole vault. The materialization rule (DC-1) draws a deliberate line:

- **Feature-level-and-up is always on the board** — Versions, Features, Sub-features, Backlog items, and Ideas appear whether or not work has started. This is the part a human plans against, so it should be visible early.
- **Plans and Tasks are materialized only for the active plan** — task breakdowns are never pre-persisted to the board. A planned-but-not-started feature shows up; its eventual task decomposition does not, until that plan is the active one.

The reasoning is that a task breakdown is working detail, not planning surface. Pre-persisting every future task would flood the human view with speculative structure that churns as plans are re-cut. Keeping Plan/Task vault-only until activation keeps the board a map of *intent and active work*, not a dump of every possible decomposition.

## Silent-source attribution: present in private, stripped in public

The vault's roadmap can name a *silent source* — attribution that is meaningful in the private working record. The public Project mirror is a different audience with a different contract: the renderer **strips silent-source attribution** so it never reaches the public board. This is renderer-enforced, not a convention someone has to remember — the same determinism that makes the render reproducible makes the stripping reliable. The private vault keeps the attribution; the public projection does not carry it.

## The meta-loop

The property that makes this plugin distinctive: **the plugin that maintains the boards is itself tracked on a board.** The crickets project's own roadmap (#41 is this very plugin) is synthesized onto crickets' GitHub Project #5; agentm's roadmap onto Project #2. So the work of building the board-synthesizer appears, as Features and an active Plan, on a board the board-synthesizer renders.

This is not a gimmick — it's the strongest possible dogfood. If the projection is wrong, it's wrong about its own development, visibly. The meta-loop means the plugin's correctness is continuously under test against the one project whose state its authors know best.

## Locked design calls

| Call | Resolution |
|---|---|
| Dependency | `requires: developer-workflows`; the vault path comes from `project.json` config, **not** a hard agentm dependency (supersedes a pre-V5-split `requires: agentm` note) |
| Taxonomy | flat Type taxonomy (Version · Feature · Sub-feature · Plan · Task · Backlog-item · Idea) |
| Materialization (DC-1) | board persists feature-and-up + Sub-feature; Plan + Task stay vault-only until the plan is active |
| Synthesis (DC-4) | one write path; deterministic, one-way, idempotent vault → board |
| Silent-source attribution | named in the private vault roadmap, **stripped** from the public Project mirror (renderer-enforced) |
| Surfaces this cycle | `github-board` only — `local-index` / `none` deferred to a follow-up |

> [!NOTE]
> These calls are recorded formally in [ADR 0025 — one-way vault→GitHub-Project board synthesis](crickets-github-projects), with the "why not the alternative" reasoning per call and the re-audit triggers. This section is the narrative; the ADR is the decision of record.

## Related

- [GitHub Projects plugin](GitHub-Projects) — the reference: config schema, Type taxonomy, the six templates, field schema, and the write path.
- [Sync a project board](Sync-A-Project-Board) — the operator recipe for a sync + the inaugural backfill.
- [Why deterministic gates run first](Why-Deterministic-Gates) — the same determinism-enables-a-gate logic, applied to the phase loop.
- [Purpose and scope](Purpose-And-Scope) — where this plugin sits in the crickets / agentm split.
- [ADR 0025](crickets-github-projects) — the decision of record for the locked design calls.
