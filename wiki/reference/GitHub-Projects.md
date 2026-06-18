<!-- mode: reference -->
# GitHub Projects plugin

> [!NOTE]
> Implemented — catalog bundle #8 (roadmap #41), group version `0.1.0`. Every value below documents the built plugin under `src/github-projects/` with `file:line` references; the locked design calls are recorded in [ADR 0025](0025-board-sync-vault-to-project).

The `github-projects` plugin (group version `0.1.0`, `requires: developer-workflows` — `src/github-projects/group.yaml:4`) synthesizes vault project state into a **GitHub Project board** — one-way and deterministically. The vault stays the agent's source of truth; the GitHub Project is the canonical *human* source, **generated and never hand-maintained**. This page indexes the config schema, the flat Type taxonomy, the six per-type templates, the frozen field schema, the materialization rule, and the single live write path. The *why* (one-way synthesis, the meta-loop, silent-source-attribution stripping) is in [One-way vault-to-board synthesis](One-Way-Vault-To-Board-Synthesis); the operator recipe is in [Sync a project board](Sync-A-Project-Board).

## ⚡ Quick Reference

| Aspect | Value |
|---|---|
| Plugin slug | `github-projects` |
| Group version | 0.1.0 (initial) |
| Requires | `developer-workflows` |
| Direction | one-way, vault → board (never board → vault) |
| Source of truth | the vault (agent); the GitHub Project is the **generated human** mirror |
| Config | a `project.json` (`vault_project` · `github.{owner,number,url,repo}` · `project_surface` · field mappings) |
| Surfaces this cycle | `github-board` only (`local-index` / `none` deferred to a follow-up) |
| Write path | one — `project_sync.py post` via `gh`; idempotent create-or-update by stable id |
| Drift gate | `check_project_sync.py` (`scripts/check-all.sh:45`, `tests-linux.yml:59`); graceful-skip with no `project.json`/`gh` |
| Types | 8 in code (`project_model.py:36`); 7 templated — `bug` is accepted but has no template this cycle (render raises) |

## `project.json` config schema

The plugin reads a per-project `project.json` (placeholder home: `<vault>/_harness/project.json`) that wires a vault project to its GitHub Project board.

The schema lives at `src/github-projects/scripts/project_schema.json` (`additionalProperties: false`). Only `vault_project` + `github` are required; `github` itself requires only `owner` + `number`.

| Key | Type | Req? | Role |
|---|---|---|---|
| `vault_project` | string | **required** | the vault project slug whose roadmap/plan/progress drives the board |
| `github.owner` | string | **required** | the GitHub owner (user/org) that owns the Project |
| `github.number` | integer (≥1) | **required** | the Project number |
| `github.url` | string | optional | the canonical Project URL — link bases are built from this; **derived from `owner`+`number` when omitted**, never hand-typed |
| `github.repo` | string (`owner/name`) | optional | the repo the Project's issues live under |
| `project_surface` | enum | optional | `github-board` \| `local-index` \| `none` — defaults to `github-board`, the only surface this cycle |
| `items_source` | string (path) | optional | path to `board-items.json`; omit → the sibling `board-items.json` beside `project.json` |
| `fields` | object | optional | maps the frozen field **names** (`track`→`Track`, `type`→`Type`, …) onto the Project's columns |
| `env` | object | optional | env-var → path overrides |

Schema: `project_schema.json:7-73`. The loader (`project_sync.py:265`, `load_config`) does the minimal runtime check — `vault_project` / `github.owner` / `github.number` present, raising `SyncError` otherwise; the JSON Schema is the **documented contract**, not wired into the loader. `items_source` resolution: `_items_path_from_cfg` (`project_sync.py:488`).

> [!NOTE]
> The vault path comes from `project.json` config, **not** a hard agentm dependency — `requires: developer-workflows`, not `requires: agentm` (this supersedes a pre-V5-split note that said `requires: agentm`).

## Flat Type taxonomy

The board models a **flat Type taxonomy** (locked 2026-06-06) — seven types, with a parent-chain rather than nested containers.

| Type | Class | Parent | Notes |
|---|---|---|---|
| Version | container | — | the top-level container |
| Feature | work | Version | |
| Sub-feature | work | Feature | |
| Plan | work | Feature \| Sub-feature | |
| Task | work | Plan | lifecycle thread `①Kickoff → ②Progress → ③Closeout` |
| Backlog-item | pre-work | — | |
| Idea | pre-work | — | |

The seven types above are the locked **flat taxonomy**. In code the `TYPES` frozenset (`project_model.py:36`) carries an eighth — `Bug` — which the graph accepts but the renderer has **no template** for this cycle, so rendering one raises `RenderError` (`project_sync.py:247`). The parent-chain is enforced at load time: the `PARENT_TYPES` table (`project_model.py:43`) drives `build_graph` (`project_model.py:145`), which rejects a top-level type that declares a parent, a missing/nonexistent parent, or a wrong-type parent. `TOP_LEVEL` (`project_model.py:49`) = Version · Backlog-item · Idea · Bug. Children keep declaration order; a cycle is rejected by `_assert_acyclic` (`project_model.py:185`).

