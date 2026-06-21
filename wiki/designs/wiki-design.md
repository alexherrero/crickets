---
title: Wiki Design
status: final
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-09
updated: 2026-06-09
last_major_revision: 2026-06-09
prd: <none — codified retroactively from the shipped wiki system: the intent-grouped IA (ADR 0018) + wiki-sync.yml + check-wiki.py + the template/voice spec>
project:
---

<!--
  Codification design (2026-06-09): the wiki system shipped across the
  2026-06-08 IA restructure + the wiki-maintenance plugin work and had no
  holistic design doc; the operator's CI-design review also moved the
  wiki-publish documentation here (deployment, not CI). Status lifecycle:
  draft → review → final → launched; the operator drives transitions.
-->

# Wiki Design

## Context

### Objective

The crickets wiki is the project's documentation, written in `wiki/` in the repo and published as a GitHub wiki. GitHub wikis are flat, resolve links case-insensitively, and show one sidebar — all of which fight structure. This design records how the wiki gets real structure anyway (intent-grouped folders, per-folder sidebars, section landing pages), and how it's linted, deployed, and kept in the operator's voice.

### Background

Machine-maintained docs rot in two ways: structurally (broken links, mixed page types, orphaned pages) and tonally (generic AI prose nobody wants to read). The wiki system attacks both — a deterministic linter (`check-wiki.py`) for structure, and a template + voice layer (the [wiki-maintenance plugin](Wiki-Maintenance)'s authoring engine) for tone. The information architecture itself was reworked on 2026-06-08 ([ADR 0018](wiki-maintenance-design)) after the original flat layout outgrew its single sidebar.

The publishing environment drives most of the design. GitHub wikis resolve page links **by basename**, **case-insensitively**, and render the **nearest** `_Sidebar.md` to the page being viewed. Those three behaviors give us the collapse/expand navigation trick (one sidebar per folder) — and the failure mode the linter exists for: two pages whose names differ only in case silently clobber each other when published.

The source of truth stays in the repo, so everything rides the normal dev flow: pages are reviewed as diffs, `check-wiki --strict` gates every push as part of [CI](continuous-integration), and a small deploy workflow mirrors `wiki/` to the GitHub wiki on every push that touches it. Publishing costs nothing and needs no infrastructure of ours.

## Design

### Overview

Pages live in folders named for reader intent — a fixed seven-section frame: `how-to/`, `reference/`, `architecture/`, `designs/`, `explanation/`, `decisions/`, `operational/` — and each folder carries its own sidebar and a landing page. Five of those sections are always present; two are conditional — **Architecture** (when the repo declares components in a `wiki/architecture.yml` manifest) and **Operational** (non-public wikis only) — per the [section taxonomy](wiki-section-taxonomy). Because GitHub renders the nearest sidebar, a reader inside Reference sees Reference expanded and every other section collapsed to a heading; the root sidebar (used by Home) shows everything expanded one level. Section headings link to the landing page — a short, curated "what's in here" with recent changes — never to an arbitrary first page. Every page is exactly one kind of thing (a tutorial, a how-to, a reference, an explanation, or an index), written against a shared template library in the operator's voice. A linter enforces all of it on every push, and a deploy workflow mirrors the folder to the live wiki. A repo gets this whole structure **in one shot** — `wiki-init` scaffolds the folders, landings, and sidebars and drops the lint-then-publish workflow, idempotently and preview-first — after which the maintenance loops keep it current (provisioning is detailed in the [provisioning design](wiki-maintenance-provisioning)).

### Infrastructure

The wiki runs on **GitHub's wiki rendering** (display) plus **GitHub Actions** (deploy); the source is the repo's `wiki/` tree. Nothing is self-hosted.

**The components:**

| Component | Where | What it does |
|---|---|---|
| `wiki/<section>/` folders | repo | the intent-grouped page tree; one folder per section |
| `wiki/architecture.yml` (optional) | repo | the per-project Architecture manifest — declares the components (and recurring pillars) that grow the `architecture/` section and its nested third sidebar level |
| `_Sidebar.md` (root + per-folder) | repo | navigation; GitHub renders the nearest one → collapse/expand behavior |
| Section index pages (`<!-- mode: index -->`) | repo | per-section landings: what the section is + curated one-liners + Recent changes |
| `check-wiki.py` | `src/wiki-maintenance/scripts/` (plugin-single-sourced) | the deterministic linter (modes, links, sidebars, basenames) — a [CI](continuous-integration) gate; a provisioned repo's CI runs a vendored copy under `.github/scripts/` |
| Template spec + section library | `src/wiki-maintenance/skills/diataxis-author/templates/` | the page shapes (§2 library, §3 structural conventions, §4 voice) |
| Voice overlays | the operator's vault (`_global/wiki-style/` + per-project) | learned voice lessons, read at authoring time |
| `[W] Update Wiki` (`wiki-sync.yml`) | Actions | one workflow, two jobs — `lint-wiki` (the gate) then `update-wiki` (`needs: lint-wiki`, mirrors `wiki/` to the GitHub wiki) |

**When what runs:**

| Trigger | What runs |
|---|---|
| Operator provisions a repo (`wiki-init`) | scaffold the seven-section frame (Architecture from `wiki/architecture.yml` when present) + drop the lint-then-publish workflow + vendor the gate (one-time, preview-first) |
| Push to the default branch touching `wiki/**` | `lint-wiki` gates, then `update-wiki` publishes (also manually runnable via `workflow_dispatch`) |
| Every push + PR | `check-wiki.py --strict` as a [CI](continuous-integration) gate (the battery, and the workflow's own `lint-wiki` job) |
| Phase boundaries (`/plan` · `/work` · `/release`) | the `documenter` agent authors/repairs affected pages (synchronous) |
| Operator loop / cron | a `wiki-watch` cycle — detect doc-worthy changes, dispatch the documenter, PR-default (asynchronous) |

**What the system guarantees:** every internal link resolves; every page is exactly one mode; no two basenames collide case-insensitively (checked twice — the linter and the deploy job); the published wiki mirrors the repo tree exactly (add, edit, rename, delete); and authored pages start from the shared templates and the operator's voice rather than from scratch.

### Detailed Design

#### 1. The intent-grouped IA + section landings

Seven sections in a fixed order, named for what the reader wants: How-to · Reference · Architecture · Designs · Explanation · Decisions · Operational — `wiki_init.py`'s `DEFAULT_SECTIONS` scaffolds them and `check-wiki`'s `_FOLDER_MODE` is the matching allow-list. Two are conditional: **Architecture** renders only when a `wiki/architecture.yml` manifest declares components — and is the one section that nests a third level, each component expanding under the section heading in the root sidebar — and **Operational** renders only for non-public visibility; the other five are always scaffolded. Each has an **index landing page** (`<!-- mode: index -->`, shape-exempt from Diátaxis rules): a short statement of what the section is, its pages as curated one-liners (not regurgitated intros), and a tooling-maintained **Recent changes** block. Sidebar section headings link to the landing, never the first sub-page.

#### 2. Sidebars — the nearest-wins trick

GitHub renders the `_Sidebar.md` **nearest** to the current page. The root sidebar (rendered on Home) shows all sections expanded one level; each folder's sidebar expands only its own section and collapses the rest to linked headings. The effect is two-level navigation on a platform that only supports one sidebar — verified live against the rendered wiki when it shipped ([ADR 0018](wiki-maintenance-design) records the call and its load-bearing assumption).

#### 3. Naming rules

GitHub resolves page links **by basename only** (folders don't namespace) and **case-insensitively**. Two rules follow: every basename must be unique across the whole tree ignoring case, and when a user-facing page and an internal design page want the same name, **the user-facing page owns the clean name** and the design page takes a `-design` suffix (`developer-safety` the plugin page vs `developer-safety-design` the design part). The linter's rule-g enforces uniqueness; the convention lives in the template spec §3.

#### 4. Page shapes + voice

Every page declares (or inherits from its folder) one mode — tutorial, how-to, reference, explanation, or index — and is built from the **section library** in the template spec: reusable section shapes (quick-reference, section-contents, recent-changes, host-differences, …) and page templates (home, plugin-home, section-index). Voice comes in layers: the spec's §4 base voice ⊕ the operator's learned overlay (global / per-project / per-repo), captured from real operator edits by the [style-learning loop](Style-Learning-Loop). Design docs are the exception: they keep the `/design` 10-section structure, never reshaped without the operator.

#### 5. Linting — `check-wiki.py`

The deterministic gate: pages live under a mode folder (rule-a), tutorials/how-tos carry their mode block (b), basenames are unique case-insensitively (g), internal links resolve (h), Home + the sidebar union reference every page (j), word-count soft ceilings (k), README links resolve (l). `--strict` promotes structural findings to failures and runs in the [CI](continuous-integration) battery on every push, so a broken wiki can't merge.

#### 6. Publishing — `wiki-sync.yml`

`wiki-sync.yml` is **one workflow with two jobs**: `lint-wiki` runs the `check-wiki` gate (on push + PR), and `update-wiki` (`needs: lint-wiki`) does the publish below — so a structurally-broken wiki can never reach the live wiki, even on a direct push to the default branch. (These were briefly two independent workflows; merging them turned the lint from a tripwire into a real gate — the 2026-06-10 reconciliation in the [provisioning design](wiki-maintenance-provisioning).)

The publish job (**deployment, not CI**): on every push to the default branch touching `wiki/**` (or a manual `workflow_dispatch`), it mirrors `wiki/` into the GitHub wiki with `rsync -a` — add, edit, rename, delete; the directory tree is preserved, which is what makes per-folder sidebars render. Before syncing it **fails loudly on case-insensitive duplicate basenames** (`_Sidebar.md`/`_Footer.md` exempt — they're location-rendered, never linked), and it gracefully skips when the repo's wiki is disabled. A bad publish self-heals: the next green push re-mirrors the whole tree.

#### 7. Maintenance — who keeps it current

Three loops, all reusing the same writer (the `documenter` agent, hard-scoped to `wiki/**`): **synchronous** — the developer-workflows phase commands dispatch the documenter at phase boundaries so docs track the code; **asynchronous** — the wiki-watcher runs idempotent cycles (cursor-backed, PR-default) against watched repos; **operator-paced** — the style-learning loop, where the operator's edits to drafted pages become durable voice lessons. The [wiki-maintenance plugin](Wiki-Maintenance) ships all three.

## Alternatives Considered

1. **A static docs site (MkDocs / GitHub Pages) instead of the GitHub wiki.** Rejected for now: the wiki is zero-infrastructure, lives beside the repo where readers already are, and needs no build pipeline. The flat-namespace and sidebar constraints are real costs — *revisit if the IA outgrows the nearest-sidebar trick.*
2. **A flat wiki, no folders.** Rejected: it's where we started; one sidebar listing every page doesn't scale past a few dozen pages, and there's no way to orient a reader by intent.
3. **One global sidebar with manual "collapsing."** Rejected: GitHub renders the nearest sidebar anyway — fighting that with one file means every section change edits one giant file and readers always see everything.
4. **Section headings linking to the first sub-page.** Rejected (operator call): a reader clicking a section wants to know what the section *is*; landing on an arbitrary page is disorienting. Hence the index landings with curated contents.
5. **Generating the wiki from code comments/docstrings.** Never seriously considered: the wiki's value is curated, reader-intent-shaped prose in the operator's voice — the opposite of extracted reference dumps.

## Dependencies

- **GitHub wiki rendering behavior** — nearest-`_Sidebar` rendering, basename link resolution, case-insensitive matching. **Load-bearing and undocumented**: the whole IA rides on observed behavior. *Re-audit trigger: any change in GitHub wiki rendering, or a platform move.*
- **GitHub Actions** — the deploy job (`contents: write`).
- **`check-wiki.py`** + the [CI](continuous-integration) battery — the enforcement layer.
- **The template spec + section library** (`src/wiki-maintenance/.../templates/`) and the **voice overlays** in the operator's vault — what pages are authored from.
- **The [wiki-maintenance plugin](Wiki-Maintenance)** — the documenter, the watcher, and the learning loop that maintain the tree.

## Migrations

- **2026-06-08 — flat → intent-grouped** ([ADR 0018](wiki-maintenance-design)): pages moved into section folders; per-folder sidebars added; section index landings created; `check-wiki.py` gained folder-mode defaults, the `index` mode, and the mode-hint comment. Verified against the live rendered wiki.
- **2026-06-09 — case-collision renames:** the `-design` suffix convention applied to five design pages whose basenames collided case-insensitively with user-facing pages; rule-g made case-insensitive (it caught the second collision the moment it landed).
- **2026-06-09 — the Agent-M design docs relocated** to the agentm wiki (they document the sibling system); crickets pages re-pointed.
- **2026-06-11 — intent-folders → seven-section frame** ([section taxonomy](wiki-section-taxonomy)): the pass-1 reader-intent folders were reconciled to the fixed seven — `get-started/` + `do/` → `how-to/`, `why/` → `explanation/`, `plugins/` → `architecture/plugins/`; `architecture/`, `designs/`, `decisions/`, and (non-public wikis only) `operational/` round out the frame. Architecture gained a per-project `wiki/architecture.yml` manifest and a third sidebar nesting level; Architecture and Operational became the two conditional sections.
- Page retirements follow the standard pattern: fold the content into its successor, repoint every inbound link, delete — never leave a stub.

## Technical Debt & Risks

1. **Sidebars and Recent-changes blocks are hand-maintained.** Seven sidebars + per-section recent-changes lines, all edited by hand (today, by the agent during doc work) — they drift if a page lands without the nav edit. `check-wiki` rule-j catches missing references; it can't catch stale Recent-changes. ***Planned fix: the composer*** — generate the sidebars and Recent-changes blocks from the tree + git metadata.
2. **The nearest-sidebar behavior is undocumented GitHub behavior.** It's observed, live-verified, and load-bearing. *Re-audit on any GitHub wiki rendering change.*
3. **`rsync` publish is one-way and trusting.** A bad push to the default branch publishes instantly; there's no staging wiki. Mitigated: `check-wiki --strict` gates the same push in CI, and the wiki is fully regenerable — the next green push re-mirrors everything.
4. **The wiki tree and the vault overlays can disagree.** Voice lessons live in the operator's vault; a fresh machine without the vault authors from the base spec only. Graceful degradation by design, but the output voice differs. *Accepted; the overlay store is the operator's to sync.*

## Quality Attributes

*(Only the attributes with real concerns are kept, per the design convention.)*

### Security

The wiki is public and synced from the repo, so the same PII discipline applies: `wiki/**` is inside the [CI](continuous-integration) PII gates (`check-no-pii` + gitleaks) and the pre-push hook's scope. The deploy job holds `contents: write` on the wiki only.

### Data Integrity

The case-collision failure mode is silent page-clobbering on publish — guarded twice (linter rule-g + the deploy job's dupe-check). Mirror semantics mean the repo tree is always the truth; the published wiki carries no state of its own.

### Accessibility

Readable prose **is** the product: plain language, de-jargoned, one mode per page, curated landings — the voice layer exists so a human actually wants to read these pages. No GUI surface of ours beyond GitHub's.

### Testability

Structure is fully deterministic (`check-wiki --strict` in CI); rendering behavior is not — nearest-sidebar and link resolution are verified by **live spot-checks by the agent** (fetching the rendered wiki) after IA changes, since no local renderer reproduces GitHub's wiki.

### Internationalization & Localization

Deferred but real: the section-template system must eventually support multiple languages (≥ Spanish). Language becomes a first-class axis when the template system gets its own design pass — recorded so it isn't designed out by accident.

## Project management

*(Shipped system — work estimates omitted per the design convention.)*

### Documentation Plan

Every wiki page documenting this system:

- **[ADR 0018](wiki-maintenance-design)** — the IA decision (per-folder sidebars + intent grouping) with its load-bearing assumption.
- **[CI gates](CI-Gates)** — where `check-wiki --strict` runs; the deploy job's place in the workflow table lives here in the [CI design](continuous-integration)'s sibling sense.
- **[Style-learning loop](Style-Learning-Loop)** — the voice layer's reference.
- **[Run the wiki-watcher](Run-The-Wiki-Watcher)** + **[Wiki Watch Config](Wiki-Watch-Config)** — the async maintenance loop.
- **[Wiki Maintenance](Wiki-Maintenance)** (plugin page) + **[wiki-maintenance design](wiki-maintenance-design)** — the toolchain that maintains the tree.
- **[Provision a repo's wiki](Provision-A-Repo-Wiki)** (how-to) + **[provisioning design](wiki-maintenance-provisioning)** — scaffolding a wiki + its CI from nothing, and the gate-distribution split (reference for the agent, vendor for CI).
- **[Declare a project's Architecture](Declare-Architecture)** (how-to) + **[Wiki Section Taxonomy](wiki-section-taxonomy)** (design) — the seven-section frame, the two conditional gates, and writing the `wiki/architecture.yml` manifest that grows the Architecture section.
- **This design** — the wiki system itself; future IA/publish changes amend it.

### Launch Plans

Already launched: the publish pipeline has mirrored `wiki/` since the repo's early releases; the intent-grouped IA + per-folder sidebars + section landings since **2026-06-08** ([ADR 0018](wiki-maintenance-design)); the case-insensitive guards + `-design` convention since **2026-06-09**.

## Operations

*(SLAs and a logging plan are omitted — GitHub's availability and the Actions logs are the whole story.)*

### Monitoring and Alerting

The `[W] Update Wiki` workflow result rides the same per-push run set the agent already watches (wake-on-CI): the **agent (LLM)** reads it alongside the test results and reports a failed publish to the operator. After IA-affecting changes, the agent additionally spot-checks the live rendered wiki (sidebar collapse, landing pages) — GitHub's rendering can't be verified locally.

### Rollback Strategy

Everything is repo-versioned: revert the commit and the next push re-mirrors the wiki to the previous state. A bad publish can't strand anything — mirror semantics make the live wiki converge to whatever `wiki/` says.

## Document History

| Date | Change | Status |
|---|---|---|
| 2026-06-09 | Codified retroactively from the shipped wiki system (the 2026-06-08 IA restructure / ADR 0018 · wiki-sync.yml · check-wiki.py · the template/voice spec · the three maintenance loops). Created at operator direction during the CI-design review — wiki publishing is deployment, not CI, and belongs here. Authored against the 10-section template with the 2026-06-09 conventions (plain title · 4-sentence objective · 3-paragraph background · platform-first infrastructure · N/A sections omitted · PM slimmed for shipped systems). | draft |
| 2026-06-10 | Operator green-light → **final**. Build order: tweaked + built **after wiki-init**, before continuous-integration (the composer — generate sidebars + Recent-changes from per-release notes — is the main tweak, with i18n ≥ Spanish a first-class axis). | final |
| 2026-06-10 | **Provisioning joins the narrative** (`wiki-maintenance-provisioning` docs-adr part). Added `wiki-init` to the Overview, the components + "when what runs" tables, and the Documentation Plan. Reconciled two now-stale details from the provisioning dogfood: `check-wiki.py` is plugin-single-sourced (`src/wiki-maintenance/scripts/`, repo-root copy gone; CI vendors a `.github/scripts/` copy), and `wiki-sync.yml` is now one workflow with two jobs (`lint-wiki` gates `update-wiki`) after the drift-1 merge. Content-only; no section restructure; Status unchanged. | final |
| 2026-06-11 | **Taxonomy joins the narrative** (`wiki-section-taxonomy` docs-adr part). Reconciled the fixed seven-section frame (How-to · Reference · Architecture · Designs · Explanation · Decisions · Operational) across the Overview, Detailed Design #1, the components + "when what runs" tables, and the Documentation Plan — replacing the retired pass-1 `get-started/do/why/plugins` intent-folders. Recorded the two conditional gates (Architecture-on-manifest, Operational-on-visibility), Architecture's third nesting level + its `wiki/architecture.yml` manifest, and a Migrations row for the folder reconciliation. Content-only; no section restructure; Status unchanged. | final |
