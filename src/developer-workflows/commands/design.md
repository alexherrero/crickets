---
name: design
description: Author → translate → sequence a design doc into a topo-ordered set of named plans. The upstream authoring step above /plan.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: author <slug|brief> (default)  |  translate <slug>  |  sequence <slug>
---

You are running the **design** command — the upstream authoring step of the developer-workflows loop. `/design` sits *above* `/plan`: where `/plan` turns a brief into a task list, `/design` walks a human through a real design doc, gates on human approval, splits the approved design into structural parts, and emits one named plan per part for `/work` + `/review` to execute.

**Arguments:** $ARGUMENTS

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

*(Gate on `Status: final` via `design_doc.py gate` + the "Detailed Design non-empty" gate → propose a part split (one per Detailed-Design subsection; cap-of-6 soft warning + `--allow-large-design`) → interactive reshape loop → write `<doc-dir>/parts/<part-slug>.md` with inherited + part-specific frontmatter → never silent-clobber → append one Document-History row to the parent. Status stays `final`.)*

> Full translate flow lands in task 3 of this plan.

## `/design sequence` — `parts/` → topo-ordered named plans

*(Gate on `Status: final` + non-empty `parts/` → validate part frontmatter → topo-sort via `design_sequence.py` (Kahn + alphabetical tie-break, cycle + missing-dep detection) → map each part to a PLAN body → write via `stage_plan.py`: the first part `activate` → `PLAN-<doc-slug>-<part-slug>.md`, the rest `path` → `queued-plans/`. Named-plan tiers only — **never** the singleton `PLAN.md`. Carry `parent_design_doc` + `parent_part_slug` frontmatter for traceability; append the Document-History row.)*

> Full sequence flow lands in task 4 of this plan.