### Materialization granularity (DC-1)

The board does **not** mirror everything in the vault. What gets a board item depends on whether work has started:

| Tier | Materialized | When |
|---|---|---|
| Versions · Features · Sub-features · Backlog · Ideas | **always** (feature-level-and-up) | whether or not work has started |
| Plan · Task | **only for the active plan** | never pre-persist task breakdowns |

DC-1 lives in `materialize(graph, active_plans)` (`project_model.py:203`): `ALWAYS_MATERIALIZE` (`project_model.py:52` — Version · Feature · Sub-feature · Backlog-item · Idea · Bug) is unconditional; a `Plan` is included only when its id is in `active_plans`, and a `Task` only when its parent plan is. Graph insertion order is preserved, so the board's item order is deterministic.

## Frozen field schema

Every materialized item carries the same six fields (DC-2), in this order. These are **board columns**, not body content — the body-only sync path never writes them; only the operator-gated backfill or a manual edit sets a Project field.

| Field | Role | Value vocabulary |
|---|---|---|
| Track | the work stream | **free-form** — schema guidance: spans `V4`→`V7` + Backlog + Ideas (`project_schema.json:60`) |
| Type | one of the locked types | the only **code-enforced** field value — `TYPES` (`project_model.py:36`) |
| Priority | fix-first ordering | **free-form** — schema guidance: P-tier `P0`–`P3`, fix-first at top (`project_schema.json:62`) |
| Start | start date | a `YYYY-MM-DD` date |
| Target | target date | a `YYYY-MM-DD` date |
| Status | lifecycle state | **free-form** — no enumerated vocabulary in code (`Item.status` is `str \| None`, `project_model.py:80`) |

> [!IMPORTANT]
> Only `Type` and `project_surface` are enforced enums in code. `Track`, `Priority`, and `Status` flow through as free-form model-supplied strings — the schema's `fields` block (`project_schema.json:60-65`) maps the column **names** (`track`→`Track`, …), not their values. Treat the vocabularies above as house convention, not validation.

## The six per-type templates

**Locked** one-line markdown templates with `{{placeholders}}` live in `src/github-projects/templates/` — 16 files. The four **work types** (Feature · Sub-feature · Plan · Task) each ship a `kickoff` / `progress` / `closeout` triad; the **container** (Version) and **pre-work types** (Backlog-item, Idea) ship a single template, plus a `backlog-item-promotion` clause.

| Type | Template file(s) | Structure (placeholders) |
|---|---|---|
| Version | `version.md` | `**About:** {{about}}` |
| Feature | `feature-{kickoff,progress,closeout}.md` | kickoff `{{goal}} · {{why_matters}}`; progress `{{date}}: {{plan_goal}} shipped ({{version}})`; closeout `{{outcome}}` · Shipped `{{release_links}}` · Deferred `{{deferred}}` (the renderer appends `→` the issue link when the deferral target is materialized) |
| Sub-feature | `sub-feature-{kickoff,progress,closeout}.md` | same shape as Feature |
| Plan | `plan-{kickoff,progress,closeout}.md` | kickoff `{{goal}} · {{done_when}}`; progress `{{date}} (→ {{task_link}}): {{progress}}`; closeout `{{outcome}}` · Shipped `{{shipped_link}}` · `{{date}}` |
| Task | `task-{kickoff,progress,closeout}.md` | the `①→②→③` lifecycle thread (below) |
| Backlog-item | `backlog-item.md` (+ `backlog-item-promotion.md`) | `What: {{what}} · Why it matters: {{why_matters}} · Priority: {{priority}} — {{priority_reason}}`; promotion clause `Promoted → {{promoted_link}} · {{date}}` |
| Idea | `idea.md` | `{{spark}} · Could promote → {{promote_target}}` |

The **Task lifecycle thread** — the three stages a Task accretes over its life, joined by blank lines (`_render_work_item`, `project_sync.py:205`):

```
**① Goal:** {{goal}}  ·  **Done when:** {{done_when}}

**② {{date}}** ([`{{sha}}`]({{commit_url}})): {{progress}}

**③ Outcome:** {{outcome}}  ·  **Landed:** {{landed_link}} · {{date}}
```

A renderer/model partition keeps the two roles disjoint (rule 6): the template owns layout + placeholder names; the model (`board-items.json`) owns the values. No `bug` template ships — see the Type note above.

## The deterministic render path

`project_sync.py` (stdlib) owns a deterministic render: stable field order, dividers, `YYYY-MM-DD` dates, and entity-id/SHA → URL links built from the remote URL in `github.url` (**never hand-typed**). The public render **strips silent-source attribution** — names present in the private vault roadmap are renderer-enforced absent from the public mirror.

| Render property | Value |
|---|---|
| Field order | stable / deterministic |
| Dates | `YYYY-MM-DD` |
| Links | built from `github.url` — entity-id / SHA → URL; never hand-typed |
| Public attribution | silent-source attribution **stripped** by the renderer |

