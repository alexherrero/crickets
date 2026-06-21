# ADR 0025 — One-way vault → GitHub-Project board synthesis (`github-projects`)

> [!NOTE]
> Status: accepted
> Date: 2026-06-14 (accepted at the roadmap #41 / catalog bundle #8 build)

> [!IMPORTANT]
> **Accepted** — catalog bundle #8 (`github-projects`, roadmap #41), group version `0.1.0`, `requires: developer-workflows`. The plugin is built and both boards are backfilled. Implementation: `src/github-projects/group.yaml` (the asset-only group), `src/github-projects/scripts/project_model.py` (the vault→item graph + DC-1 materialization), `src/github-projects/scripts/project_sync.py` (the single deterministic render + live `gh` write path), `src/github-projects/scripts/check_project_sync.py` (the `vault == board` drift gate), and `src/github-projects/templates/` (the 16 per-type template files). The decisions below held through the build.

## Context

A project has two audiences for its state. The **agent** needs a working substrate it reads and writes freely — that is the vault (roadmap, plans, progress). The **human** needs a glanceable, familiar surface — a GitHub Project board. The naïve answer lets both be authoritative and reconciles them; that is exactly where drift, merge conflicts, and "which one is right?" live.

The `github-projects` plugin answers the question differently: the vault is the single source of truth, and the GitHub Project board is a *generated* mirror of it — never an editable peer. This ADR records the locked calls for that one-way synthesis, the materialization boundary, the field schema, the render/write contract, the public-attribution stripping, and the surface scope this cycle.

**Open questions this decision resolves:**

- Does the plugin depend on `agentm` (where the phase loop originated) or on `developer-workflows` (the plugin that actually emits the phase hooks)? And where does the vault path come from?
- What is the Type taxonomy, and what happens to a type that has no template yet (`Bug`)?
- What does the board mirror, and what stays vault-only? (the materialization boundary, DC-1)
- What is the field schema, and which field values are code-enforced vs. model-supplied? (DC-2)
- One render path or many? Is the write idempotent? (DC-4)
- How is silent-source attribution handled across the private/public boundary?
- Which project surfaces ship this cycle?

## Decision

### 1. `requires: developer-workflows`, not `requires: agentm`; the vault path comes from config

The group declares `requires: developer-workflows` (`src/github-projects/group.yaml:4`). The vault project path is supplied per-project by a `project.json` (`vault_project` + `github.{owner,number}`), resolved by `load_config` (`project_sync.py:265`) — not hard-wired to an agentm checkout.

**Why not `requires: agentm`?** The board synthesizer needs the *phase hooks* (`/plan`, `/work`, `/release`, `/bugfix`) that live in `developer-workflows`, not the agentm harness itself — and after the V5 split `developer-workflows` is the standalone plugin those commands ship in. Pinning to `agentm` would couple a board plugin to the whole harness and break the "any repo with `developer-workflows` can wire a board" story. Taking the vault path from config (rather than deriving it from an agentm layout) is what lets a non-agentm project point the plugin at its own vault. This supersedes a pre-V5-split note that read `requires: agentm`.

### 2. Flat Type taxonomy; `Bug` is accepted by the graph but template-less this cycle

The board models a **flat** Type taxonomy with a parent-chain rather than nested containers: Version · Feature · Sub-feature · Plan · Task (lifecycle `①Kickoff → ②Progress → ③Closeout`) · Backlog-item · Idea. The parent-chain is enforced at load (`PARENT_TYPES`, `project_model.py:43`; `build_graph`, `project_model.py:145`; cycle guard `_assert_acyclic`, `project_model.py:185`). The `TYPES` frozenset (`project_model.py:36`) carries an eighth member — `Bug` — which the graph accepts but the renderer has **no template** for, so rendering one raises `RenderError` (`project_sync.py:247`).

**Why not nested containers (Version › Feature › … as a tree)?** A flat taxonomy with an explicit parent-chain renders to a flat board (the surface GitHub Projects actually gives you) without forcing a tree the board can't display; the parent-chain still validates structure (`Feature→Version`, `Task→Plan`, …) without a nesting abstraction the renderer would have to flatten anyway.

**Why accept `Bug` in `TYPES` but ship no template?** `/bugfix` keeps the GitHub *issue* as the bug's record this cycle (recorded in the developer-workflows hooks); a board Bug template is deferred. Carrying `Bug` in `TYPES` (so the graph and drift gate recognize it) while *refusing to render* it (a loud `RenderError`, not a silent skip) is the honest state: the type exists, the surface for it does not yet, and any attempt to materialize one fails fast rather than emitting a malformed item.

### 3. Materialization boundary (DC-1): feature-and-up always; Plan + Task only for the active plan

`materialize(graph, active_plans)` (`project_model.py:203`) persists `ALWAYS_MATERIALIZE` (`project_model.py:52` — Version · Feature · Sub-feature · Backlog-item · Idea · Bug) unconditionally; a `Plan` is materialized only when its id is in `active_plans`, and a `Task` only when its parent plan is.

**Why not materialize every Plan and Task always?** A task breakdown is working detail, not planning surface. Pre-persisting every future plan's task decomposition would flood the human board with speculative structure that churns every time a plan is re-cut. Holding Plan/Task vault-only until the plan is active keeps the board a map of *intent and active work*, not a dump of every possible decomposition — and it keeps the deterministic render small enough that the drift gate stays cheap.

### 4. Frozen field schema (DC-2): six columns; only `Type` and `project_surface` are code-enforced enums

Every materialized item carries the same six board **columns**, in order: Track · Type · Priority · Start · Target · Status. Critically, only **`Type`** (the `TYPES` frozenset) and **`project_surface`** (the config enum, `github-board` | `local-index` | `none`) are enforced enums in code. `Track`, `Priority`, and `Status` flow through as **free-form, model-supplied strings** — `Item.status` is `str | None` (`project_model.py:80`), and the schema's `fields` block (`project_schema.json:60-65`) maps the column *names*, not their values. The body-only sync path **never writes these columns**; only the operator-gated backfill or a manual edit sets a Project field.

**Why not enumerate `Track` / `Priority` / `Status` in code too?** Those vocabularies are house convention that shifts across the V4→V7 arc (Tracks come and go; P-tiers and Status labels are project-local). Hard-coding them would turn every convention tweak into a code change + dist regen + test churn, and would reject a perfectly valid model-supplied value the moment the convention drifted. Keeping them free-form (with the vocabulary documented as guidance in `project_schema.json`, not validation) lets the model own the values while the code owns only what must be stable — the Type partition the renderer dispatches on, and the surface enum the config switches on.

**Why freeze the field *set* (six columns) even though three are free-form?** A stable column set is what makes the board's shape predictable and the field-mapping (`fields` in `project.json`) a fixed contract; freezing *which* columns exist is orthogonal to enforcing their *values*.

### 5. Single deterministic, idempotent, one-way render+write path (DC-4)

Exactly one path renders and writes: `project_sync.py` owns the deterministic render (stable field order, `_CLAUSE_SEP = "  ·  "` divider at `project_sync.py:48`, `YYYY-MM-DD` dates via `fmt_date` at `:92-99`, links built from `github.url` — never hand-typed — at `:80`/`:88`/`:102-112`), and `project_sync.py post` is the **only** writer to GitHub, idempotent by stable id (`plan_item_action`, `:346`: create / noop / update by rendered-vs-current body diff). Nothing flows back from board to vault.

**Why not a separate render module and a separate writer?** Splitting render from write invites two renderings that drift — the writer's idea of the body and the drift gate's idea of the body diverging. One helper that owns *both* render and post means the gate (`check_project_sync.py`, which reuses `plan_item_action`) compares against the exact bytes the writer would post; "in sync" is definitionally "every materialized item is a no-op against its issue." Determinism is the precondition for the gate existing at all — you can only assert `vault == board` against a render that's reproducible.

**Why one-way (no board → vault reconciliation)?** Two writable stores require conflict resolution; one writable store + one generated mirror requires none. A human editing the board is editing something the next sync overwrites — which is the intended signal that the board is not where state lives. Recovery is trivial: if the board drifts, re-run `post` and it converges (idempotent), no manual cleanup.

### 6. Silent-source attribution: named in the private vault, renderer-stripped from the public board

The vault roadmap may name a *silent source* (attribution meaningful in the private record). The renderer appends `**Source (private):**` **only when `not public and item.silent_source`** (`project_sync.py:249-250`); the default public render omits it.

**Why renderer-enforced rather than a convention?** A convention someone has to remember is a leak waiting to happen on a public board. Making the strip a property of the single deterministic render path means the same determinism that makes the render reproducible makes the stripping reliable — the public projection *cannot* carry attribution the private vault holds, because the only code path that emits it is gated on `--private`.

### 7. `github-board` is the only surface this cycle

`project_surface` is an enum (`github-board` | `local-index` | `none`, defaulting to `github-board`), but only `github-board` is implemented this cycle.

**Why ship the enum but only one surface?** Reserving the enum seam now (config-validated, defaulted) means `local-index` / `none` can land as a pure follow-up without a config-schema break — the contract is forward-compatible. Implementing all three now would build two surfaces with no current consumer; the enum is the cheap, additive way to keep the door open.

## Consequences

**Positive**

- Any repo with `developer-workflows` installed can wire a board by dropping a `project.json` in its vault — no agentm dependency, no hard-coded vault path.
- The drift gate (`check_project_sync.py`) exists *because* the render is deterministic and single-path: "in sync" is "every materialized item is a no-op," computed against the exact bytes the writer posts.
- The board is recoverable by construction — idempotent one-way writes mean re-running `post` converges; a drifted board is one re-sync from correct, with no manual cleanup.
- Free-form `Track`/`Priority`/`Status` let house conventions evolve without code churn; only the genuinely-stable enums (`Type`, `project_surface`) are gate-locked.
- Silent-source stripping is renderer-enforced, so the public board cannot carry private attribution.
- The meta-loop is the strongest dogfood: roadmap #41 (this plugin) is itself synthesized onto crickets Project #5, so a wrong projection is wrong about its own development, visibly.

**Negative / accepted debt**

- `Bug` is in `TYPES` but renders to a `RenderError` — a bug authored as a board item fails fast rather than rendering. Until a Bug template ships, `/bugfix` leaves bugs as GitHub issues. **Re-audit when** a Bug board template is specified, or if operators ask for bugs on the board.
- Three of the six fields are unvalidated by code — a typo'd `Status` or `Track` is accepted. The trade is convention-agility over value-validation. **Re-audit if** an invalid field value ever causes a board/render fault rather than just an odd-looking column.
- `local-index` / `none` surfaces are reserved but unbuilt — an operator wanting a non-GitHub surface has only the enum, not the behavior.
- The body-only sync never writes board *columns* (DC-2 fields) — Track/Type/Priority/Start/Target/Status are set by the operator-gated backfill or by hand, and can drift from the vault until reconciled. (Two follow-ups are recorded: draft-issue representation and field reconciliation; both are board-FIELD concerns orthogonal to body sync.)

**Load-bearing assumptions + re-audit triggers**

- *The render is fully deterministic — same vault state always renders the same bytes.* **Re-audit if** any nondeterminism (unordered iteration, locale-dependent dates, network-derived ordering) enters the render path; the drift gate's correctness depends on it.
- *One write path, idempotent by stable id, is the only writer to GitHub.* **Re-audit if** a second writer is added (a field-setter, a non-`post` mutation, or a raw `gh project item-create` path) — the drift gate flags raw-created issues as `orphan`s precisely because they bypass the single path.
- *Free-form field values are house convention, not validation.* **Re-audit if** a downstream consumer (a report, a query, an automation) starts depending on a specific `Status`/`Track`/`Priority` vocabulary — at that point the value may need to become an enforced enum.
- *`github-board` is the only consumer of `project_surface`.* **Re-audit when** `local-index` or `none` is implemented — the default and the enum seam were chosen to make that a back-compatible addition.

## Related

- [GitHub Projects plugin](GitHub-Projects) — the reference: config schema, Type taxonomy, the six templates, the frozen field schema, and the write path.
- [Sync a project board](Sync-A-Project-Board) — the operator recipe for a sync + the inaugural backfill.
- [One-way vault-to-board synthesis](One-Way-Vault-To-Board-Synthesis) — the narrative *why* this ADR formalizes (the two-sources/one-direction shape and the meta-loop).
- [ADR 0016 — Project surface split](0016-project-surface-split) — the `project_surface` enum this plugin consumes; `github-board` here is the surface that split reserved.
- [ADR 0021 — per-plugin versioning](continuous-integration) — why `github-projects` carries its own `group.yaml` version (`0.1.0`) independent of `developer-workflows`.
- [Developer Workflows](Developer-Workflows) — the base plugin this one requires; its `/plan` · `/work` · `/release` · `/bugfix` commands emit the board updates.
