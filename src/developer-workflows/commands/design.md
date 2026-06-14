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

*(Bootstrap → section-by-section walk → Quality-Attributes 11-sub-attr drill-down → Alternatives push-back → draft → review → final lifecycle. Refuses re-invocation after `final`. Inline review pass only; external review is the deferred #5b pointer above.)*

> Full authoring flow lands in task 2 of this plan.

## `/design translate` — final doc → structural `parts/`

*(Gate on `Status: final` via `design_doc.py gate` + the "Detailed Design non-empty" gate → propose a part split (one per Detailed-Design subsection; cap-of-6 soft warning + `--allow-large-design`) → interactive reshape loop → write `<doc-dir>/parts/<part-slug>.md` with inherited + part-specific frontmatter → never silent-clobber → append one Document-History row to the parent. Status stays `final`.)*

> Full translate flow lands in task 3 of this plan.

## `/design sequence` — `parts/` → topo-ordered named plans

*(Gate on `Status: final` + non-empty `parts/` → validate part frontmatter → topo-sort via `design_sequence.py` (Kahn + alphabetical tie-break, cycle + missing-dep detection) → map each part to a PLAN body → write via `stage_plan.py`: the first part `activate` → `PLAN-<doc-slug>-<part-slug>.md`, the rest `path` → `queued-plans/`. Named-plan tiers only — **never** the singleton `PLAN.md`. Carry `parent_design_doc` + `parent_part_slug` frontmatter for traceability; append the Document-History row.)*

> Full sequence flow lands in task 4 of this plan.