Render contract (`project_sync.py`): the clause divider is `_CLAUSE_SEP = "  ·  "` (`project_sync.py:48`); stages join with `\n\n` (`:49`); dates go through `fmt_date` → `strftime("%Y-%m-%d")`, which also validates a `YYYY-MM-DD` input (`:92-99`). `fill()` (`:116-134`) splits a template on the divider and **drops a whole clause when any of its placeholder values is `None`** (an absent optional), but **raises `RenderError` when a placeholder key is missing from the value map entirely** (a withheld required value) — a single-space `·` inside a clause is preserved. Links are built, never hand-typed: `_entity_link` resolves an id/issue to its issue URL (`:102-112`), `commit_link` (`:80`) and `release_link` (`:88`) build from the repo/Project URL. The public render appends `**Source (private):**` only when `not public and item.silent_source` (`:249-250`) — so silent-source attribution is renderer-stripped from the public board.

## The single live write path

`project_sync.py post` is the **only** path that writes to GitHub. It is idempotent: create-or-update keyed by stable id.

The `post` subcommand (`_build_parser`, `project_sync.py:497-516`) takes:

| Flag | Role |
|---|---|
| `--config` | **required** — path to `project.json` |
| `--id` / `--issue` | select the item by vault id or by existing issue number |
| `--type` | a `<type>-<stage>` shortcut (e.g. `task-progress`); **omit for a full re-render** from `board-items.json` |
| `--commit` / `--summary` / `--date` | stage values folded into the flag-suppliable stages |
| `--active-plan` (repeatable) | which plans are active (drives DC-1 materialization) |
| `--templates` | override the template dir (defaults to the `scripts/` sibling) |
| `--private` | render with silent-source attribution (default is the public, stripped render) |
| `--dry-run` | render without writing — the preview boundary |

**Idempotency** — `plan_item_action` (`project_sync.py:346`): no issue yet → `create`; rendered body equals the current body → `noop`; else → `update`. Re-running converges.

**Stage shortcuts** — `apply_update` (`project_sync.py:386`) folds flag values only for the three flag-suppliable stages: `task-progress` (`--commit`+`--summary`), `plan-progress` (`--summary`), `task-closeout` (`--summary`+`--commit`). The template-driven stages — every `kickoff`, plus plan/feature `closeout` — are **not** flag-suppliable; they raise if you pass `--type`, because they re-render in full from `board-items.json` (`:429-430`).

## Drift gate + phase-hook emission

| Mechanism | Behaviour |
|---|---|
| Drift gate | `check_project_sync.py` asserts `vault == board`; wired into `scripts/check-all.sh` |
| Graceful-skip | no `project.json` or no `gh` → the gate skips cleanly (never an error) |
| Phase hooks | `developer-workflows` `/plan` · `/work` · `/release` · `/bugfix` emit the matching board update **when the plugin is installed**; graceful-skip otherwise |

The gate is `compute_drift` (`check_project_sync.py:55-90`), which surfaces four drift kinds: `create` (a vault item with no issue), `missing` (an item's issue absent from the board), `update` (the rendered body differs), and `orphan` (a board issue no materialized item claims). Exit codes: `0` clean **or** graceful-skip, `1` on drift, `2` on an operational `CheckError`. Graceful-skip is `return 0` when there's no `project.json` (`:133-136`) or no `gh` on PATH (`:138-140`). The read side is `fetch_board_bodies` (`:101-113`, `gh issue list --state open`). Phase emission is wired into `developer-workflows` 0.12.0: `/plan` emits **Plan kickoff**, `/work` emits **Task progress** (`--type task-progress`), `/release` emits **Plan + Feature closeout**, and `/bugfix` carries a graceful-skip note — each checks `find_capability.py board-sync` (via the agentm capability resolver) and skips silently when unavailable.

## Wired boards

Each board is wired by a `project.json` in that project's vault `_harness/` (gitignored — never in the public repo); the config carries no PII.

| Project | Board | Status |
|---|---|---|
| crickets | `alexherrero/crickets` Project #5 | wired + backfilled (18 open issues synced byte-for-byte) |
| agentm | `alexherrero/agentm` Project #2 | wired + backfilled (16 items synced) |

> [!NOTE]
> The inaugural backfill of both boards to current state was **operator-gated** — the one bulk write, run only on explicit approval. See [Sync a project board](Sync-A-Project-Board#backfill-both-boards-operator-gated).

## See also

- [One-way vault-to-board synthesis](One-Way-Vault-To-Board-Synthesis) — the *why*: one-way deterministic synthesis, the vault-as-source-of-truth, and the meta-loop.
- [Sync a project board](Sync-A-Project-Board) — the operator recipe for a board sync + the inaugural backfill.
- [Developer Workflows](Developer-Workflows) — the base plugin `github-projects` requires; the phase commands that emit board updates.
- [CI gates](CI-Gates) — the gate battery `check_project_sync.py` joins.
- [Plugin anatomy](Plugin-Anatomy) — what a crickets plugin's `scripts/` payload is.
- [ADR 0025](0025-board-sync-vault-to-project) — the locked design calls (DC-1 / DC-2 / DC-4, taxonomy, silent-source, surface) and why-not-the-alternative per call.
