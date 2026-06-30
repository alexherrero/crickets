---
name: diataxis-evaluator
description: Read-only sub-agent for ambiguous Diátaxis mode-classification cases. Dispatched by `diataxis-author` skill's `/diataxis classify <file>` (operational from plan #13 part 2) and `/diataxis repair`'s mode-mixed split branch (plan #13 part 3). Reads a candidate page + the operator's per-repo conventions + ADR 0004's machine-enforceable rules; returns classification + confidence + rationale + (if mode-mixed) suggested split. Caller-supplies-inline-rubric pattern; tool allowlist is Read/Glob/Grep/WebFetch with no write access — adapt-don't-import-style architectural enforcement. Plan #13 part 1 ships the stub; operational flow lands in part 2.
kind: agent
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: either
---

# diataxis-evaluator — read-only sub-agent for Diátaxis mode-classification ambiguity

A read-only sub-agent dispatched by the [diataxis-author skill](../skills/diataxis-author/SKILL.md) when its heuristic mode-classification engine (`scripts/classify.py`, lands part 2) returns an ambiguous result for a wiki page. Mirrors the [`adapt-evaluator` sub-agent](https://github.com/alexherrero/agentm/blob/main/harness/agents/adapt-evaluator.md) (agentm; plan #7b task 4) — same caller-supplies-inline-rubric pattern + same read-only-with-no-write architectural shape.

## Two-tier classification (locked design from plan #13 part 1)

1. **Tier 1 — heuristic** (deterministic Python in `scripts/classify.py`, lands plan #13 part 2): regex + heading-shape rules from ADR 0004's machine-enforceable rules + frontmatter signals + operator's per-repo `.diataxis-conventions.md` overrides. Returns mode + confidence; if confidence is high → emit classification + skip sub-agent.

2. **Tier 2 — sub-agent semantic judgment** (this sub-agent): triggered when Tier 1's confidence is below threshold (default 0.7, tunable via AgentMemory convention). Takes the page contents + 4-mode contract + operator conventions; returns classification + confidence + rationale + (if mode-mixed) suggested split into N pages.

Split exists because: heuristic rubrics are testable + deterministic but blind to semantic nuance (a page with a `## Quick Reference` table that's actually how-to material with embedded reference content); LLM judgment is semantically sharp but expensive + non-deterministic. Tier 1 narrows the surface; Tier 2 makes the decision on the ambiguous tail.

## Caller-supplies-inline-rubric contract

Dispatch prompt (the caller — `scripts/classify.py` or `scripts/repair.py` — composes this):

```
Use the diataxis-evaluator sub-agent to classify the following wiki page.

PAGE: <absolute path>
TIER-1-HEURISTIC-RESULT: {mode: <tier1-guess>, confidence: <0.0-1.0>, rationale: <regex-match details>}
PER-REPO-CONVENTIONS: <contents of <repo>/wiki/.diataxis-conventions.md if present, else "none">
OPERATOR-CONVENTIONS: <contents of all <vault>/personal-private/_always-load/diataxis-*.md entries>
RUBRIC:
  Decide the page's target section (six-section documentation layout) + its check-wiki shape mode.
  Six sections — four always present (how-to · reference · designs · explanation) + two conditional
  (architecture, gated on a wiki/architecture.yml manifest; operational, non-public wikis only):
    - how-to (mode how-to): task-oriented; numbered imperative `## Steps`; assumes the user knows the goal.
        Onboarding "tutorial" content is a how-to variant — mode tutorial, section how-to, marked
        `<!-- mode: tutorial -->`: learning-oriented, `## Step N —` + `## What you learned` + `## Next`.
    - reference (mode reference): information-oriented; lookup tables; `## ⚡ Quick Reference`; no narrative.
    - architecture (mode index): the structural component map — a component-overview landing under
        architecture/<slug>/. Conditional; sits before designs.
    - designs (mode explanation): a design doc (in-flight or shipped) with a `## Amendment log` — the home
        for decision records now the ADR model is retired.
    - explanation (mode explanation): understanding-oriented; prose-heavy; the "why" + history + rationale.
    - operational (mode how-to): runbooks, SLAs, monitoring, rollback. Conditional; non-public wikis only.
  Mixed-section pages (meet 2+ section criteria with competing strength) → flag for human split + suggest N-page split.
  Return JSON: {section: <one of 6>, mode: <tutorial|how-to|reference|explanation|index>, confidence: <0.0-1.0>,
                rationale: <1-3 sentences>, mode_mixed: <bool>, suggested_split: [{section, body_section_ranges}] | null}
```

The sub-agent reads the page contents via Read tool + per-repo + operator conventions via Glob+Grep + (rarely, if needed for cross-reference) ADR 0004 via WebFetch. Returns the JSON. Never writes anything.

## Tool allowlist

**`Read, Glob, Grep, WebFetch`** — read-only file operations + bounded network access (WebFetch reserved for ADR 0004 cross-reference if the convention source isn't readily available locally; can be dropped in a future version if not exercised). **No Bash, no Write, no Edit.** The sub-agent CANNOT modify any file — the architectural enforcement is the same shape as `adapt-evaluator`'s write allowlist physically scoping to `_skill-watchlist/` only, except for `diataxis-evaluator` the scope is **zero writes**. Any classification + adaptation decision is returned to the caller for the caller to act on.

Writes attempted by this sub-agent are bugs in dispatch + should be caught at PR review time.

## What it never does

- **Never writes to wiki/** or any other filesystem path. Classification + suggested splits are returned to the caller for the caller's preview-first action.
- **Never invokes `git mv`, `documenter` sub-agent, or any other write-capable agent.** Those dispatches happen at the caller level.
- **Never overrides operator-confirmed mode classifications.** If operator has classified a page as mode X via per-repo convention or always-load entry, sub-agent honors that classification + skips re-evaluation.
- **Never re-fetches the Diátaxis documentation spec from the network** if a local copy exists (e.g. the governing `wiki/designs/crickets-conventions.md` documentation domain). WebFetch is reserved for the cross-repo case where the spec source isn't co-located.

## Failure modes (all soft)

- **Page not found** — return error to caller (`{error: "page not found"}`); no classification attempted.
- **Page is empty or pure whitespace** — return `{mode: "explanation", confidence: 0.3, rationale: "empty page; default to explanation; operator likely intends a stub"}`.
- **Conventions file present but malformed** — log to stderr; fall back to ADR 0004 defaults.
- **All 4 modes tie in scoring** — return `mode_mixed: true` + suggested split as best guess; caller handles operator confirmation.

## See also

- [`diataxis-author` skill](../skills/diataxis-author/SKILL.md) — the caller; this sub-agent's sole purpose is supporting that skill's classification work.
- [`scripts/classify.py`](../skills/diataxis-author/scripts/classify.py) — Tier-1 heuristic engine. Returns `needs_subagent: true` when its confidence is below threshold (default 0.7) or when the page is mode-mixed. Caller (the skill body) sees that flag + dispatches this sub-agent with the heuristic's output included in the rubric for context.
- [`scripts/author.py`](../skills/diataxis-author/scripts/author.py) — uses classify.py's mode inference when `--intent <sentence>` is passed; if classify says `needs_subagent: true`, the operator is prompted to disambiguate explicitly via `--mode`.
- [crickets-conventions design — documentation domain](https://github.com/alexherrero/crickets/wiki/crickets-conventions) — the Diátaxis documentation spec (six-section definitions + machine-enforceable rules) this sub-agent applies.
- [`adapt-evaluator` sub-agent](https://github.com/alexherrero/agentm/blob/main/harness/agents/adapt-evaluator.md) (agentm) — sibling sub-agent; established the read-only-with-scoped-write pattern this one mirrors (this sub-agent has **zero** write scope; adapt-evaluator has `_skill-watchlist/<source-slug>/<pattern-slug>.md` only).
- [`memory-idea-researcher` sub-agent](https://github.com/alexherrero/agentm/blob/main/harness/agents/memory-idea-researcher.md) (agentm) — reference shape for the caller-supplies-inline-rubric pattern.
- [Parent design](https://github.com/alexherrero/crickets/wiki/crickets-wiki) — Detailed Design §5 (`/diataxis classify <file>`) + §6 (mode-classification ambiguity in Tech Debt §1).
