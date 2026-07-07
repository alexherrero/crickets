---
title: github-projects — design
status: launched
kind: design
scope: feature
area: crickets/github-projects
governs: [src/github-projects/]
parent: crickets-hld.md
seeded: 2026-06-20
approved: 2026-06-23
---

> [!NOTE]
> **LAUNCHED (lifted 2026-06-24, AG Phase 3; originally approved 2026-06-23) · locked 2026-06-28 (final AG design sweep).** child-design — **the `github-projects` capability** (one-way deterministic board-sync — project a vault project's roadmap/plan/progress onto a GitHub Project board). `status: launched` (lifted into tracked `wiki/designs/` 2026-06-24, AG Phase 3). Points *up* at the [crickets HLD](crickets-hld.md).

# github-projects

## Objective

`github-projects` **projects vault state onto a GitHub Project board** — a one-way, deterministic, idempotent sync where the **vault stays the source of truth and the board is the generated human mirror.** It is platform-bound (`github-`) and keeps its name. It declares `[board-sync]`.

## Overview

The renderer, model, drift detector, schema, templates, DC-2 field-mirroring, and native sub-issue nesting are all delivered (see Design):

| Primitive | Kind | What it does |
|---|---|---|
| `project_sync.py` | script | The single idempotent write path — renders each vault item to a GitHub Issue and reconciles it (create / update / noop). |
| `project_model.py` | script | The board model — the taxonomy + the Version→Feature→Sub-feature→Plan→Task parent chain + the materialization partition. |
| `check_project_sync.py` | script | The drift **detector** — fails the gate when the board body diverges from the rendered source, or an issue has no backing vault item. |
| `project_schema.json` | rule | The board-shape contract — the parent chain + the DC-2 field set (Track · Type · Priority · Start · Target · Status). |
| per-type templates | template | The locked kickoff / progress / closeout triads (task · plan · feature · sub-feature) + single-line forms (version · idea · backlog-item · promotion). |

![One-way deterministic board-sync: the vault project (roadmap · plans · progress — the source of truth) feeds project_sync.py (deterministic, idempotent render) which writes the GitHub Project board (issues + native sub-issue nesting) as a Version→Feature→(Sub-feature)→Plan→Task tree ≥4 deep, each item a kept-current summary body + a comment per commit; check_project_sync.py is a drift gate that detects but never corrects, and the Planner (TPM) persona's depth-maintainer + drift-corrector drives the write path to hold depth + correct drift](diagrams/crickets-github-projects.svg)

*One direction only — the vault is authored; `project_sync.py` renders it to nested issues (≥4 levels deep; each work item carries a kept-current summary body + a comment per commit); `check_project_sync.py` detects drift but never corrects. The **Planner (TPM)** persona's depth-maintainer + drift-corrector (AG Wave D) drives the write path to hold the depth floor + correct drift.*

### One-way, idempotent, deterministic

The sync runs **vault → board and never back.** `project_sync.py` is a single write path that converges — running it twice changes nothing the second time — so it is safe to re-run on every plan-state change. The render is fully deterministic: the script owns all structure (field order, `YYYY-MM-DD` dates, the commit/entity links built from a SHA or id, the `gh` posting); the only model-supplied part is the human sentences in the template `{{placeholders}}`. A human reads the board for a glance; the vault is where the state actually lives.

### Levels → issues, and what's on the board when

Every taxonomy type — **version · feature · sub-feature · plan · task** (plus top-level `backlog-item` · `idea` · `bug`) — renders to **one real GitHub Issue** (not a draft card, so the nesting + Gantt roll-up work), and the parent chain becomes **native GitHub sub-issue nesting**: Version → Feature → Sub-feature → Plan → Task.

**What materializes when** is the central partition (DC-1): everything **feature-and-up** — Versions, Features, Sub-features (+ top-level Backlog-items / Ideas) — is mirrored **the moment it exists, started or not** (it is the human-facing roadmap and must always be visible). **Plan + Task issues materialize only for the *active* plan**, at work-start — future plans/tasks live implicitly under their already-materialized feature until picked up, to bound issue volume. Never pre-persist task breakdowns; always persist features-and-up.

### The depth floor — at least four

A live plan's board reaches **at least four levels — Version → Feature → Plan → Task — always, with Sub-feature an optional fifth.** Flattening to epic- or feature-level is **drift** (an under-populated source), not a simplification. The always-on roadmap tier (feature-and-up) is the floor for *unstarted* work; the moment a plan goes active, Plan + Task complete the ≥4 chain beneath it.

### Two surfaces — a current-summary body and a per-commit comment trail

A version is a one-line *About*. A work item (task / plan / feature / sub-feature) carries **two surfaces**:

- **The issue body — a kept-current summary.** ① **Kickoff** (`Goal · Done-when` for a task, `Goal · Why-it-matters` for a feature) at start, ② **current progress summary** that reflects where the work stands right now, and ③ **Closeout** (`Outcome · Landed/Shipped-link · date`) at ship. The body answers *what is this, and where does it stand* — at a glance.
- **A comment per commit — the granular trail.** Each commit posts a **GitHub issue comment** — a timeline entry (`{date} ([sha](commit-url)): {summary}`, the commit link built deterministically from the SHA). The comments answer *what happened, commit by commit.* (Altitude follows the unit: a task comments per commit, a plan per task, a feature per plan shipped.)

### Per-commit comment + keep-the-summary-current — two idempotent surfaces

The two surfaces reconcile differently, both idempotently:

- **The body summary** is **re-rendered from the source and byte-compared** to the live body each sync → **create / update (`gh issue edit --body`) / noop**. Whole-body replacement means any out-of-band edit on GitHub is overwritten on the next sync, and an unchanged state is a clean noop.
- **The per-commit comments** are **append-only, posted once per commit SHA.** Idempotency is by **SHA-keyed dedupe**: before posting, the sync checks whether a comment for that commit already exists (the comment carries its SHA; the vault source records which SHAs are posted) → post only if absent. So re-running never double-posts a commit's comment.

> **Shipped (0.2.0).** The per-commit update lands as a **`gh issue comment`** post (`post_comment()`, SHA-keyed dedupe via a hidden `<!-- board:sha:… -->` marker) alongside the whole-body reconcile — the body stays the kept-current summary; the comment trail is the granular per-commit timeline, exactly as designed here.

### The message voice + operational rules — the board-write spec

Three things the board-write path must honor — a message voice, a roll-up altitude, and a set of operational rules:

**The message voice — plain English for a non-technical human.** Every per-commit line and every roll-up summary is written for the owner glancing at the board, **not** in commit-ese. The rules: no file / function / script names, no code identifiers, no config keys; describe the user-visible value or the concrete change; **never name an external project / author / tool as a source** (the silent-source rule — strip it from the public board); don't echo the conventional-commit type ("docs:" / "refactor:" still did something — say what). Approved substitutions: `vault` → "notes folder", `plugin` / `bundle` → "add-on", `harness` / engine → "the tool", `wiki` → "documentation site", `ADR` / decision-record → "decision notes", `persona` → "role", `crickets` → "the suite / project", a release bump → "Cut release X bundling the above." A drafting agent reads each commit's diff; a critic pass enforces this voice and catches leaked jargon.

**The roll-up altitude (which comment lands where).** A comment-per-commit lands on the **lowest materialized work item** — the **Plan** in the common case (Tasks materialize only when a plan is actively broken down). Summaries cascade **up** as each unit completes: a **plan-completion summary** (≤2 plain paragraphs) on its **Feature**, and a **feature-landing summary** (≤2 plain paragraphs) on its **Version**. The reader gets per-commit detail at the bottom and a human digest at every level above.

**Operational rules the build must get right:**
- **Resolve + dedupe via the issues-LIST API, never search.** `gh issue list --search` hits the search index, which lags minutes for just-created issues — so a re-run after a partial failure would create **duplicates**. List-and-match-by-exact-title (and list-comments-and-match-by-marker) are immediately consistent. Items are reused by exact title (or a stable id), created only if absent.
- **SHA-keyed comment dedupe via a hidden marker.** Each comment ends with `<!-- board:<key> -->` (key = `sha:<short>` for a commit, `plansum:<id>` / `verland:<id>` for a roll-up); the sync skips a comment whose marker is already present, so re-running never double-posts.
- **Idempotent recovery.** A transient `401 Bad credentials` on a Project mutation is expected at scale; because every step is find-or-create / skip-if-present, re-running simply converges with zero duplicates.
- **Cross-check commit coverage.** A drafting agent can silently drop a commit — diff the expected SHA set against what was drafted before posting.
- **Adding a board Track is non-destructive only if done right.** Add a single-select option by re-submitting **every existing option with its `id`** plus the new one *without* an id (the option input accepts `id`); replacing options without ids orphans every item's value. Verify zero items changed before / after.
- **At scale, pace under GitHub's content-creation secondary limit.** A bulk backfill (hundreds–thousands of comments) trips GitHub's anti-abuse limit (~80 content-writes/min **and** ~500/hour) — the error is `GraphQL: was submitted too quickly (addComment)`. Pace comment posts **≥~8s apart** (~450/hour), and on a "too quickly" error wait a **long fixed cooldown (~120s) and retry patiently** — rapid exponential retries re-poke the cooldown and *extend* the penalty. A full-history backfill (~1,100 comments) takes ~1.5–2 hours of paced posting; the normal active-work path (a few commits per plan) never approaches the limit, so this pacing only matters for one-shot backfills.

### Status — mirrored at lifecycle transitions

Status is a custom Project field — **Todo → In Progress → Done** — moved at the phase transitions, not free-floating:

- **work-start (`/plan`)** → *In Progress* + the ① kickoff;
- **while working** → stays *In Progress*; a comment posts per commit, the body summary stays current;
- **ship** → the ③ closeout → *Done* → the issue is **closed**.

Container items (Version) carry no status thread — they roll up child status natively; pre-work cards (Backlog-item / Idea) are static, ordered by Priority, with no thread until promoted.

**Built and wired (as of 0.2.0–0.2.5).** The shipping path writes the **issue body + open/closed state**, the **DC-2 Project fields** (Track · Type · Priority · Start · Target · **Status**, via `sync_fields()`), and **native sub-issue nesting** (via `sync_nesting()` / `sync_all_nesting()`, the GraphQL `addSubIssue` mutation — `gh issue` itself has no sub-issue subcommand) — all idempotent, all exercised against real boards (agentm #223/#224, crickets #142/#150–152), including a case-mismatch idempotent-skip bugfix (display-case field labels vs. `gh`'s lowercased value keys, `project_sync.py:519–521`) found and closed live. The Status *field* now moves at the same progress/closeout transitions described below; the hierarchy `project_model.py` models is the same tree `sync_nesting()` actually links.

### The drift gate detects; the Planner corrects

`check_project_sync.py` is the **detector**: a board body that differs from the rendered source is `update` drift, an issue with no backing vault item is `orphan` drift — it **fails the gate but does not auto-correct**, and this module itself is never modified by anything below. Auto-correction + holding the depth floor as plans churn is the job of the **Planner (TPM)** persona — the renamed (was the "V5-11 PM chief-of-staff") depth-maintainer + drift-corrector that *drives* this deterministic write path. It does **not** own the write path — `github-projects` owns `project_sync.py`; the Planner is the intelligence above it.

**Shipped (AG Wave D):** the corrector logic itself — `depth_maintain.py` (materializes a collapsed Feature→Plan or Plan→Task gap when the match is unambiguous — slug-equals-feature-id, an explicit `fields.plan_slug`, or the Plan's own task checklist; flags anything it can't safely infer) and `drift_correct.py` (independently re-derives `update`/`orphan` drift and acts: `update` gets the same idempotent `project_sync.py post` a manual re-sync already does, `orphan` is **never auto-closed or edited** — surfaced for operator judgment). `planner_maintain.py` composes both into one entrypoint, and `/work`/`/release` now call it at the same graceful-skip board-sync gate they already call `project_sync.py post` from.

**Still open:** the actual *persona-activation* dispatch — a runtime that reads the Planner's own `modes: [loop, sub-agent]`/`triggers:` frontmatter and routes into this script automatically — doesn't exist yet. A grounding check against agentm (where that plumbing and the Planner's manifest both live) found the shape-validation-only `persona_resolve.py`/`persona_compile.py` pipeline never branches on `modes:`, and no call site wires `triggers:` to an invocation. Until that dispatcher ships, depth + drift correction run at the one workflow-step gate this repo already has wired to board-sync (`/work`, `/release`) plus explicit invocation (`/planner-maintain`) — not yet "the Planner activates and this runs" end-to-end. When the dispatcher ships, it calls this same script.

### Opinions

None — `github-projects` **mirrors, it does not judge.** It projects whatever state the vault holds; whether that state is good, done, or correctly prioritized is the planning personas' call (the **Planner** above it), not the projection's.

## Dependencies

- **requires [development-lifecycle](crickets-development-lifecycle.md)** — it mirrors that loop's roadmap / plan / progress artifacts; the board is meaningless without the phase state that feeds it, and the `/work` commit hook is what drives the per-commit ② line.
- **driven by the [Planner (TPM)](https://github.com/alexherrero/agentm/wiki/agentm-personas) persona** — the depth-maintainer + drift-corrector logic (`depth_maintain.py`/`drift_correct.py`/`planner_maintain.py`, AG Wave D) composes `github-projects` (soft `enhances`) to hold the ≥4 depth floor + correct drift; it **drives** the write path, never owns it. The logic ships; true persona-activation dispatch (agentm's `modes:`/`triggers:` runtime) does not yet — see Risks.
- **consumed by the Operator dashboard (designed)** — a unified read-only `/status` (plans + board + phase transitions + health) extends `queue-status` and reads board-sync; see [Personas](https://github.com/alexherrero/agentm/wiki/agentm-personas).
- **routes per repo** — agentm items → Project **#2**, crickets items → Project **#5** (split 2026-06-02); each item lands on its own repo's board. `dev-setup` is intentionally vault-only (no mirror; its absence is not drift).
- Points up at the [crickets HLD](crickets-hld.md); the requires/enhances mechanics are in [crickets-composition](crickets-composition.md).

## Migrations

- **The `requires` target is renamed** — it required `developer-workflows`; that capability is now **`development-lifecycle`** (the spine rename), so the `requires:` edge re-points. Mechanical — the spine group declares both `developer-workflows` and `development-lifecycle` so the edge keeps resolving (the [composition](crickets-composition.md) rename mechanism).
- The capability name itself is stable (platform-bound, keeps `github-projects`).

## Risks & open questions

- **Persona-activation dispatch doesn't exist yet.** The depth-maintainer + drift-corrector *logic* shipped (AG Wave D — `depth_maintain.py`/`drift_correct.py`/`planner_maintain.py`), wired into `/work`/`/release`'s existing board-sync gate plus explicit invocation. What's still missing is a runtime that reads the Planner's `modes:`/`triggers:` frontmatter and activates it automatically as the persona itself — that dispatcher lives in agentm and is shape-validation-only today (confirmed by a live grounding check this same plan ran). Until it ships, "the Planner runs" means the workflow-step gate + explicit `/planner-maintain`, not true persona activation.
- **Manual net-new-Feature creation is an undocumented gap.** No automated entrypoint creates a brand-new Feature from scratch — `sync_fields`/`sync_nesting` operate on an item already in `board-items.json` with an existing issue. Today materializing a net-new Feature is a manual four-step `gh` sequence: `gh issue create` → `gh project item-add` → `gh project item-edit` (Type/Track/Status) → `gh api graphql` (`addSubIssue` nesting) — confirmed live staging this same plan (both boards' Wave-D features were materialized this way). A future Planner enhancement could absorb this into the depth-maintainer, but it is out of scope for the Planner's first cut (depth-maintenance today only fills in a missing *intermediate* level — Plan under an existing Feature, Task under an existing Plan — not a missing top-level Feature itself).
- **The Operator `/status` dashboard is designed, not built** — it consumes board-sync but lives closer to the persona / queue-status surface.
- **Re-audit triggers:** wire real persona-activation dispatch once agentm's `modes:`/`triggers:` runtime ships (call `planner_maintain.py` from it); decide + build the automated net-new-Feature-creation entrypoint if the operator wants one; reconcile against the github-projects rethink; build the unified `/status` when the Operator surface lands.

## References

- crickets `src/github-projects/` — `project_sync.py` · `project_model.py` · `check_project_sync.py` · `project_schema.json` · the per-type template set; declares `[board-sync]`
- **The conventions:** DC-1 (`v4-41-project-human-source.md`) — the materialization partition + the progress altitudes (task = per commit, plan = per task, feature = per plan shipped) + the title-in-plain-language / link-everything rules
- **The boards:** agentm → Project #2 · crickets → Project #5 (split 2026-06-02); `dev-setup` vault-only
- **Rethink in flight (2026-06-19):** `_harness/RESEARCH-FINDINGS-github-projects-rethink-20260619.md` · `HANDOFF-github-projects-rethink-20260619.md`
- **Up / consumed by:** [crickets HLD](crickets-hld.md) · [composition](crickets-composition.md) · [Personas](https://github.com/alexherrero/agentm/wiki/agentm-personas) (Planner — drives this; Operator — reads it) · [development-lifecycle](crickets-development-lifecycle.md)

## Amendment log

**2026-07-06 — the Planner (TPM) depth-maintainer + drift-corrector ships (AG Wave D, tasks 2–4).** `depth_maintain.py` materializes a collapsed Feature→Plan or Plan→Task gap when the match is unambiguous (slug-equals-feature-id, an explicit `fields.plan_slug`, or a materialized Plan's own task checklist) and flags anything it can't safely infer — never fuzzy-title-guesses a Feature-to-plan-file match. `drift_correct.py` independently re-derives `update`/`orphan` drift (never parses `check_project_sync.compute_drift`'s string lines, never modifies that module) and acts: `update` reuses `project_sync.py`'s existing `post` body-sync; `orphan` is surfaced for operator judgment and never auto-closed, per this design's own carried-forward constraint. `planner_maintain.py` composes both (persisting the depth pass's write before the drift pass's own disk re-read — a real ordering bug the task's own end-to-end test caught before the fix) and is wired into `/work`/`/release`'s existing board-sync gate plus a new `/planner-maintain` explicit-invocation command. **What did not ship:** true persona-activation dispatch — a live grounding check against agentm (where the Planner's `team-coordinator.md` manifest and the `persona_resolve.py`/`persona_compile.py` activation plumbing both live, out of this crickets-side plan's authority) found that plumbing validates a persona's `modes:`/`triggers:` frontmatter for shape only; no dispatcher branches behavior on `modes: [loop, sub-agent]`, and no call site wires `triggers:` to an invocation. So the sections above describing "the Planner drives this" describe the logic that now exists, not yet a persona that autonomously activates it — re-audit when agentm ships that dispatcher (it should call `planner_maintain.py` directly).

**2026-07-06 — reconciled to as-built (AG Wave D, task 1).** The DC-2 field-mirroring (`sync_fields()`) and native sub-issue nesting (`sync_nesting()`/`sync_all_nesting()`) sections above previously read as `[PENDING-IMPL]`/"no live callers yet" — stale since `group.yaml` 0.2.0 (both shipped, unit-tested and dry-run-tested) and 0.2.1/0.2.2/0.2.5 (three live bugfixes found exercising the write path against real boards: the Status-default-sync fix, the `item-list` pagination + case-fold fixes, and the CREATE-path item-add threading fix). The per-commit comment path (`post_comment()`, SHA-keyed dedupe) was likewise already shipped in 0.2.0, not still a "designed delta." All three sections rewritten to as-built framing; the "Built vs designed" honest-split language retired since there is no longer an undelivered split for these three mechanics. Also documented, as a newly-named (not newly-created) gap: no automated entrypoint materializes a net-new Feature from scratch (`gh issue create` → `item-add` → field-edit → `addSubIssue` nest remains a manual four-step sequence) — confirmed live during this same plan's staging research; named for a future Planner enhancement, not built here. The **Planner (TPM)** depth-maintainer + drift-corrector itself remains unbuilt as of this amendment (tasks 2–4 of the same plan build it) — re-audit this log again once those ship.

**2026-06-28 — lock-down sweep (operator review).** Converted the board-sync mermaid to a house-style hand-SVG (`diagrams/crickets-github-projects.svg`); and, per operator review, **stripped the how-we-got-here narrative** from the message-voice / operational-rules section — it now documents the board-write spec directly (the dogfood that produced it stays recorded in this log, not the body). The folded ADR 0016/0025 records and the newest-first log are unchanged. Locked as a v5–v8 guidepost.

**2026-06-28 — flagged native sub-issue nesting as designed-not-wired (critique W7).** The honest split now records that the parent-chain links producing the ≥4-deep tree, the Gantt roll-up, and child-status roll-up are `[PENDING-IMPL]` — modeled + validated in `project_model.py` but not emitted; the mechanism is a GraphQL `addSubIssue` / `gh api` call (`gh issue` has no sub-issue subcommand). *Re-audit:* wire the sub-issue links when the depth tree is built.

**2026-06-26 — board-reflection dogfood: the message voice + operational spec.** Hand-ran the full Version→Feature→Plan→per-commit + cascading-summaries discipline on both boards (agentm #2 issues #95–#106, crickets #5 issues #37–#51) ahead of the wiring, and folded the learnings into the body (see "The message voice + the 2026-06-26 dogfood"): the plain-English message voice (operator-approved substitution vocabulary; silent-source-stripped), the roll-up altitude (per-commit on the lowest materialized item; summaries cascade plan→feature→version), and the operational rules (resolve / dedupe via the issues-LIST API not search; hidden-marker SHA-dedupe; idempotent recovery from a transient 401; commit-coverage cross-check; non-destructive Track-option add; **content-creation rate-limit pacing for bulk backfills** — ~8s/post + a patient 120s cooldown on "submitted too quickly", since rapid retries extend GitHub's anti-abuse penalty). *Why not just wire what was drafted:* the dogfood caught a search-index duplication hazard, a silently-dropped commit, the safe Track-add method, and GitHub's ~500/hr content-creation limit (a full-history backfill is a ~1.5–2 hr paced grind) — all build-breaking if unlearned. *Re-audit trigger:* GitHub changes the sub-issue or single-select-option API, or the voice spec is revised.

**2026-06-24 — folded ADRs 0016 / 0025 into this design (AG Phase 4, move-and-retire).**

**0016 — Project surface split: separate agentm + crickets GitHub Projects (2026-06-03).** crickets gets its own GitHub Project (#5); 17 issues transferred from agentm's Project (#2). Operator-personal items stay in agentm. Cross-repo dependencies ride the issue graph, not the Project layer. Why not stay as a guest on agentm's Project: post-decoupling the repos have independent release cadences. Why not cross-list operator-personal: fuzzy comment-timeline ownership; pick one canonical home. Why not wait for GitHub native cross-Project dependencies: issue graph already covers the substance. *Cross-repo:* the agentm side of this decision lives in the [agentm-foundations-hld](https://github.com/alexherrero/agentm/wiki/agentm-foundations-hld) Amendment log (0008). *Re-audit triggers:* GitHub ships native cross-Project dependencies; crickets re-couples to agentm; >5 cross-repo deps in one Version Issue feels noisy.

**0025 — One-way vault → GitHub-Project board synthesis (2026-06-14).** Vault is the single source of truth; GitHub Project board is a generated mirror (never editable peer). `requires: developer-workflows`. Flat Type taxonomy. Materialization boundary: features-and-up always; Plan + Task only for the active plan. Six frozen board columns; only `Type` and `project_surface` are code-enforced enums. Single deterministic idempotent render+write path in `project_sync.py`. Why not `requires: agentm`: couples a board plugin to the whole harness. Why not two writable stores: requires conflict resolution; one-way write + idempotent re-sync needs none. Why not enumerate Track/Priority/Status in code: those vocabularies shift across the V4–V7 arc; free-form lets conventions evolve without code churn. Why not materialize all Plans/Tasks always: floods the board with speculative structure. *Re-audit triggers:* any nondeterminism enters the render path; a second writer to GitHub is added; a downstream consumer depends on a specific Status/Track/Priority vocabulary.

**2026-06-23 — authored, reviewed, and finalized.** `github-projects` is the **one-way, deterministic, idempotent board-sync** — the vault stays the source of truth, the GitHub Project is the generated human mirror; it declares `[board-sync]` and **mirrors, it does not judge** (no opinion). Every taxonomy type renders to **one GitHub Issue** with **native sub-issue nesting** (Version→Feature→Sub-feature→Plan→Task); the **DC-1 materialization partition** keeps features-and-up always on the board (the roadmap, started or not) and adds Plan+Task only for the **active plan** at work-start. The depth floor is **≥4** (Version→Feature→Plan→Task, Sub-feature an optional fifth) — epic-level is drift. Each work item carries **two surfaces**: a **kept-current summary body** (① kickoff + current progress + ③ closeout, whole-body byte-compare reconcile) and **a per-commit GitHub comment** as the granular trail. **Status** is mirrored at lifecycle transitions (Todo→In Progress→Done, Done closes the issue). The **Planner (TPM)** persona (renamed from the V5-11 PM chief-of-staff; now a persona, unbuilt) **drives** this write path to hold depth + correct drift — it does not own it.

**Built vs designed:** the renderer (`project_sync.py`), model (`project_model.py`), drift **detector** (`check_project_sync.py`), schema, and templates ship, writing the issue **body + open/closed state**. Designed-not-wired (`[PENDING-IMPL]`): the **per-commit `gh issue comment`** + **SHA-keyed dedupe** (operator decision — a comment, not the as-built body line; the body becomes the current summary), the **DC-2 field writes** incl. the Status-field transition (operator-gated backfill — argv builders with no live callers), and the **Planner** depth-maintainer / drift-corrector. Routes per repo (agentm→#2, crickets→#5; dev-setup vault-only). **Re-audit:** build the per-commit comment + dedupe; wire the DC-2 field writes; build the Planner; reconcile against the 2026-06-19 board-sync rethink (these are the pre-rethink mechanics); re-point `requires`→`development-lifecycle`; build the Operator `/status`.
