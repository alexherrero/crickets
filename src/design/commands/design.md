---
name: design
description: Author → translate → sequence a design doc into a topo-ordered set of named plans. The upstream authoring step above /plan.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: author <slug|brief> (default)  |  translate <slug>  |  sequence <slug>
---

You are running the **design** command — the upstream authoring step of the development-lifecycle loop. `/design` sits *above* `/plan`: where `/plan` turns a brief into a task list, `/design` walks a human through a real design doc, gates on human approval, splits the approved design into structural parts, and emits one named plan per part for `/work` + `/review` to execute.

**Arguments:** $ARGUMENTS

> **Recommended model for this phase:** Sonnet 5 (`claude-sonnet-5`) — lighter model for planning and authoring. Override with `/model` if needed.

> **Three verbs, one pipeline.** `/design author` (write + finalize a design doc) → `/design translate` (split a final doc into structural `parts/`) → `/design sequence` (topo-order the parts into named plans). The pipeline is strictly ordered by a single hard gate — `Status: final` — which only a human approval can set. Each verb is documented in its own section below.

## Dispatch

`$ARGUMENTS` selects the sub-verb. The first token is the verb; the rest is its argument (a slug, or — for `author` on a new doc — a brief). Bare `/design <slug-or-brief>` with no recognized verb defaults to **`author`** (the common case).

| Invocation | Verb | What it does |
|---|---|---|
| `/design author <slug\|brief>` (or bare) | **author** | Write a new design doc or resume/review an in-progress one. The **only** verb that transitions `Status`. |
| `/design translate <slug>` | **translate** | Split a `Status: final` doc into structural `parts/<part-slug>.md`. Refuses on non-final. |
| `/design sequence <slug>` | **sequence** | Topo-order `parts/` into named plans (first activated, rest queued). Refuses on non-final. |

## Shared conventions

These hold across all three verbs.

### Status lifecycle (the hard gate)

A design doc carries a `status:` field in its frontmatter with exactly four states:

| Status | Meaning | Set by |
|---|---|---|
| `draft` | Authoring in progress; not yet submitted for review. | `/design author` |
| `review` | Author signaled readiness; awaiting human approval. | `/design author` |
| `final` | **Human-approved. HARD GATE** — `translate` + `sequence` only run here. | `/design author` |
| `launched` | All queued parts have shipped via `/work` + `/release`. | harness `/release` (manual today — auto-promotion deferred) |

`/design author` is the **only** verb that transitions `Status` (`draft → review → final`); it never advances past `final`. `translate` and `sequence` **never** change Status — they call the shared gate `design_doc.py gate <path>` (or `require_final()`), which exits non-zero with a state-specific message on any non-`final` doc and **never auto-repairs**. A refusal points the operator back to `/design author` to finish the review pass. This gate is what makes the downstream pipeline trustworthy: it preserves the human-approval signal.

### Storage resolution (never hardcode `.harness/`)

Designs live in one of two places, by the doc's `visibility:` field:

