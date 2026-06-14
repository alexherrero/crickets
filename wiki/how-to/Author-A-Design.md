# How to author, translate, and sequence a design with `/design`

> [!IMPORTANT]
> **Status: pending** (V5-10 sibling #5, `design-command`). This is a forward-declared skeleton — the `/design` command is not yet built. Step bodies are reserved, not written; a later `/work` task fills them from the shipped diff. Do not follow these steps yet.

> [!NOTE]
> **Goal:** Take a problem from ambiguous brief to a sequenced set of named plans using the `/design` command's three sub-verbs — `author` (walk the 10-section design-doc template to `Status: final`), `translate` (split the final doc into structural parts), and `sequence` (emit one named plan per part, first activated and the rest staged).
> **Prereqs:** the `developer-workflows` plugin installed ([Install crickets plugins](Install-Into-Project)) at the version that ships `/design`; a clean working tree; a problem worth a design (ambiguous, multi-stakeholder, or with cross-cutting Quality-Attributes / Operations concerns). For an already-settled design, skip `/design` and go straight to [`/plan`](Run-A-Named-Plan). _Exact version + prereqs filled by `/work` once the task ships._

`/design` is the **upstream authoring step** of the phase loop — it starts *earlier* than `/plan`. Use it when the problem is not yet tasks-shaped; use `/plan` once the design is settled. The three sub-verbs run in order: `author` → `translate` → `sequence`. Each gate is a `Status:` check, so you cannot skip ahead.

## Steps

1. **Author the design doc (`/design author`).** Walk the 10-section template — Context → Design → Alternatives Considered → Dependencies → Migrations → Technical Debt & Risks → Quality Attributes → Project management → Operations → Document History — with the 11-sub-attr Quality-Attributes drill-down (each concern described, or marked `N/A: <one-sentence reason>`). The command drives the Status lifecycle `draft → review → final` and runs an inline review pass (approve / revise / skip). Only `author` transitions Status; it refuses re-invocation once the doc is `final`.

   _Filled by `/work` once the task ships._

2. **Translate the final doc into parts (`/design translate`).** With the doc at `Status: final`, the command proposes a part split (one part per Detailed-Design subsection by default, capped at ~6), offers an interactive reshape (merge / split / rename / reorder), and writes the structural part files at `<doc-dir>/parts/<part-slug>.md`. Translate **hard-gates on `Status: final`** — it refuses a `draft` or `review` doc.

   _Filled by `/work` once the task ships._

3. **Populate the part files.** Fill each `parts/<part-slug>.md` with the detailed-design content for that slice before sequencing.

   _Filled by `/work` once the task ships._

4. **Sequence the parts into plans (`/design sequence`).** The command reads the populated `parts/`, topo-sorts them (deterministic; alphabetical tie-break), and emits one named plan per part via the shipped `stage_plan.py` writer: the first part is **activated** as `PLAN-<doc-slug>-<part-slug>.md`, and the rest are **staged** into `queued-plans/`. It never touches the singleton `PLAN.md`.

   _Filled by `/work` once the task ships._

5. **Run the sequenced plans.** Pick up the activated plan with `/work --name <doc-slug>-<part-slug>` (or hand it to a worker — see [Run a coordinator-directed worker team](Run-A-Coordinator-Directed-Worker-Team)), then activate the next staged part when ready ([Run a named plan](Run-A-Named-Plan)).

   _Filled by `/work` once the task ships._

## Worked scenarios

> [!NOTE]
> The three scenarios below are reserved placeholders. Each will be filled by `/work` from a real run once the command ships.

### Scenario A — a published design (committed to the wiki)

_A `visibility: published` design routed to `wiki/designs/<slug>.md`, authored → translated → sequenced end-to-end. Filled by `/work` once the task ships._

### Scenario B — a confidential design (machine-local, not committed)

_A `visibility: confidential` design routed to `<resolved-harness>/designs/<slug>.md` (harness root resolved via `resolve_plan.py`, storage-agnostic), authored → translated → sequenced. Filled by `/work` once the task ships._

### Scenario C — reshaping the part split before sequencing

_A design whose default one-part-per-subsection split is reshaped (merge / split / rename / reorder) during `/design translate` before `/design sequence` emits the plans. Filled by `/work` once the task ships._

## Verify

_Verification commands filled by `/work` once the task ships. Expected shape: after step 1 the doc carries `Status: final`; after step 2 `<doc-dir>/parts/` holds one file per part; after step 4 the active `PLAN-<doc-slug>-<part-slug>.md` exists, the remaining parts sit in `queued-plans/`, and the singleton `PLAN.md` is untouched._

## Troubleshooting

- **`/design translate` or `/design sequence` refuses.** The doc is not `Status: final` — the translate/sequence gate is a hard `Status: final` check. Finish the `author` review pass first. _Fix detail filled by `/work` once the task ships._
- **`/design author` refuses to re-open a `final` doc.** By design — only `author` transitions Status, and it will not re-invoke after `final`. _Escape-hatch detail filled by `/work` once the task ships._
- **`/design sequence` would clobber the singleton `PLAN.md`.** It never does — it writes only named plans (`PLAN-<doc-slug>-<part-slug>.md`) via `stage_plan.py`. If you see singleton churn, that is a bug. _Detail filled by `/work` once the task ships._

## See also

- [Named plans](Named-Plans) — the reference for the phase-loop command surface `/design` joins, including the `/design` row.
- [Run a named plan](Run-A-Named-Plan) — drive the named plans `/design sequence` emits.
- [Run a coordinator-directed worker team](Run-A-Coordinator-Directed-Worker-Team) — hand the sequenced plans to workers; `tech-lead` forward-references the `/design` → `/plan` authoring arc.
- [Coordinator roles](Coordinator-Roles) — the `tech-lead` role whose authoring floor `/design` raises.
- [ADR 0024 — package /design as a command](0024-design-as-command) — why `/design` ships as a command (tested Python helper + thin prompt), not a skill.
