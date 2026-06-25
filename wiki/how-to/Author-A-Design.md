# How to author, translate, and sequence a design with `/design`

> [!NOTE]
> **Goal:** Take a problem from ambiguous brief to a sequenced set of named plans using the `/design` command's three sub-verbs — `author` (walk the 10-section design-doc template to `Status: final`), `translate` (split the final doc into structural parts), and `sequence` (emit one named plan per part, first activated and the rest staged).
> **Prereqs:** the `developer-workflows` plugin installed ([Install crickets plugins](Install-Into-Project)) at a version that ships `/design` (0.5.0 or later); a clean working tree; a problem worth a design (ambiguous, multi-stakeholder, or with cross-cutting Quality-Attributes / Operations concerns). For an already-settled design, skip `/design` and go straight to [`/plan`](Run-A-Named-Plan).

`/design` is the **upstream authoring step** of the phase loop — it starts *earlier* than `/plan`. Use it when the problem is not yet tasks-shaped; use `/plan` once the design is settled. The three sub-verbs run in order: `author` → `translate` → `sequence`. The gate between them is a single hard `Status: final` check (run by the tested helper `design_doc.py`), so you cannot skip ahead — only the human approval inside `author` sets `final`.

## Steps

1. **Author the design doc (`/design author`).** Run `/design author <slug> [--visibility confidential|published]` (bare `/design <slug-or-brief>` defaults to `author`). On a new slug the command bootstraps from the bundled template (`${CLAUDE_PLUGIN_ROOT}/templates/design-doc.md`), prefills frontmatter (`status: draft`, `visibility` from your flag, `author` read from `.git/config`'s `[user] name`, dates set to today), and starts the section walk.

   Walk the 10 sections in template order — Context → Design → Alternatives Considered → Dependencies → Migrations → Technical Debt & Risks → Quality Attributes → Project management → Operations → Document History. The Quality Attributes section drills all **11** sub-attrs (Security → Reliability → Data Integrity → Privacy → Scalability → Latency → Abuse → Accessibility → Testability → Internationalization & Localization → Compliance); answer each with a concern, or `N/A: <one-sentence reason>` — a bare `N/A` is pushed back. The command saves after every section, so an interrupted session resumes where you left off. When the draft is complete, pick **"Ready for review (Status → review)"**; re-run `/design author <slug>` to enter the inline review pass (Approve / Revise / Skip per section), then answer **"Approve as final?"** to transition `review → final`. Only `author` moves Status, and it refuses to re-open a `final` doc.

2. **Translate the final doc into parts (`/design translate`).** Run `/design translate <slug>`. The command runs two hard gates through the helper — `design_doc.py gate <path>` (must be `Status: final`) and `design_doc.py detailed-design <path>` (the `### Detailed Design` section must be non-empty). Both must pass or it halts with the helper's verbatim refusal. It then proposes a part split (one part per Detailed-Design subsection by default, soft-capped at ~6 with `--allow-large-design` to override) and presents it as a table for **Approve / Reshape / Cancel**. On Approve it writes one `<doc-dir>/parts/<part-slug>.md` per part (each carrying `parent_design`, `part_slug`, `dependencies`, `estimated_scope` frontmatter), then appends one Document-History row to the parent — the parent's `Status` stays `final`.

3. **Review and fill the part files.** `translate` lifts each part's Scope, Dependencies, and Verification criteria from the parent's Detailed-Design subsections, so the part files arrive populated. Read each `parts/<part-slug>.md`, confirm its Scope and dependency rationale match your intent, and flesh out any Verification-criteria bullets that need more than the parent supplied — these become the sequenced plan's Goal and Verification strategy in the next step.

4. **Sequence the parts into plans (`/design sequence`).** Run `/design sequence <slug>`. The command re-checks the `Status: final` gate and that `parts/` is non-empty and valid, then topo-sorts the parts via `design_sequence.py order <doc-dir>/parts` (deterministic; alphabetical tie-break; halts on a dependency cycle or a missing dependency, surfacing the helper's message verbatim). It maps each part to a `/plan`-shaped PLAN body (`Status: planning`, with `parent_design_doc` + `parent_part_slug` traceability frontmatter) and writes them via the shipped `stage_plan.py`: the **first** part (topo order) is `activate`d as `PLAN-<doc-slug>-<first-part-slug>.md`, and the **rest** are staged into `queued-plans/`. The singleton `PLAN.md` is never touched.

5. **Run the sequenced plans.** Pick up the activated plan with `/work --name <doc-slug>-<first-part-slug>` (or hand it to a worker — see [Run a coordinator-directed worker team](Run-A-Coordinator-Directed-Worker-Team)). Each emitted PLAN is `Status: planning`, a *draft* decomposition — run `/plan --name <doc-slug>-<part-slug>` against it to refine the tasks before `/work`. When a queued part's turn comes, activate it with `/plan --activate <doc-slug>-<part-slug>` (see [Run a named plan](Run-A-Named-Plan)).

## Worked scenarios

> [!NOTE]
> These are illustrative walkthroughs of the documented flow, not a capture of a real run. They use a small example slug, `export-pipeline`, and show the exact commands you type and the files each verb writes. Substitute your own slug and paths.

### Scenario A — a published design (committed to the wiki)

A design worth committing alongside the wiki. Author it `published`, so it routes to `wiki/designs/`:

```
/design author export-pipeline --visibility published
```

You walk the 10 sections and the 11 Quality-Attributes sub-attrs, mark it **Ready for review**, then re-run `/design author export-pipeline` and **Approve as final**. The doc now lives at `wiki/designs/export-pipeline.md` with `status: final`. Translate and sequence it:

```
/design translate export-pipeline      # Approve the proposed split
/design sequence export-pipeline
```

Resulting tree (the part split is illustrative — three Detailed-Design subsections → three parts, `command-surface` depending on `data-model`):

```
wiki/designs/
  export-pipeline.md                 # Status: final
  parts/
    data-model.md                    # dependencies: []
    command-surface.md               # dependencies: [data-model]
    rollout.md                       # dependencies: [data-model, command-surface]
<harness>/
  PLAN-export-pipeline-data-model.md            # active (first in topo order)
  queued-plans/
    PLAN-export-pipeline-command-surface.md     # staged
    PLAN-export-pipeline-rollout.md             # staged
  PLAN.md                            # UNTOUCHED
```

### Scenario B — a confidential design (machine-local, not committed)

A design you don't want committed (sensitive, or just not wiki-worthy). Drop `--visibility` (or pass `confidential` explicitly) and it routes to the resolved harness root, never the repo:

```
/design author export-pipeline      # confidential is the default
```

The command resolves the harness root via `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_doc.py" harness-root` (the vault `_harness/` in the dogfood; a gitignored `.harness/` standalone) — it never hardcodes `.harness/`. The doc lands at `<resolved-harness>/designs/export-pipeline.md`. Translate and sequence are identical to Scenario A; only the doc + `parts/` location differs:

```
<resolved-harness>/
  designs/
    export-pipeline.md
    parts/
      data-model.md
      command-surface.md
      rollout.md
  PLAN-export-pipeline-data-model.md            # active
  queued-plans/
    PLAN-export-pipeline-command-surface.md     # staged
    PLAN-export-pipeline-rollout.md             # staged
```

### Scenario C — reshaping the part split before sequencing

The default one-part-per-subsection split rarely matches the real shape. During `/design translate`, after the proposed table, choose **Reshape** instead of Approve. Say `translate` proposed four parts but `data-model` and `access-layer` are one deployable unit, and `rollout` is large enough to split:

```
Reshape
merge data-model access-layer        # → one "foundations" part; confirm merged scope
split rollout                        # → "rollout-flag" + "rollout-telemetry"; confirm split lines
rename foundations data-foundations  # optional tidy-up
Approve
```

Each op re-presents the table; the loop continues until you Approve. Only then does `translate` write the part files — Cancel at any point leaves the parent untouched and writes nothing. `/design sequence` then topo-orders the reshaped parts exactly as in Scenario A.

## Verify

After each verb, confirm the on-disk state (substitute your slug for `export-pipeline` and your doc dir for `wiki/designs`):

```bash
# After author — the doc is Status: final
grep -m1 '^status:' wiki/designs/export-pipeline.md      # → status: final

# After translate — one part file per proposed part
ls wiki/designs/parts/                                    # → data-model.md  command-surface.md  rollout.md

# After sequence — first part active, rest queued, singleton untouched
ls <resolved-harness>/PLAN-export-pipeline-*.md           # → PLAN-export-pipeline-data-model.md
ls <resolved-harness>/queued-plans/                       # → the remaining parts
test -f <resolved-harness>/PLAN.md && echo "singleton present and untouched"
```

(For a confidential design, the doc + `parts/` are under `<resolved-harness>/designs/` instead of `wiki/designs/`. Resolve `<resolved-harness>` with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_doc.py" harness-root`.)

## Troubleshooting

- **`/design translate` or `/design sequence` refuses with a `Status:` message.** The doc is not `Status: final` — translate and sequence both hard-gate on it via `design_doc.py gate`, which exits 2 with a state-specific reason (draft / review / launched / malformed) and never auto-repairs. Finish the `author` review pass: run `/design author <slug>`, walk the inline review (Approve / Revise / Skip), and answer **"Approve as final?"** with `yes`. The Status field is then `final` and the gate passes.
- **`/design translate` refuses with "Detailed Design has no content".** This is the second gate (`design_doc.py detailed-design`): the `### Detailed Design` section is scaffold-only, so there is nothing to split. Re-run `/design author <slug>`, **Revise** the Design section, and author at least one Detailed-Design subsection (the split heuristic keys off these), then re-run `/design translate`.
- **`/design author` refuses to re-open a `final` doc.** By design — only `author` transitions Status, and it will not re-invoke after `final` (that would silently re-open an approved design). The escape hatch is manual: edit the doc's `status:` frontmatter field from `final` back to `review` yourself and append a Document-History row noting why, then re-run `/design author <slug>` to enter the review pass. `author` never moves Status backwards on its own.
- **`/design sequence` halts with a cycle or missing-dependency message.** The topo-sort (`design_sequence.py order`) found a `dependency cycle detected: a → b → a` or a `part 'x' depends on 'y' which does not exist in parts/`. Edit the offending part file's `dependencies:` frontmatter to break the cycle or fix the dangling slug, then re-run `/design sequence` — the order is deterministic, so a fixed `parts/` always re-sequences the same way.

## See also

- [Named plans](Named-Plans) — the reference for the phase-loop command surface `/design` joins, including the `/design` row.
- [Run a named plan](Run-A-Named-Plan) — drive the named plans `/design sequence` emits.
- [Run a coordinator-directed worker team](Run-A-Coordinator-Directed-Worker-Team) — hand the sequenced plans to workers; `tech-lead` forward-references the `/design` → `/plan` authoring arc.
- [Coordinator roles](Coordinator-Roles) — the `tech-lead` role whose authoring floor `/design` raises.
- [Development lifecycle design — package /design as a command](crickets-development-lifecycle) — why `/design` ships as a command (tested Python helper + thin prompt), not a skill.