- **confidential** → `<harness>/designs/<slug>.md` — the **resolver-resolved** harness root (the vault `_harness/` in the dogfood; a gitignored `.harness/` standalone). Resolve it with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_doc.py" harness-root` — **never a hardcoded `.harness/`**. A non-zero exit is a hard stop that surfaces stderr (no silent fallback — Risk #7).
- **published** → `wiki/designs/<slug>.md` — committed; the crickets path (**not** agentm's `wiki/explanation/` tree). Surfaces in `wiki/Home.md` + `_Sidebar.md`.

Parts live beside their doc: `<doc-dir>/parts/<part-slug>.md`.

### Tested helper vs. thin prompt

Crickets diverges from agentm's no-Bash `Read/Write/Edit/Glob/Grep`-only skill on purpose: the **deterministic, falsifiable** pieces (the `Status: final` gate, frontmatter parsing, harness-root resolution, the Kahn topo-sort, PLAN emission) live in unit-tested stdlib-only Python helpers — `scripts/design_doc.py` (gate + storage) and `scripts/design_sequence.py` (topo-sort) — invoked via `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<helper>.py" …`. The **interactive, human-judgment** pieces (the section walk, the split proposal, approve/revise/skip) stay in this prompt body. Helpers never own interactive logic; the prompt never re-derives a gate or a sort.

### External review is deferred (#5b)

The host-specific external-review handoff (the Antigravity/Gemini transfer-context + pre-handoff snapshot + `--resume-external-review` resume flow) is **deferred** to follow-on #5b. This command ships the **inline** author/review flow only. Where agentm offers a "Hand off for external review" branch, crickets shows a one-line "deferred to #5b" pointer — not a live flow.

### No PII

This is a public repo. Never write the vault path or any PII token into a committed file; the helpers resolve confidential paths at runtime so nothing host-specific is baked in.

### Behavioral contract (development-lifecycle commands)

When a design covers a development-lifecycle command or agent lifecycle step, verify these two checklist items before finalizing:

1. **Recoverability-gate compliance** — does the command treat invocation as authorization to run to completion? Recoverable actions (push, tag, gh release, create) must proceed announced; only genuinely unrecoverable ones stop. A design step that inserts "summarize and wait" after each recoverable action is a contract defect.
2. **Close-out autonomy** — are close-out and bookkeeping steps (plan archiving, `progress.md` appends, ROADMAP moves) autonomous — never gated on explicit approval? If a step pauses for confirmation before archiving a completed artifact or writing a log entry, that is a defect.

These items are derived from `corrections.md` seeds via the upstream-guardrail mechanism (developer-workflows-autonomy part 3).

## `/design author` — write + finalize a design doc

`author` is the **only** verb that transitions `Status` (`draft → review → final`); it never advances past `final`. It runs in one of three modes by the target doc's existing Status: **bootstrap** (no doc yet), **authoring** (`draft`), **review pass** (`review`). Save after every section so a partial draft survives an interrupted session.

**Inputs.** `<slug>` (filename identifier — required for a new doc, inferred from the path on resume) and `--visibility {confidential|published}` (defaults to `confidential`). Visibility routes the output path per *Storage resolution* above: `confidential` → `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_doc.py" harness-root` then `<harness>/designs/<slug>.md`; `published` → `wiki/designs/<slug>.md`. To resume, locate the doc through the same two-path lookup (if both exist, ask which); never hardcode the confidential root.

### Step 1 — Bootstrap (new doc only)

If the target path doesn't exist:

1. Confirm the title (default: derive from the slug → title case).
2. Copy the template at `${CLAUDE_PLUGIN_ROOT}/templates/design-doc.md` to the target path.
3. Prefill frontmatter: `title` ← confirmed title; `status: draft`; `visibility` ← caller's choice; `author` ← read from `.git/config`'s `[user] name = …` (if unreadable/absent, **prompt** the human — never leave `author` blank); `contributors: []`; `created`/`updated`/`last_major_revision` ← today (`YYYY-MM-DD`).
4. Seed the Document History table with the initial row: `| <today> | Initial draft created via /design author. | draft |`.
5. Confirm the path + Status: draft, then start the section walk.

If the path already exists, skip bootstrap — the doc's existing Status picks the mode (authoring on `draft`, review pass on `review`).

### Step 2 — Walk sections (authoring)

For each top-level section in template order — **Context → Design → Alternatives Considered → Dependencies → Migrations → Technical Debt & Risks → Quality Attributes → Project management → Operations**:

1. Read the section's current state.
2. If empty (only the italic prompt + HTML comments): present the prompt, ask *"What goes in this section?"*, accept a multi-line response.
3. If it already has content (resume): present it, ask *"Keep / Edit / Replace?"*.
4. Write the response in, replacing the scaffolding prompt + comments (author-facing only — they don't render once filled).
5. Update the `updated` frontmatter field after each save.

Sub-sections inside **Design** (Overview / Infrastructure / Detailed Design), **Project management** (Work estimates / Documentation Plan / Launch Plans), and **Operations** (SLAs / Monitoring and Alerting / Logging Plan / Rollback Strategy) are walked as individual children, in template order.

### Step 3 — Quality Attributes drill-down (strictest discipline)

Walk all **11** sub-attrs in template order: **Security → Reliability → Data Integrity → Privacy → Scalability → Latency → Abuse → Accessibility → Testability → Internationalization & Localization → Compliance**. For each:

> *"<attr>: Does this design have <attr> concerns? Describe them, or 'N/A' with one sentence on why."*

- **Substantive content** → write it in as-is.
- **N/A** → must take the form `N/A: <one-sentence rationale>`. If the human answers bare `"N/A"`, **push back**: *"N/A needs a one-sentence reason. Why doesn't this design have <attr> concerns?"* The **N/A-rationale rule** is non-negotiable — forcing a conscious N/A catches blind spots early. If N/A piles up across attrs, flag it: *"Most designs have at least one concern in Reliability / Security / Testability — want to revisit?"*

### Step 4 — Alternatives Considered

> *"What other approaches did you consider? Why did you reject each?"*

Push for at least one alternative. Only accept `N/A: only one viable approach (<justify>)` after one explicit push-back.

### Step 5 — Save + Status lifecycle

After all sections are filled, present a summary (sections filled, sub-attrs described vs. N/A, length), then ask the human to pick one:

- **"Ready for review (Status → review)"** — transition `draft → review`; append `| <date> | Author signaled ready for review. | review |` to Document History; tell the human the next `/design author <slug>` runs the review pass.
- **"Keep drafting"** — stay `draft`; return to the section walk.
- **"Stop and resume later"** — save state; resume on the next `/design author <slug>`.

> **External review is deferred (#5b).** Where agentm offers a "Hand off for external review" branch here, crickets ships the **inline** flow only — see *External review is deferred* above. This is a one-line pointer, **not** a live handoff flow.

### Step 6 — Review pass (invoked on a `Status: review` doc)

Announce review-pass mode, then walk each section (Context → … → Operations) and each Quality-Attributes sub-attr, prompting **Approve / Revise / Skip**:

- **Approve** — passes unchanged (track the count).
- **Revise** — reopen the section via the Step-2 walk (accept new content, replace).
- **Skip** — move on (track the count).

After the walk, summarize. If anything was Skipped or Revised, ask *"Some sections still need attention. Continue review pass? Or transition to final anyway?"* To finalize, ask explicitly *"Approve as final? This locks the doc and unblocks /design translate."* On `yes`: transition `review → final`; append `| <date> | Approved as final via /design author review pass. | final |`; set `last_major_revision` to today.

### After `final` — refuse re-invocation

Once `Status: final`, `/design author` **refuses** further invocations on that doc (it would re-open an approved design). The refusal points to the downstream verbs (`/design translate`). The only way back is the manual escape hatch: a human edits the Status field directly (`final → review`) — `author` never moves Status backwards itself, and never silently transitions in any direction.

## `/design translate` — final doc → structural `parts/`

`translate` consumes a `Status: final` design doc and produces N structural-part files at `<doc-dir>/parts/<part-slug>.md` — each a focused implementation slice small enough for one `/design sequence` → `/work` cycle. translate is **read-mostly** with respect to the parent: it appends one Document-History row and bumps `updated`, but **never changes Status** (only `/design author` and the harness `/release` do).

**Inputs.** `<slug>` (or full path — resolve via the two-path lookup in *Storage resolution*; if both exist, ask which) and `--allow-large-design` (optional — bypasses the cap-of-6 soft warning; if you reach for it twice running, split the *design* upstream instead).

### Step 1 — Preconditions (two hard gates, both via the tested helper)

Both gates are deterministic, so they live in `design_doc.py` — call them; never re-derive a gate in this prompt.

1. **`Status: final`** — run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_doc.py" gate <path>`. Exit 0 → final, continue. Exit 2 → **halt** and surface stderr verbatim (it carries the state-specific refusal — draft/review/launched/malformed — pointing back to `/design author <slug>`). Never auto-repair.
2. **Detailed Design non-empty** — run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_doc.py" detailed-design <path>`. Exit 0 → the section has substantive content (prose or a `####` subsection), continue. Exit 2 → **halt** and surface stderr (`Detailed Design has no content; design too sparse to translate. Author at least one Detailed Design subsection before re-running.`). This gate exists because the `### Detailed Design` subsections drive the Step-3 split heuristic — a scaffold-only section has nothing to split.

These two refusals are the contract layer between `/design author` (produces the parent) and `/design sequence` (consumes `parts/`). Bypassing either loses the traceability from human-approved design to executed plans.

### Step 2 — Read the design

Read the full parent. Parse the 10 sections and hold for Step 3:

- `## Design / ### Detailed Design` subsections — drive the part-split heuristic.
- `## Dependencies` — each part may inherit a subset.
- `## Quality Attributes` sub-attrs — extract the part-specific concerns into each part's Verification.
- `## Operations` sub-sections — extract part-specific ops concerns.
- `## Project management / ### Work estimates` — informs each part's `estimated_scope`.

### Step 3 — Propose a part split

Heuristics:

- **Default:** one part per top-level subsection of Detailed Design.
- **Group** tightly-coupled subsections into one part when the downstream one only makes sense given the upstream (e.g. a Security model conditional on an Infrastructure choice), or they share one deployable unit (one migration + one API surface + one runbook = one part).
- **Split** a single subsection into multiple parts only if its scope is genuinely larger than one PLAN cycle can absorb.
- **Cap ~6.** More than 6 → soft warning: *"This design proposes \<N\> parts (>6). Consider splitting the design itself into multiple documents — usually a clearer story than a megadesign. Re-run with `--allow-large-design` to override."* Soft only; `--allow-large-design` overrides.

For each proposed part populate: **slug** (kebab-case, the filename), **title** (the part h1), **scope** (1–2 paragraphs lifted from the source subsection(s)), **dependencies** (other part slugs; empty for foundational parts), **verification criteria** (falsifiable claims from the parent's Quality Attributes / Operations / Documentation Plan rows that apply), **estimated_scope** (`S` one short `/work` session · `M` multiple sessions, single PLAN · `L` large — consider splitting).

### Step 4 — Human review of the split

Present the split as a table, then ask **Approve / Reshape / Cancel**:

```
Proposed split for <parent-slug> (Status: final):

| # | Slug | Title | Dependencies | Est. | Source sections |
|---|------|-------|--------------|------|-----------------|
| 1 | foundations | Foundations: data model + access layer | (none) | M | Detailed Design §1, §2 |
| 2 | command-surface | Command surface + status display | depends on #1 | S | Detailed Design §3 |
| 3 | rollout | Rollout: feature flag + telemetry | depends on #1, #2 | S | Detailed Design §4 + Operations §Monitoring |

Total: 3 parts. Approve / Reshape / Cancel?
```

- **Approve** → Step 5.
- **Reshape** → enter the reshape sub-loop; re-present the table after each op; loop until Approve:
  - `merge <slug-a> <slug-b>` — combine two parts; propose merged title/scope/verification; re-confirm.
  - `split <slug>` — split one part into two; propose the split lines; re-confirm.
  - `rename <old-slug> <new-slug>` — rename without changing structure.
  - `reorder <slug-list>` — change ordering (a numbering hint for Step 5; doesn't affect dependencies).
- **Cancel** → halt without writing anything; parent unmodified.

The reshape loop is the human's primary lever — the proposed split is a starting point, not the answer.

> **External review is deferred (#5b).** agentm offers a "Hand off for external review" branch here (a `proposed-split-<slug>.md` transfer file → Antigravity/Gemini reshape → resume diff-review). crickets ships the **inline** reshape loop only; this is a one-line pointer, **not** a live handoff — see *External review is deferred* above.

### Step 5 — Write the part files

For each approved part, write `<doc-dir>/parts/<part-slug>.md` (create `parts/` if absent):

```yaml
---
# Inherited from parent design
title: <part-specific title>
status: draft
visibility: <inherited>
author: <inherited>
contributors: <inherited>
created: <today>
updated: <today>
last_major_revision: <today>

# New part-specific fields
parent_design: ../<parent-slug>.md
part_slug: <slug>
dependencies: [<other-part-slugs>]
estimated_scope: S|M|L
---

# <Title>

## Scope

<1-2 paragraphs lifted from the parent's Detailed Design subsection(s).>

## Dependencies

<List with rationale, e.g. "depends on foundations: needs the data model + access layer before the command surface can wire up.">

## Verification criteria

<Bulleted falsifiable claims from the parent's Quality Attributes / Operations / Documentation Plan rows that apply to this part.>

## Parent design

This part implements one slice of [<parent-title>](../<parent-slug>.md) (`Status: final`). See the parent for Context, Alternatives Considered, the Quality Attributes overview, and the Operations strategy. Mid-execution scope changes to this part are appended to the parent's Document History.
```

**Never silent-clobber.** If a part file already exists (re-running translate), show the diff and ask **Overwrite / Keep existing / Cancel** per file.

### Step 6 — Update the parent's Document History

After all part files are written, append one row to the parent's Document History table and bump `updated` to today:

```
| <today> | Translated to N parts via /design translate: <comma-separated part slugs>. | final |
```

The parent's `Status` **stays `final`** — translate never changes Status.

## `/design sequence` — `parts/` → topo-ordered named plans

`sequence` consumes the populated `<doc-dir>/parts/` (translate's output) and generates one **named** plan per part, in dependency order, via the shipped `stage_plan.py` writer. This is the bridge from the design phase to the execution phase: after `sequence`, the first part is the active named plan and the rest are queued, ready for `/work`. Like translate, `sequence` is read-mostly with respect to the parent (one Document-History row, bump `updated`) and **never changes Status**.

**The crickets divergence — named-plan tiers, never the singleton.** agentm's skill writes the first part to the singleton `.harness/PLAN.md`. crickets does **not**: it stages every part as a *named* plan via `stage_plan.py`, so an unrelated active `PLAN.md` is never clobbered. The first part (topo-order) is `activate`d → `PLAN-<doc-slug>-<part-slug>.md`; the rest are written to their staging `path` under `queued-plans/`. The singleton `PLAN.md` is **never** touched.

**Inputs.** `<slug>` (or full path — same two-path lookup as translate).

### Step 1 — Preconditions (the same final gate + a non-empty `parts/`)

1. **`Status: final`** — run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_doc.py" gate <path>`. Exit 0 → continue; exit 2 → **halt** and surface stderr (the state-specific refusal pointing back to `/design author <slug>`). Never auto-repair.
2. **`parts/` exists and validates** — the topo-sort helper (Step 2) is the gate: it refuses (exit 2) on a missing/empty `parts/` directory or any part with invalid frontmatter (missing `part_slug`, missing `dependencies` key, an `estimated_scope` not in `S|M|L`, or a duplicate slug). Surface its stderr verbatim — a refusal means *run `/design translate` first* (or fix the named part).

### Step 2 — Topological sort (the tested helper)

Ordering is deterministic + falsifiable, so it lives in `design_sequence.py` — call it; never hand-order parts in this prompt:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_sequence.py" order <doc-dir>/parts
```

It reads `parts/*.md`, builds the dependency DAG keyed by `part_slug`, and **Kahn topo-sorts with an alphabetical tie-break** (so the same parts always yield the same order — `queued-plans/` never churns across re-runs). Exit 0 prints the ordered slugs, one per line — the first line is the part to activate, the rest queue in order. Exit 2 halts with a concrete message on a **cycle** (`dependency cycle detected: a → b → a`) or a **missing dependency** (`part 'x' depends on 'y' which does not exist in parts/`). Surface stderr verbatim; never guess an order past a refusal.

### Step 3 — Map each part to a PLAN body

For each part (in the helper's order), generate a `/plan`-shaped PLAN body from the part file + parent design. The mapping:

| PLAN section | Source |
|---|---|
| `# Plan: <title>` | the part's h1 title + ` (from design <doc-slug>)` |
| `**Status:** planning` | always `planning` — these are draft plans the human refines with `/plan` before `/work` |
| `**Created:**` | today |
| `**Brief:**` | the part's `## Scope` |
| `## Goal` | the part's Verification criteria, rephrased as user-visible outcomes |
| `## Constraints` | the parent's Quality-Attributes concerns that apply to this part |
| `## Out of scope` | the other part slugs ("see `PLAN-<doc-slug>-<other-slug>.md`") + the parent's Out-of-scope items |
| `## Tasks` | a **draft** decomposition from the part's Scope/Detailed-Design source — each `### N.` with a one-sentence What + Verification. Note in the body that the human runs `/plan` against this to refine before `/work`. |
| `## Risks / open questions` | the parent's Technical Debt & Risks + part-specific concerns |
| `## Verification strategy` | the part's Verification criteria verbatim |
| `## Locked design calls` | a pointer back to the parent design + the key decisions from its Alternatives Considered |

Carry two traceability fields in the PLAN frontmatter so a later `/release` can match a finished plan back to its source part:

```yaml
parent_design_doc: <relative path to the design doc>
parent_part_slug: <the part's part_slug>
```

### Step 4 — Write via `stage_plan.py` (first activated, rest queued — never the singleton)

The named-plan name for each part is `<doc-slug>-<part-slug>`. Use the shipped writer — cross-plugin, since `stage_plan.py` lives in **development-lifecycle** (a hard `requires:` dependency, always installed alongside this plugin); **never** write `PLAN.md` directly.

- **First part (topo-order):**
  1. Get the staging path: `python3 "${CLAUDE_PLUGIN_ROOT}/../development-lifecycle/scripts/stage_plan.py" path <doc-slug>-<first-part-slug>` → write the PLAN body there.
  2. Activate it: `python3 "${CLAUDE_PLUGIN_ROOT}/../development-lifecycle/scripts/stage_plan.py" activate <doc-slug>-<first-part-slug>` → promotes it to the active `PLAN-<doc-slug>-<first-part-slug>.md`. `activate` is **guarded** — exit 2 if an active plan of that name already exists; surface it, never clobber.
- **Each remaining part:** get its staging `path` (`stage_plan.py path <doc-slug>-<part-slug>`, same cross-plugin invocation) and write the PLAN body there — it stays inert in `queued-plans/`, invisible to `/work` until a coordinator activates it.

If a staged or active file already exists on a re-run, show the diff and ask **Overwrite / Keep existing / Cancel** per file — **never silent-clobber** (mirrors translate's Step 5).

### Step 5 — Update the parent's Document History

Append one row and bump `updated` to today; Status stays `final`:

```
| <today> | Sequenced into N plans via /design sequence; first active (PLAN-<doc-slug>-<first-part-slug>.md), N-1 queued in queued-plans/. | final |
```

After `sequence`, the design hand-off is complete — the rest is the normal `/work` → `/review` → `/release` loop on the generated named plans.
